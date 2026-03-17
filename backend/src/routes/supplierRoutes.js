const router = require('express').Router();
const supplierController = require('../controllers/supplierController');
const authMiddleware = require('../middleware/authMiddleware');

router.use(authMiddleware);

router.get('/', supplierController.getAll);
router.get('/:id', supplierController.getById);
router.put('/:id', supplierController.update);

module.exports = router;
