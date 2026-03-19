const router = require('express').Router();
const invoiceController = require('../controllers/invoiceController');
const authMiddleware = require('../middleware/authMiddleware');
const roleMiddleware = require('../middleware/roleMiddleware');
const upload = require('../middleware/fileUpload');
const { validateInvoiceUpdate } = require('../validators/invoiceValidator');

router.use(authMiddleware);

router.post(
  '/upload',
  roleMiddleware('ADMIN', 'CONTABILIDAD'),
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
router.put('/:id', roleMiddleware('ADMIN', 'CONTABILIDAD', 'REVISOR'), validateInvoiceUpdate, invoiceController.update);
router.post('/:id/reprocess', roleMiddleware('ADMIN', 'CONTABILIDAD', 'REVISOR'), invoiceController.reprocess);
router.post('/:id/validate', roleMiddleware('ADMIN', 'CONTABILIDAD', 'REVISOR'), invoiceController.validate);
router.post('/:id/reject', roleMiddleware('ADMIN', 'CONTABILIDAD', 'REVISOR'), invoiceController.reject);

module.exports = router;
