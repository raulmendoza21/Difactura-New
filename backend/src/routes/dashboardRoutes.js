const router = require('express').Router();
const dashboardController = require('../controllers/dashboardController');
const authMiddleware = require('../middleware/authMiddleware');
const { asesoriaOnly } = require('../middleware/tipoUsuarioMiddleware');

router.use(authMiddleware);

router.get('/', asesoriaOnly, dashboardController.getStats);

module.exports = router;
