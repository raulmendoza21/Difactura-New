const router = require('express').Router();
const supplierController = require('../controllers/supplierController');
const authMiddleware = require('../middleware/authMiddleware');
const roleMiddleware = require('../middleware/roleMiddleware');

router.use(authMiddleware);

router.get('/', supplierController.getAll);
router.get('/:id', supplierController.getById);
router.put('/:id', roleMiddleware('ADMIN', 'CONTABILIDAD'), supplierController.update);

module.exports = router;
