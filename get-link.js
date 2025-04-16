const fs = require('fs');
const path = require('path');
const https = require('https');

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).send('Method not allowed');

  const { uuid, latitude, longitude } = req.body;
  if (!uuid || !latitude || !longitude) {
    return res.status(400).send('Missing data');
  }

  const dataPath = path.join(process.cwd(), 'data.json');
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
      break;
    }
  }

  if (!link || ownerIds.length === 0) {
    return res.status(404).send('Pet not found');
  }

  const locationMessage = `🔔 Питомец был найден!\n📍 https://maps.google.com/?q=${latitude},${longitude}`;

  for (const id of ownerIds) {
    const url = `https://api.telegram.org/bot<8018448279:AAFGUqua1bsG73Wr8PKuoJjQhXP0UdOOXfQ>/sendMessage?chat_id=${id}&text=${encodeURIComponent(locationMessage)}`;
    https.get(url).on('error', () => {});
  }

  res.status(200).json({ redirectTo: link });
};