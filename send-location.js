const fs = require('fs');
const path = require('path');
const https = require('https');

const BOT_TOKEN = '8018448279:AAFGUqua1bsG73Wr8PKuoJjQhXP0UdOOXfQ';

module.exports = (req, res) => {
  if (req.method !== 'POST') {
    return res.status(405).send('Method Not Allowed');
  }

  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', () => {
    try {
      const { uuid, latitude, longitude } = JSON.parse(body);
      if (!uuid || !latitude || !longitude) {
        return res.status(400).send('Missing data');
      }

      const dataPath = path.join(__dirname, 'data.json');
      const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));

      // Найдём владельца по uuid
      let ownerId = null;
      for (const userId in data) {
        const user = data[userId];
        const pet = user.pets?.find(p => p.uuid === uuid);
        if (pet) {
          ownerId = pet.owner_ids[0];
          break;
        }
      }

      if (!ownerId) {
        return res.status(404).send('Owner not found');
      }

      const text = `Ваш питомец был найден!\nhttps://www.google.com/maps?q=${latitude},${longitude}`;
      const url = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage?chat_id=${ownerId}&text=${encodeURIComponent(text)}`;

      https.get(url, tgRes => {
        tgRes.on('data', () => {});
        tgRes.on('end', () => {
          res.status(200).send('Location sent');
        });
      }).on('error', (err) => {
        res.status(500).send('Telegram error');
      });

    } catch (err) {
      res.status(500).send('Server error');
    }
  });
};