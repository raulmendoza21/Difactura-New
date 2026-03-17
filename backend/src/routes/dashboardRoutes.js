const router = require('express').Router();
const dashboardController = require('../controllers/dashboardController');
const authMiddleware = require('../middleware/authMiddleware');

router.use(authMiddleware);

router.get('/', dashboardController.getStats);

module.exports = router;
