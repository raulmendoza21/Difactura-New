const STYLES = {
  info: {
    container: 'border-blue-200 bg-blue-50/80 text-blue-900',
    badge: 'bg-blue-100 text-blue-700',
    icon: 'text-blue-600 bg-blue-100',
    itemDot: 'bg-blue-500',
  },
  warning: {
    container: 'border-amber-200 bg-amber-50/90 text-amber-950',
    badge: 'bg-amber-100 text-amber-700',
    icon: 'text-amber-600 bg-amber-100',
    itemDot: 'bg-amber-500',
  },
  success: {
    container: 'border-emerald-200 bg-emerald-50/90 text-emerald-950',
    badge: 'bg-emerald-100 text-emerald-700',
    icon: 'text-emerald-600 bg-emerald-100',
    itemDot: 'bg-emerald-500',
  },
  error: {
    container: 'border-red-200 bg-red-50/90 text-red-950',
    badge: 'bg-red-100 text-red-700',
    icon: 'text-red-600 bg-red-100',
    itemDot: 'bg-red-500',
  },
  progress: {
    container: 'border-indigo-200 bg-indigo-50/90 text-indigo-950',
    badge: 'bg-indigo-100 text-indigo-700',
    icon: 'text-indigo-600 bg-indigo-100',
    itemDot: 'bg-indigo-500',
  },
};

function Icon({ tone }) {
  if (tone === 'success') {
    return (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="m5 13 4 4L19 7" />
      </svg>
    );
  }

  if (tone === 'error') {
    return (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 8v4m0 4h.01M10.29 3.86l-7.5 13A1 1 0 0 0 3.65 18h16.7a1 1 0 0 0 .86-1.5l-7.5-13a1 1 0 0 0-1.72 0Z" />
      </svg>
    );
  }

  if (tone === 'warning') {
    return (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 9v4m0 4h.01M4.93 19h14.14c.78 0 1.26-.84.87-1.5L12.87 5c-.39-.66-1.35-.66-1.74 0L4.06 17.5c-.39.66.09 1.5.87 1.5Z" />
      </svg>
    );
  }

  if (tone === 'progress') {
    return (
      <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
        <path className="opacity-90" d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </svg>
    );
  }

  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 16v-4m0-4h.01M3 12a9 9 0 1 1 18 0 9 9 0 0 1-18 0Z" />
    </svg>
  );
}

export default function StatusPanel({
  tone = 'info',
  eyebrow,
  title,
  description,
  items = [],
  footer,
  compact = false,
}) {
  const styles = STYLES[tone] || STYLES.info;

  return (
    <div className={`card border ${styles.container} ${compact ? 'p-4' : 'p-5'} animate-fade-in`}>
      <div className="flex gap-4">
        <div className={`w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 ${styles.icon}`}>
          <Icon tone={tone} />
        </div>
        <div className="min-w-0 flex-1">
          {eyebrow && (
            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold uppercase tracking-[0.14em] ${styles.badge}`}>
              {eyebrow}
            </span>
          )}
          {title && <h3 className="mt-2 text-base font-bold">{title}</h3>}
          {description && <p className="mt-1.5 text-sm leading-6 opacity-90">{description}</p>}
          {items.length > 0 && (
            <ul className="mt-3 space-y-2">
              {items.map((item, index) => (
                <li key={`${item}-${index}`} className="flex gap-2.5 text-sm leading-6">
                  <span className={`w-2 h-2 rounded-full mt-2 ${styles.itemDot}`} />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}
          {footer && <p className="mt-3 text-xs font-medium opacity-75">{footer}</p>}
        </div>
      </div>
    </div>
  );
}
