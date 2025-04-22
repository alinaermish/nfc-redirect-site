const fs = require('fs');
const path = require('path');
const https = require('https');

module.exports = async (req, res) => {
  console.log("📩 [GET-LINK] Новый запрос получен");

  if (req.method !== 'POST') {
    console.log("⛔ [GET-LINK] Неверный метод запроса:", req.method);
    return res.status(405).send('Method not allowed');
  }

  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', () => {
    try {
      console.log("📦 [GET-LINK] Получено тело:", body);
      const { uuid, latitude, longitude } = JSON.parse(body);

      if (!uuid || !latitude || !longitude) {
        console.log("⚠️ [GET-LINK] Отсутствуют данные:", { uuid, latitude, longitude });
        return res.status(400).send('Missing data');
      }

      console.log("🔍 [GET-LINK] UUID:", uuid);
      const dataPath = path.join(__dirname, 'data.json');
      const rawData = fs.readFileSync(dataPath, 'utf8');
      const json = JSON.parse(rawData);

      let link = null;
      let ownerIds = [];

      for (const userId in json) {
        const user = json[userId];
        if (!user.pets) continue;

        const pet = user.pets.find(p => p.uuid === uuid);
        if (pet) {
          link = pet.link;
          ownerIds = pet.owner_ids;
          console.log("✅ [GET-LINK] Найден питомец:", pet.name);
          break;
        }
      }

      if (!link || ownerIds.length === 0) {
        console.log("❌ [GET-LINK] Питомец не найден или нет владельцев.");
        return res.status(404).send('Pet not found');
      }

      const locationMessage = `🔔 Питомец найден!\n📍 https://maps.google.com/?q=${latitude},${longitude}`;
      const botToken = '8018448279:AAFGUqua1bsG73Wr8PKuoJjQhXP0UdOOXfQ';

      for (const id of ownerIds) {
        const url = `https://api.telegram.org/bot${botToken}/sendMessage?chat_id=${id}&text=${encodeURIComponent(locationMessage)}`;
        console.log("📬 [GET-LINK] Отправка в Telegram ID:", id);
        https.get(url).on('error', (err) => {
          console.log("❌ [GET-LINK] Ошибка Telegram:", err.message);
        });
      }

      console.log("➡️ [GET-LINK] Перенаправление на:", link);
      res.status(200).json({ redirectTo: link });

    } catch (err) {
      console.log("💥 [GET-LINK] Ошибка сервера:", err);
      res.status(500).send('Server error');
    }
  });
};
