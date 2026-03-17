const router = require('express').Router();
const customerController = require('../controllers/customerController');
const authMiddleware = require('../middleware/authMiddleware');

router.use(authMiddleware);

router.get('/', customerController.getAll);
router.get('/:id', customerController.getById);
router.put('/:id', customerController.update);

module.exports = router;
