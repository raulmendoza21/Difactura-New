const router = require('express').Router();
const authController = require('../controllers/authController');
const authMiddleware = require('../middleware/authMiddleware');
const roleMiddleware = require('../middleware/roleMiddleware');
const { asesoriaOnly } = require('../middleware/tipoUsuarioMiddleware');
const { validateLogin, validateRegister } = require('../validators/authValidator');

router.post('/login', validateLogin, authController.login);
router.post('/register', authMiddleware, asesoriaOnly, roleMiddleware('ADMIN'), validateRegister, authController.register);
router.get('/me', authMiddleware, authController.me);

module.exports = router;
