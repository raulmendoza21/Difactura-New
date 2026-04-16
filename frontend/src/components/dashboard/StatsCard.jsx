import { memo } from 'react';
import InfoPopover from '../common/InfoPopover';

export default memo(function StatsCard({
  title,
  value,
  icon,
  color = 'blue',
  subtitle,
  infoTitle,
  infoDescription,
  infoItems,
}) {
  const colors = {
    blue: 'from-blue-500 to-blue-600 shadow-blue-200',
    emerald: 'from-emerald-500 to-emerald-600 shadow-emerald-200',
    amber: 'from-amber-500 to-amber-600 shadow-amber-200',
    red: 'from-red-500 to-red-600 shadow-red-200',
    purple: 'from-purple-500 to-purple-600 shadow-purple-200',
  };

  return (
    <div className="card p-5 hover:shadow-md transition-shadow duration-200">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-slate-500">{title}</p>
            {infoTitle && (
              <InfoPopover
                title={infoTitle}
                description={infoDescription}
                items={infoItems}
                widthClass="w-64"
                align="left"
              />
            )}
          </div>
          <p className="text-3xl font-bold text-slate-800 mt-1">{value ?? '-'}</p>
          {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
        </div>
        <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${colors[color]} shadow-sm flex items-center justify-center flex-shrink-0`}>
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={icon} />
          </svg>
        </div>
      </div>
    </div>
  );
})
