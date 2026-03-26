function parseIntegerEnv(name, defaultValue) {
  const value = Number.parseInt(process.env[name] || `${defaultValue}`, 10);
  return Number.isFinite(value) ? value : defaultValue;
}

module.exports = {
  pollIntervalMs: parseIntegerEnv('PROCESSING_POLL_INTERVAL_MS', 3000),
  jobStaleMs: parseIntegerEnv('PROCESSING_JOB_STALE_MS', 900000),
  recoveryIntervalMs: parseIntegerEnv('PROCESSING_JOB_RECOVERY_INTERVAL_MS', 30000),
  maxRecoveries: parseIntegerEnv('PROCESSING_JOB_MAX_RECOVERIES', 2),
};
