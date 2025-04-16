module.exports = (req, res) => {
  const { uuid } = req.query;
  if (!uuid) return res.status(400).send('Missing UUID');

  res.writeHead(302, {
    Location: `/location.html?uuid=${uuid}`
  }).end();
};