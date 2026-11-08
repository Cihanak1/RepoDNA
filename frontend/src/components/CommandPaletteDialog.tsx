import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Command,
  Download,
  FileCode2,
  FolderTree,
  Layers,
  Moon,
  RefreshCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Sun,
  X,
} from 'lucide-react';
import { readPreference, savePreference } from '../utils/preferences';
import type { FileNode } from '../types/repodna';
import type { GraphDensityMode, GraphGroupingMode, LayoutMode } from '../utils/graphLayout';

interface CommandPaletteDialogProps {
  isOpen: boolean;
  onClose: () => void;
  files: FileNode[];
  onSelectFile: (fileId: string) => void;
  onSwitchTab: (tab: 'studio' | 'report') => void;
  onToggleTheme: () => void;
  onChangeLayout: (mode: LayoutMode) => void;
  onChangeGrouping: (mode: GraphGroupingMode) => void;
  onChangeDensity: (mode: GraphDensityMode) => void;
  onToggleCyclesOnly: () => void;
  onResetFilters: () => void;
  onExportReport?: (format: 'json' | 'html') => void;
  onLoadDemo: () => void;
}

interface PaletteAction {
  id: string;
  category: 'Navigation & Actions' | 'Graph Controls' | 'Repository Modules';
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  badge?: string;
  onRun: () => void;
}

export const CommandPaletteDialog: React.FC<CommandPaletteDialogProps> = ({
  isOpen,
  onClose,
  files,
  onSelectFile,
  onSwitchTab,
  onToggleTheme,
  onChangeLayout,
  onChangeGrouping,
  onChangeDensity,
  onToggleCyclesOnly,
  onResetFilters,
  onExportReport,
  onLoadDemo,
}) => {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [recent, setRecent] = useState(() => readPreference<string[]>('recentCommands', [], (v): v is string[] => Array.isArray(v) && v.every(item => typeof item === 'string')));
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen && !dialog.open) {
      setQuery('');
      setActiveIndex(0);
      dialog.showModal();
      window.setTimeout(() => {
        if (dialog.open) inputRef.current?.focus();
      }, 20);
    } else if (!isOpen && dialog.open) {
      dialog.close();
    }
  }, [isOpen]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const handleClose = () => {
      // A queued close event from a previous session must not close a reopened dialog.
      if (dialog.open) return;
      dialog.returnValue = '';
      onClose();
    };
    dialog.addEventListener('close', handleClose);

    let onBackdropClick: ((e: MouseEvent) => void) | null = null;
    if (!('closedBy' in HTMLDialogElement.prototype)) {
      onBackdropClick = (event: MouseEvent) => {
        if (event.target !== dialog) return;
        const rect = dialog.getBoundingClientRect();
        const inside =
          rect.top <= event.clientY &&
          event.clientY <= rect.top + rect.height &&
          rect.left <= event.clientX &&
          event.clientX <= rect.left + rect.width;
        if (!inside) dialog.close();
      };
      dialog.addEventListener('click', onBackdropClick);
    }
    return () => {
      dialog.removeEventListener('close', handleClose);
      if (onBackdropClick) dialog.removeEventListener('click', onBackdropClick);
    };
  }, [onClose]);

  const actions = useMemo<PaletteAction[]>(() => {
    const baseActions: PaletteAction[] = [
      {
        id: 'act-studio',
        category: 'Navigation & Actions',
        title: 'Switch to Architecture Studio View',
        subtitle: 'Interactive module dependency graph and inspector',
        icon: <FileCode2 className="w-4 h-4 text-accent" aria-hidden="true" />,
        badge: 'View',
        onRun: () => {
          onSwitchTab('studio');
          onClose();
        },
      },
      {
        id: 'act-report',
        category: 'Navigation & Actions',
        title: 'Open Health & Transparency Report',
        subtitle: 'Rule-based architectural deductions, circular chains, and git churn',
        icon: <ShieldCheck className="w-4 h-4 text-success" aria-hidden="true" />,
        badge: 'View',
        onRun: () => {
          onSwitchTab('report');
          onClose();
        },
      },
      {
        id: 'act-theme',
        category: 'Navigation & Actions',
        title: 'Toggle Dark / Light Workstation Theme',
        subtitle: 'Switch color scheme across all panels and canvas',
        icon: <Sun className="w-4 h-4 text-warning" aria-hidden="true" />,
        badge: 'Theme',
        onRun: () => {
          onToggleTheme();
          onClose();
        },
      },
      {
        id: 'act-demo',
        category: 'Navigation & Actions',
        title: 'Load Labeled Demo Showcase Dataset',
        subtitle: 'Inspect multi-language sample architecture with cycles and hotspots',
        icon: <Sparkles className="w-4 h-4 text-warning" aria-hidden="true" />,
        badge: 'Scan',
        onRun: () => {
          onLoadDemo();
          onClose();
        },
      },
      {
        id: 'grp-dirs',
        category: 'Graph Controls',
        title: 'Group Graph by Directory Packages (Collapse Nodes)',
        subtitle: 'Aggregate files by directory to reduce node and edge count',
        icon: <FolderTree className="w-4 h-4 text-accent" aria-hidden="true" />,
        badge: 'Cluster',
        onRun: () => {
          onChangeGrouping('directories');
          onSwitchTab('studio');
          onClose();
        },
      },
      {
        id: 'grp-files',
        category: 'Graph Controls',
        title: 'Expand Graph to Individual File Modules',
        subtitle: 'Show all individual source files and direct import edges',
        icon: <Layers className="w-4 h-4 text-accent" aria-hidden="true" />,
        badge: 'Modules',
        onRun: () => {
          onChangeGrouping('files');
          onSwitchTab('studio');
          onClose();
        },
      },
      {
        id: 'flt-cycles',
        category: 'Graph Controls',
        title: 'Toggle Circular Dependency Filter (Cycles Only)',
        subtitle: 'Isolate modules participating in Tarjan SCC dependency cycles',
        icon: <RefreshCcw className="w-4 h-4 text-danger" aria-hidden="true" />,
        badge: 'Filter',
        onRun: () => {
          onToggleCyclesOnly();
          onSwitchTab('studio');
          onClose();
        },
      },
      {
        id: 'flt-reset',
        category: 'Graph Controls',
        title: 'Reset All Graph & Explorer Filters',
        subtitle: 'Clear search, language, cycle, hub, and neighborhood filters',
        icon: <Moon className="w-4 h-4 text-muted" aria-hidden="true" />,
        badge: 'Reset',
        onRun: () => {
          onResetFilters();
          onChangeLayout('layered');
          onChangeDensity('balanced');
          onChangeGrouping('files');
          onClose();
        },
      },
    ];

    if (onExportReport) {
      baseActions.push(
        {
          id: 'exp-json',
          category: 'Navigation & Actions',
          title: 'Export Deterministic JSON Architecture Report',
          subtitle: 'Download machine-readable JSON snapshot of current analysis',
          icon: <Download className="w-4 h-4 text-accent" aria-hidden="true" />,
          badge: 'Export',
          onRun: () => {
            onExportReport('json');
            onClose();
          },
        },
        {
          id: 'exp-html',
          category: 'Navigation & Actions',
          title: 'Export Standalone HTML Architecture Report',
          subtitle: 'Download self-contained HTML engineering report',
          icon: <Download className="w-4 h-4 text-success" aria-hidden="true" />,
          badge: 'Export',
          onRun: () => {
            onExportReport('html');
            onClose();
          },
        }
      );
    }

    const fileActions: PaletteAction[] = files.map((f) => ({
      id: `file-${f.id}`,
      category: 'Repository Modules',
      title: f.id,
      subtitle: `${f.language} • ${f.lines_code} LOC • In:${f.fan_in} Out:${f.fan_out} I=${f.instability.toFixed(2)}`,
      icon: (
        <FileCode2
          className={`w-4 h-4 ${f.in_cycle ? 'text-danger' : 'text-accent'}`}
          aria-hidden="true"
        />
      ),
      badge: f.in_cycle ? 'CYCLE' : f.is_hub ? 'HUB' : f.language,
      onRun: () => {
        onSelectFile(f.id);
        onSwitchTab('studio');
        onClose();
      },
    }));

    const q = query.trim().toLowerCase();
    if (!q) {
      return [...baseActions].sort((a, b) => (recent.includes(b.id) ? 1 : 0) - (recent.includes(a.id) ? 1 : 0)).concat(fileActions.slice(0, 25));
    }

    return [...baseActions, ...fileActions]
      .filter(
        (item) =>
          item.title.toLowerCase().includes(q) ||
          item.subtitle.toLowerCase().includes(q) ||
          (item.badge && item.badge.toLowerCase().includes(q))
      )
      .sort((a, b) => Number(b.title.toLowerCase().startsWith(q)) - Number(a.title.toLowerCase().startsWith(q)))
      .slice(0, 40);
  }, [
    files,
    query,
    recent,
    onSelectFile,
    onSwitchTab,
    onToggleTheme,
    onChangeLayout,
    onChangeGrouping,
    onChangeDensity,
    onToggleCyclesOnly,
    onResetFilters,
    onExportReport,
    onLoadDemo,
    onClose,
  ]);

  const run = (action: PaletteAction) => {
    if (!action.id.startsWith('file-')) {
      const next = [action.id, ...recent.filter(id => id !== action.id)].slice(0, 5);
      setRecent(next); savePreference('recentCommands', next);
    }
    action.onRun();
  };
  useEffect(() => {
    dialogRef.current?.querySelector(`[data-active="true"]`)?.scrollIntoView?.({ block: 'nearest' });
  }, [activeIndex]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((prev) => (actions.length > 0 ? (prev + 1) % actions.length : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((prev) =>
        actions.length > 0 ? (prev - 1 + actions.length) % actions.length : 0
      );
    } else if (e.key === 'Enter' && actions[activeIndex]) {
      e.preventDefault();
      run(actions[activeIndex]);
    }
  };

  return (
    <dialog
      ref={dialogRef}
      data-testid="command-palette-dialog"
      {...({ closedby: 'any' } as React.DialogHTMLAttributes<HTMLDialogElement>)}
      aria-labelledby="command-palette-title"

    >
      <div className="flex flex-col max-h-[75vh]">
        <div className="flex items-center gap-2.5 px-4 py-3 border-b border-line">
          <Command className="w-4 h-4 text-accent shrink-0" aria-hidden="true" />
          <h2 id="command-palette-title" className="visually-hidden">
            Command Palette and Quick Module Jump
          </h2>
          <Search className="w-4 h-4 text-muted shrink-0" aria-hidden="true" />
          <input
            ref={inputRef}
            onKeyDown={handleKeyDown}
            role="combobox" aria-expanded={isOpen} aria-controls="palette-results" aria-autocomplete="list"
            aria-activedescendant={actions[activeIndex] ? `command-option-${activeIndex}` : undefined}
            data-testid="command-palette-input"
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIndex(0);
            }}
            placeholder="Jump to module path, symbol, or run workstation command..."
            aria-label="Search commands or modules"
            className="flex-1 bg-transparent border-0 text-sm text-ink placeholder:text-muted"
          />
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            aria-label="Close command palette"
            className="p-1 rounded-lg hover:bg-raised text-muted cursor-pointer"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        <div id="palette-results" role="listbox" aria-label="Commands and modules" className="overflow-y-auto p-2 space-y-1 max-h-[55vh]">
          {actions.length === 0 ? (
            <div className="p-6 text-center text-xs text-muted">
              No matching commands or repository modules found for "{query}".
            </div>
          ) : (
            actions.map((item, idx) => {
              const isSelected = idx === activeIndex;
              return (
                <React.Fragment key={item.id}>
                {(idx === 0 || actions[idx - 1].category !== item.category) && <div role="presentation" className="command-group">{item.category}</div>}
                <button
                  id={`command-option-${idx}`} role="option" aria-selected={isSelected} data-active={isSelected} tabIndex={-1}
                  type="button"
                  data-testid={`palette-item-${item.id}`}
                  onClick={() => run(item)}
                  onMouseEnter={() => setActiveIndex(idx)}
                  className={`w-full px-3 py-2 rounded-lg text-left flex items-center justify-between gap-3 transition cursor-pointer ${
                    isSelected
                      ? 'bg-accent/20 border border-accent/40 text-ink'
                      : 'hover:bg-raised border border-transparent text-muted'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    {item.icon}
                    <div className="min-w-0">
                      <div className="text-xs font-semibold font-mono truncate">{item.title}</div>
                      <div className="text-[11px] text-muted truncate">{item.subtitle}</div>
                    </div>
                  </div>
                  {item.badge && (
                    <span className="text-[11px] font-mono uppercase px-2 py-0.5 rounded bg-panel border border-line text-accent shrink-0">
                      {recent.includes(item.id) && !query ? 'Recent' : item.badge}
                    </span>
                  )}
                </button>
                </React.Fragment>
              );
            })
          )}
        </div>

        <div className="px-4 py-2 border-t border-line bg-panel flex items-center justify-between text-[11px] text-muted">
          <span>
            Use <kbd className="px-1.5 py-0.5 rounded bg-raised text-ink font-mono">↑</kbd>{' '}
            <kbd className="px-1.5 py-0.5 rounded bg-raised text-ink font-mono">↓</kbd> to
            navigate, <kbd className="px-1.5 py-0.5 rounded bg-raised text-ink font-mono">Enter</kbd> to select
          </span>
          <span>
            <kbd className="px-1.5 py-0.5 rounded bg-raised text-ink font-mono">Esc</kbd> to dismiss
          </span>
        </div>
      </div>
    </dialog>
  );
};
