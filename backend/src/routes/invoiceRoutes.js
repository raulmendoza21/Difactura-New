const router = require('express').Router();
const invoiceController = require('../controllers/invoiceController');
const authMiddleware = require('../middleware/authMiddleware');
const roleMiddleware = require('../middleware/roleMiddleware');
const { asesoriaOnly } = require('../middleware/tipoUsuarioMiddleware');
const upload = require('../middleware/fileUpload');
const { validateInvoiceUpdate } = require('../validators/invoiceValidator');

router.use(authMiddleware);

router.post(
  '/upload',
  roleMiddleware('ADMIN', 'CONTABILIDAD', 'EMPRESA_UPLOAD'),
  upload.fields([
    { name: 'files', maxCount: 25 },
    { name: 'camera_files', maxCount: 25 },
    { name: 'file', maxCount: 1 },
  ]),
  invoiceController.upload
);
router.get('/', invoiceController.getAll);
router.get('/documents/:documentId/file', invoiceController.getDocumentFile);
router.get('/:id', invoiceController.getById);
router.put('/:id', asesoriaOnly, roleMiddleware('ADMIN', 'CONTABILIDAD', 'REVISOR'), validateInvoiceUpdate, invoiceController.update);
router.post('/:id/reprocess', asesoriaOnly, roleMiddleware('ADMIN', 'CONTABILIDAD', 'REVISOR'), invoiceController.reprocess);
router.post('/:id/validate', asesoriaOnly, roleMiddleware('ADMIN', 'CONTABILIDAD', 'REVISOR'), invoiceController.validate);
router.post('/:id/reject', asesoriaOnly, roleMiddleware('ADMIN', 'CONTABILIDAD', 'REVISOR'), invoiceController.reject);

module.exports = router;
