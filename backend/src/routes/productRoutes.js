const router = require('express').Router();
const productController = require('../controllers/productController');
const authMiddleware = require('../middleware/authMiddleware');

router.use(authMiddleware);

router.get('/', productController.getAll);
router.get('/:id', productController.getById);

module.exports = router;
