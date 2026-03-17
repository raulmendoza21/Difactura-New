const productRepo = require('../repositories/productRepository');

async function getAll(req, res, next) {
  try {
    const products = await productRepo.findAll();
    res.json(products);
  } catch (err) { next(err); }
}

async function getById(req, res, next) {
  try {
    const product = await productRepo.findById(parseInt(req.params.id, 10));
    if (!product) return res.status(404).json({ error: true, message: 'Producto no encontrado' });
    res.json(product);
  } catch (err) { next(err); }
}

module.exports = { getAll, getById };
