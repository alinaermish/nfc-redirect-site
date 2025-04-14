const fs = require('fs');
const path = require('path');

module.exports = async (req, res) => {
  const { id } = req.query;

  if (!id) {
    return res.status(400).send('Missing ID');
  }

  const dataPath = path.join(__dirname, 'data.json');

  let rawData;
  try {
    rawData = fs.readFileSync(dataPath, 'utf8');
  } catch (err) {
    return res.status(500).send('Ошибка загрузки базы данных.');
  }

  let json;
  try {
    json = JSON.parse(rawData);
  } catch (err) {
    return res.status(500).send('Ошибка чтения данных.');
  }

  // Ищем ссылку по UUID
  let foundPet = null;
  for (const userId in json) {
    const user = json[userId];
    if (!user.pets) continue;

    for (const pet of user.pets) {
      if (pet.uuid === id) {
        foundPet = pet;
        break;
      }
    }

    if (foundPet) break;
  }

  if (foundPet) {
    return res.writeHead(302, { Location: foundPet.link }).end();
  } else {
    return res.status(404).send('Питомец не найден. Ссылка недействительна.');
  }
};