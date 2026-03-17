const router = require('express').Router();
const authController = require('../controllers/authController');
const authMiddleware = require('../middleware/authMiddleware');
const { validateLogin, validateRegister } = require('../validators/authValidator');

router.post('/login', validateLogin, authController.login);
router.post('/register', authMiddleware, validateRegister, authController.register);
router.get('/me', authMiddleware, authController.me);

module.exports = router;
