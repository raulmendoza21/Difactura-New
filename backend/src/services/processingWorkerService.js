const crypto = require('crypto');
const invoiceRepo = require('../repositories/invoiceRepository');
const documentProcessingService = require('./documentProcessingService');

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

class ProcessingWorkerService {
  constructor() {
    this.workerId = process.env.PROCESSING_WORKER_ID || `backend-${crypto.randomUUID()}`;
    this.pollIntervalMs = parseInt(process.env.PROCESSING_POLL_INTERVAL_MS || '3000', 10);
    this.jobStaleMs = parseInt(process.env.PROCESSING_JOB_STALE_MS || '900000', 10);
    this.running = false;
    this.loopPromise = null;
  }

  async start() {
    if (this.running) {
      return;
    }

    this.running = true;
    const recoveredJobs = await this.recoverStaleJobs();

    console.log(
      `[processing-worker:${this.workerId}] Iniciado. Poll=${this.pollIntervalMs}ms, stale=${this.jobStaleMs}ms, recuperados=${recoveredJobs}`
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

  async recoverStaleJobs() {
    const cutoffDate = new Date(Date.now() - this.jobStaleMs);
    const jobs = await invoiceRepo.requeueStaleJobs(cutoffDate);
    return jobs.length;
  }

  async runLoop() {
    while (this.running) {
      try {
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
