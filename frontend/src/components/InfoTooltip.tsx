import React, { useState } from 'react';

interface InfoTooltipProps {
  title: string;
  description: string;
  children: React.ReactNode;
  id?: string;
}

export const InfoTooltip: React.FC<InfoTooltipProps> = ({
  title,
  description,
  children,
  id,
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const tooltipId = id || `info-tooltip-${title.toLowerCase().replace(/[^a-z0-9]/g, '-')}`;

  return (
    <span
      className="relative inline-flex items-center group cursor-help"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation();
          setIsVisible(false);
        }
      }}
      tabIndex={0}
      role="button"
      aria-describedby={isVisible ? tooltipId : undefined}
      aria-label={`${title}: ${description}`}
    >
      <span className="border-b border-dotted border-muted/80 hover:border-accent transition-colors">
        {children}
      </span>

      {isVisible && (
        <span
          id={tooltipId}
          role="tooltip"
          className="info-tooltip-popover absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 rounded-lg bg-panel border border-line shadow-xl text-ink text-left z-50 pointer-events-none animate-in fade-in duration-100"
        >
          <span className="block text-xs font-bold text-accent mb-1">{title}</span>
          <span className="block text-[11px] text-muted leading-relaxed font-normal">{description}</span>
          <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-panel" />
        </span>
      )}
    </span>
  );
};
