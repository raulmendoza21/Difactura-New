export default function InfoPopover({
  title = 'Informacion',
  description = '',
  items = [],
  align = 'right',
  placement = 'bottom',
  widthClass = 'w-72',
}) {
  const positionClass =
    placement === 'right'
      ? 'left-full top-1/2 ml-3 -translate-y-1/2'
      : placement === 'left'
        ? 'right-full top-1/2 mr-3 -translate-y-1/2'
        : align === 'left'
          ? 'left-0 top-11'
          : align === 'center'
            ? 'left-1/2 top-11 -translate-x-1/2'
            : 'right-0 top-11';

  return (
    <div className="relative isolate z-0 group group-hover:z-[90] group-focus-within:z-[90]">
      <button
        type="button"
        className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-xs font-semibold text-slate-500 shadow-sm transition-colors hover:border-blue-200 hover:text-blue-600"
        aria-label={title}
      >
        i
      </button>

      <div
        className={`pointer-events-none absolute ${positionClass} z-[100] ${widthClass} rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-2xl opacity-0 transition-all duration-200 group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100`}
      >
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
          {title}
        </p>

        {description && (
          <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
        )}

        {items.length > 0 && (
          <ul className="mt-3 space-y-2 text-sm text-slate-600">
            {items.map((item) => (
              <li key={item} className="rounded-xl bg-slate-50 px-3 py-2 leading-5">
                {item}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
