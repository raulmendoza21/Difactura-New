import { CONFIDENCE_THRESHOLDS } from '../../utils/constants';
import { formatPercentage } from '../../utils/formatters';

export default function ConfidenceBadge({ value, size = 'sm' }) {
  if (value == null) return <span className="badge bg-slate-100 text-slate-400">N/A</span>;

  const isRatio = Number(value) <= 1;
  const normalized = isRatio ? Number(value) * 100 : Number(value);

  let colorClass, dotColor;
  if (normalized >= CONFIDENCE_THRESHOLDS.HIGH) {
    colorClass = 'bg-emerald-50 text-emerald-700';
    dotColor = 'bg-emerald-500';
  } else if (normalized >= CONFIDENCE_THRESHOLDS.MEDIUM) {
    colorClass = 'bg-amber-50 text-amber-700';
    dotColor = 'bg-amber-500';
  } else {
    colorClass = 'bg-red-50 text-red-700';
    dotColor = 'bg-red-500';
  }

  return (
    <span className={`badge ${colorClass} ${size === 'lg' ? 'px-3 py-1.5 text-sm' : ''}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor} mr-1.5`} />
      {formatPercentage(value, { isRatio })}
    </span>
  );
}
