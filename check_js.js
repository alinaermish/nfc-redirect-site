module.exports = (req, res) => {
      return res.status(405).send('I return only JS files');
    }