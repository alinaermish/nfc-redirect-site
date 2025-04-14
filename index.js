import { writeFileSync } from 'fs';

export default async function handler(req, res) {
  const { id } = req.query;

  if (!id) {
    return res.status(400).send('Missing ID');
  }

  const ip = req.headers['x-forwarded-for'] || req.socket.remoteAddress;

  // Отправка IP-адреса в Telegram-бота
  await fetch(`https://api.telegram.org/bot<ТВОЙ_ТОКЕН>/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: '<ЗДЕСЬ_БУДЕТ_ID_ПОЛЬЗОВАТЕЛЯ>',
      text: `Сканирован тег с ID: ${id}\nIP: ${ip}`
    })
  });

  // Пример получения taplink из data.json — будет позже заменено динамически
  const data = {
    "965ce123-4957-417b-b6fc-2f292cd6e026": "https://taplink.cc/example"
  };

  const redirectUrl = data[id];

  if (!redirectUrl) {
    return res.status(404).send('Ссылка не найдена');
  }

  res.writeHead(302, {
    Location: redirectUrl
  });
  res.end();
}