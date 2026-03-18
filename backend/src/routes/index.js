const router = require('express').Router();

router.use('/auth', require('./authRoutes'));
router.use('/invoices', require('./invoiceRoutes'));
router.use('/suppliers', require('./supplierRoutes'));
router.use('/companies', require('./customerRoutes'));
router.use('/customers', require('./customerRoutes'));
router.use('/products', require('./productRoutes'));
router.use('/dashboard', require('./dashboardRoutes'));

module.exports = router;
