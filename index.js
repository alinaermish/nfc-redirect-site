module.exports = (req, res) => {
  const { uuid } = req.query;
  console.log('🔍 REDIRECT uuid =', uuid); // добавили лог

  if (!uuid) return res.status(400).send(`Missing UUID,${uuid}`);
  // else return res.status(400).send(`hah2 UUID,${uuid},${req})`);

  res.writeHead(302, {
    Location: `/public/location.html?uuid=${uuid}`
  }).end();
};
