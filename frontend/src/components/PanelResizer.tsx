import { useRef } from 'react';

interface Props {
  label: string;
  value: number;
  min: number;
  max: number;
  reverse?: boolean;
  onChange: (value: number) => void;
}

export function PanelResizer({ label, value, min, max, reverse, onChange }: Props) {
  const drag = useRef<{ x: number; value: number } | null>(null);
  const update = (next: number) => onChange(Math.max(min, Math.min(max, next)));
  return <div role="separator" tabIndex={0} aria-label={label}
    aria-orientation="vertical" aria-valuemin={min} aria-valuemax={max} aria-valuenow={value}
    className="panel-resizer" title={`${label}: drag or use arrow keys. Home / End for limits.`}
    onPointerDown={event => {
      drag.current = { x: event.clientX, value };
      event.currentTarget.setPointerCapture(event.pointerId);
      event.preventDefault();
    }}
    onPointerMove={event => {
      if (drag.current) update(drag.current.value + (event.clientX - drag.current.x) * (reverse ? -1 : 1));
    }}
    onPointerUp={() => { drag.current = null; }}
    onLostPointerCapture={() => { drag.current = null; }}
    onKeyDown={event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      if (event.key === 'Home') update(min);
      else if (event.key === 'End') update(max);
      else update(value + (event.key === 'ArrowRight' ? 16 : -16) * (reverse ? -1 : 1));
    }} />;
}
