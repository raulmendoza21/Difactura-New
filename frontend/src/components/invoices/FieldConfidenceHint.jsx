import { CONFIDENCE_THRESHOLDS_RATIO } from '../../utils/constants';

export function isFieldSuspicious(value) {
  return typeof value === 'number' && value < CONFIDENCE_THRESHOLDS_RATIO.SUSPICIOUS;
}

export function getFieldInputClass(value) {
  if (!isFieldSuspicious(value)) {
    return 'input-field';
  }

  return 'input-field border-amber-300 bg-amber-50/50 focus:ring-amber-500/20 focus:border-amber-500';
}

export default function FieldConfidenceHint({ value, label = '', compact = false }) {
  if (!isFieldSuspicious(value)) return null;

  return (
    <span
      title={label ? `${label}: revisar este campo` : 'Campo a revisar'}
      aria-label={label ? `${label}: revisar este campo` : 'Campo a revisar'}
      className={`inline-block rounded-full bg-amber-400 ring-2 ring-amber-100 ${compact ? 'h-2.5 w-2.5' : 'h-3 w-3'}`}
    />
  );
}
