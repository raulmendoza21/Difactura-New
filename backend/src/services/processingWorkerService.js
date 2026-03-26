const crypto = require('crypto');
const processingConfig = require('../config/processing');
const invoiceRepo = require('../repositories/invoiceRepository');
const documentProcessingService = require('./documentProcessingService');

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

class ProcessingWorkerService {
  constructor() {
    this.workerId = process.env.PROCESSING_WORKER_ID || `backend-${crypto.randomUUID()}`;
    this.pollIntervalMs = processingConfig.pollIntervalMs;
    this.jobStaleMs = processingConfig.jobStaleMs;
    this.recoveryIntervalMs = processingConfig.recoveryIntervalMs;
    this.maxRecoveries = processingConfig.maxRecoveries;
    this.running = false;
    this.loopPromise = null;
    this.lastRecoveryAt = 0;
  }

  async start() {
    if (this.running) {
      return;
    }

    this.running = true;
    const recoveredJobs = await this.recoverStaleJobs({ force: true, reason: 'startup' });

    console.log(
      `[processing-worker:${this.workerId}] Iniciado. Poll=${this.pollIntervalMs}ms, stale=${this.jobStaleMs}ms, recovery=${this.recoveryIntervalMs}ms, recuperados=${recoveredJobs}`
    );

    this.loopPromise = this.runLoop();
  }

  async stop() {
    if (!this.running) {
      return;
    }

    this.running = false;

    if (this.loopPromise) {
      await this.loopPromise;
      this.loopPromise = null;
    }

    console.log(`[processing-worker:${this.workerId}] Detenido`);
  }

  async recoverStaleJobs({ force = false, reason = 'scheduled' } = {}) {
    const now = Date.now();
    if (!force && now - this.lastRecoveryAt < this.recoveryIntervalMs) {
      return 0;
    }

    this.lastRecoveryAt = now;

    const cutoffDate = new Date(now - this.jobStaleMs);
    const jobs = await invoiceRepo.requeueStaleJobs(cutoffDate, {
      maxRecoveries: this.maxRecoveries,
    });

    if (jobs.length > 0) {
      console.warn(
        `[processing-worker:${this.workerId}] Recuperados ${jobs.length} jobs atascados (${reason})`
      );
    }

    return jobs.length;
  }

  async runLoop() {
    while (this.running) {
      try {
        await this.recoverStaleJobs();
        const job = await invoiceRepo.claimNextPendingJob(this.workerId);

        if (!job) {
          await sleep(this.pollIntervalMs);
          continue;
        }

        console.log(`[processing-worker:${this.workerId}] Job ${job.id} reclamado para factura ${job.factura_id}`);
        await documentProcessingService.processJob(job);
        console.log(`[processing-worker:${this.workerId}] Job ${job.id} completado`);
      } catch (error) {
        console.error(`[processing-worker:${this.workerId}] Error en loop de procesamiento: ${error.message}`);
        await sleep(this.pollIntervalMs);
      }
    }
  }
}

module.exports = new ProcessingWorkerService();
