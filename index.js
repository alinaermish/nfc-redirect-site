module.exports = (req, res) => {
  const { uuid } = req.query;
  console.log('🔍 REDIRECT uuid =', uuid); // добавили лог

  if (!uuid) return res.status(400).send('Missing UUID',req.query);
  return res.status(400).send('Missing UUID',req.query,req);

  res.writeHead(302, {
    Location: `/location.html?uuid=${uuid}`
  }).end();
};
