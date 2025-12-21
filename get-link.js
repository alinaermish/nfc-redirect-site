const fs = require('fs');
const path = require('path');
const https = require('https');

const BOT_TOKEN = process.env.BOT_TOKEN;

module.exports = async (req, res) => {
  console.log("📩 [GET-LINK] Новый запрос получен");

  if (req.method !== 'POST') {
    console.log("⛔ [GET-LINK] Неверный метод запроса:", req.method);
    return res.status(405).send('Method not allowed');
  }

  let body = '';
  req.on('data', chunk => body += chunk);

  req.on('end', async () => {
    try {
      console.log("📦 [GET-LINK] Получено тело:", body);
      const { uuid, latitude, longitude } = JSON.parse(body);

      if (!uuid) {
        console.log("⚠️ [GET-LINK] Отсутствует UUID");
        return res.status(400).send('Missing uuid');
      }

      const dataPath = path.join(__dirname, 'data.json');
      const json = JSON.parse(fs.readFileSync(dataPath, 'utf8'));

      let link = null;
      let ownerIds = [];
      let foundPet = null;

      for (const userId in json) {
        const user = json[userId];
        if (!user.pets) continue;

        const pet = user.pets.find(p => p.uuid === uuid);
        if (pet) {
          link = pet.link;
          ownerIds = pet.owner_ids;
          foundPet = pet;
          console.log("✅ [GET-LINK] Найден питомец:", pet.name);
          break;
        }
      }

      if (!foundPet || !link || ownerIds.length === 0) {
        console.log("❌ [GET-LINK] Питомец не найден или нет владельцев.");
        return res.status(404).send('Pet not found');
      }

      if (latitude && longitude) {
        const locationMessage = `🔔 Питомец найден\n🐾 ${foundPet.name || "Имя неизвестно"}\n📍 https://maps.google.com/?q=${latitude},${longitude}`;

        await Promise.all(ownerIds.map(id => {
          const url = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage?chat_id=${id}&text=${encodeURIComponent(locationMessage)}`;
          return new Promise((resolve) => {
            const request = https.get(url, (tgRes) => {
              tgRes.on('data', () => {});
              tgRes.on('end', () => {
                console.log(`📬 [GET-LINK] Отправлено в Telegram ID: ${id}`);
                resolve();
              });
            });
            request.on('error', (err) => {
              console.log("❌ [GET-LINK] Ошибка Telegram:", err.message);
              resolve();
            });
          });
        }));
      } else {
        console.log("⚠️ [GET-LINK] Локация не предоставлена. Отправка уведомлений не требуется.");
      }

      console.log("➡️ [GET-LINK] Перенаправление на:", link);
      res.status(200).json({ redirectTo: link });

    } catch (err) {
      console.log("💥 [GET-LINK] Ошибка сервера:", err);
      res.status(500).send('Server error');
    }
  });
};
