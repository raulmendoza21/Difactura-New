const router = require('express').Router();
const customerController = require('../controllers/customerController');
const authMiddleware = require('../middleware/authMiddleware');
const roleMiddleware = require('../middleware/roleMiddleware');

router.use(authMiddleware);

router.get('/', customerController.getAll);
router.get('/:id', customerController.getById);
router.put('/:id', roleMiddleware('ADMIN', 'CONTABILIDAD'), customerController.update);

module.exports = router;
