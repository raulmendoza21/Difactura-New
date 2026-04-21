// Configuracion de tarificacion / hitos de volumen documental.
// Mientras no exista una tabla `empresa_plan` en BD, estos valores se usan
// como referencia visual en el centro operativo (barra "Documentos procesados").
//
// Cuando se introduzca un plan por empresa o asesoria, el backend deberia
// devolver `stats.plan.cuota_docs_mes` y aqui se podra deprecar la lista
// de hitos y usar directamente la cuota contratada.

// Permite override por entorno: VITE_BILLING_MILESTONES="50,100,250,500"
function parseEnvMilestones(raw) {
  if (!raw) return null;
  const parsed = String(raw)
    .split(',')
    .map((v) => parseInt(v.trim(), 10))
    .filter((n) => Number.isFinite(n) && n > 0)
    .sort((a, b) => a - b);
  return parsed.length > 0 ? parsed : null;
}

const ENV_MILESTONES = parseEnvMilestones(import.meta?.env?.VITE_BILLING_MILESTONES);

export const BILLING_MILESTONES =
  ENV_MILESTONES || [50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000];

export function getNextMilestone(processedTotal = 0, milestones = BILLING_MILESTONES) {
  const next = milestones.find((m) => m > processedTotal);
  if (next) return next;
  // Si superamos el ultimo hito, redondeamos al siguiente millar.
  return Math.max(milestones[milestones.length - 1] || 1000, Math.ceil((processedTotal + 1) / 1000) * 1000);
}
