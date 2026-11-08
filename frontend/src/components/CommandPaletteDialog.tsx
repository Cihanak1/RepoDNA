import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Command,
  Compass,
  Download,
  FileCode2,
  FolderTree,
  Languages,
  Layers,
  RefreshCcw,
  ShieldCheck,
  Sliders,
  SlidersHorizontal,
  Sparkles,
  Sun,
  X,
} from 'lucide-react';
import { readPreference, savePreference, type WorkstationMode } from '../utils/preferences';
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
  workstationMode?: WorkstationMode;
  onToggleMode?: () => void;
  onToggleLanguage?: () => void;
  onOpenTour?: () => void;
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
  workstationMode = 'simple',
  onToggleMode,
  onToggleLanguage,
  onOpenTour,
}) => {
  const { i18n } = useTranslation();
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [recent, setRecent] = useState(() =>
    readPreference<string[]>('recentCommands', [], (v): v is string[] =>
      Array.isArray(v) && v.every((item) => typeof item === 'string')
    )
  );
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
      window.requestAnimationFrame(() => {
        const trigger = document.querySelector<HTMLElement>('[data-testid="open-command-palette-btn"]');
        trigger?.focus();
      });
    }
  }, [isOpen]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const handleClose = () => {
      if (dialog.open) return;
      dialog.returnValue = '';
      onClose();
      window.requestAnimationFrame(() => {
        const trigger = document.querySelector<HTMLElement>('[data-testid="open-command-palette-btn"]');
        trigger?.focus();
      });
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
        id: 'act-mode',
        category: 'Navigation & Actions',
        title: 'Toggle Simple / Advanced Workstation Mode',
        subtitle: `Currently in ${workstationMode} mode. Toggle cognitive simplification.`,
        icon: <Sliders className="w-4 h-4 text-accent" aria-hidden="true" />,
        badge: 'Mode',
        onRun: () => {
          onToggleMode?.();
          onClose();
        },
      },
      {
        id: 'act-lang',
        category: 'Navigation & Actions',
        title: 'Switch Language (Türkçe / English)',
        subtitle: `Currently ${i18n.language.startsWith('tr') ? 'Türkçe' : 'English'}. Toggle interface language.`,
        icon: <Languages className="w-4 h-4 text-accent" aria-hidden="true" />,
        badge: 'Lang',
        onRun: () => {
          onToggleLanguage?.();
          onClose();
        },
      },
      {
        id: 'act-tour',
        category: 'Navigation & Actions',
        title: 'Open RepoDNA Quick Guide',
        subtitle: 'Step-by-step introduction to repository analysis',
        icon: <Compass className="w-4 h-4 text-accent" aria-hidden="true" />,
        badge: 'Guide',
        onRun: () => {
          onOpenTour?.();
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
        id: 'layout-layered',
        category: 'Graph Controls',
        title: 'Switch to Hierarchical Layered Graph Layout',
        subtitle: 'Daguerre-style vertical flow showing top-level callers to bottom-level leaves',
        icon: <Layers className="w-4 h-4 text-accent" aria-hidden="true" />,
        badge: 'Layout',
        onRun: () => {
          onChangeLayout('layered');
          onSwitchTab('studio');
          onClose();
        },
      },
      {
        id: 'density-compact',
        category: 'Graph Controls',
        title: 'Set Graph Density to Compact',
        subtitle: 'Minimal spacing to view more nodes on screen',
        icon: <SlidersHorizontal className="w-4 h-4 text-muted" aria-hidden="true" />,
        badge: 'Density',
        onRun: () => {
          onChangeDensity('compact');
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
        icon: <RefreshCcw className="w-4 h-4 text-muted" aria-hidden="true" />,
        badge: 'Reset',
        onRun: () => {
          onResetFilters();
          onClose();
        },
      },
      {
        id: 'exp-json',
        category: 'Navigation & Actions',
        title: 'Export Machine-Readable Analysis JSON',
        subtitle: 'Full dependency graph, SCC cycles, and health findings dump',
        icon: <Download className="w-4 h-4 text-accent" aria-hidden="true" />,
        badge: 'Export',
        onRun: () => {
          onExportReport?.('json');
          onClose();
        },
      },
      {
        id: 'exp-html',
        category: 'Navigation & Actions',
        title: 'Export Standalone HTML Health Report',
        subtitle: 'Self-contained architectural health document with remediation evidence',
        icon: <Download className="w-4 h-4 text-success" aria-hidden="true" />,
        badge: 'Export',
        onRun: () => {
          onExportReport?.('html');
          onClose();
        },
      },
    ];

    const fileActions: PaletteAction[] = files.slice(0, 100).map((file) => ({
      id: `file-${file.id}`,
      category: 'Repository Modules',
      title: file.id,
      subtitle: `${file.language} · ${file.lines_code} LOC · ${file.support_level}${
        file.in_cycle ? ' · IN CYCLE' : ''
      }`,
      icon: (
        <span
          className={`w-2 h-2 rounded-full ${
            file.in_cycle ? 'bg-danger' : 'bg-accent'
          }`}
          aria-hidden="true"
        />
      ),
      badge: file.language,
      onRun: () => {
        onSelectFile(file.id);
        onSwitchTab('studio');
        onClose();
      },
    }));

    return [...baseActions, ...fileActions];
  }, [
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
    onToggleMode,
    onToggleLanguage,
    onOpenTour,
    workstationMode,
    i18n.language,
    onClose,
  ]);

  const filteredActions = useMemo(() => {
    const q = query.trim().toLowerCase();
    const map = new Map(actions.map((act) => [act.id, act]));

    if (!q) {
      const recentActions = recent
        .map((id) => map.get(id))
        .filter((act): act is PaletteAction => Boolean(act))
        .map((act) => ({ ...act, category: 'Navigation & Actions' as const, isRecent: true }));
      const remaining = actions.filter((act) => !recent.includes(act.id));
      return [...recentActions, ...remaining];
    }

    return actions
      .filter((act) => {
        const titleMatch = act.title.toLowerCase().includes(q);
        const subMatch = act.subtitle.toLowerCase().includes(q);
        const idMatch = act.id.toLowerCase().includes(q);
        return titleMatch || subMatch || idMatch;
      })
      .sort((a, b) => {
        const aTitle = a.title.toLowerCase();
        const bTitle = b.title.toLowerCase();
        if (aTitle.startsWith(q) && !bTitle.startsWith(q)) return -1;
        if (!aTitle.startsWith(q) && bTitle.startsWith(q)) return 1;
        return 0;
      });
  }, [actions, query, recent]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  const handleSelectAction = (act: PaletteAction) => {
    setRecent((prev) => {
      const updated = [act.id, ...prev.filter((id) => id !== act.id)].slice(0, 5);
      savePreference('recentCommands', updated);
      return updated;
    });
    dialogRef.current?.close();
    onClose();
    act.onRun();
    window.setTimeout(() => {
      const trigger = document.querySelector<HTMLElement>('[data-testid="open-command-palette-btn"]');
      trigger?.focus();
    }, 50);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((prev) => (prev < filteredActions.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((prev) => (prev > 0 ? prev - 1 : filteredActions.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredActions[activeIndex]) {
        handleSelectAction(filteredActions[activeIndex]);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <dialog
      ref={dialogRef}
      aria-label="Command Palette"
      data-testid="command-palette-dialog"
      className="backdrop:bg-black/60 rounded-xl bg-canvas border border-line p-0 text-ink max-w-xl w-full shadow-2xl overflow-hidden m-auto"
    >
      <div className="flex flex-col max-h-[75vh]">
        {/* Search Input */}
        <div className="p-3 border-b border-line flex items-center gap-2.5 bg-panel">
          <Command className="w-4 h-4 text-accent shrink-0" aria-hidden="true" />
          <input
            ref={inputRef}
            data-testid="command-palette-input"
            type="text"
            role="combobox"
            aria-expanded={filteredActions.length > 0}
            aria-controls="command-palette-list"
            aria-activedescendant={
              filteredActions[activeIndex] ? `command-option-${activeIndex}` : undefined
            }
            aria-label="Search commands or modules"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command, action, or module path... (Esc to close)"
            className="flex-1 bg-transparent border-0 text-sm font-medium text-ink placeholder:text-muted focus:outline-none"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="p-1 rounded text-muted hover:text-ink cursor-pointer"
            >
              <X className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          )}
        </div>

        {/* Action List */}
        <div
          id="command-palette-list"
          role="listbox"
          tabIndex={-1}
          className="flex-1 overflow-y-auto p-2 space-y-1 text-xs"
        >
          {filteredActions.length === 0 ? (
            <div className="p-8 text-center text-muted">
              No matching commands or modules found.
            </div>
          ) : (
            filteredActions.map((act, idx) => {
              const isSelected = idx === activeIndex;
              const isRecent = !query && recent.includes(act.id);
              return (
                <div
                  key={`${act.id}-${idx}`}
                  id={`command-option-${idx}`}
                  role="option"
                  aria-selected={isSelected}
                  onMouseEnter={() => setActiveIndex(idx)}
                  onClick={() => handleSelectAction(act)}
                  className={`p-2.5 rounded-lg flex items-center justify-between gap-3 cursor-pointer transition ${
                    isSelected ? 'bg-accent/15 border border-accent/40' : 'hover:bg-raised'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="p-1.5 rounded bg-panel border border-line shrink-0">
                      {act.icon}
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-ink flex items-center gap-1.5 truncate">
                        {isRecent && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-accent/20 text-accent font-bold uppercase">
                            Recent
                          </span>
                        )}
                        <span className="truncate">{act.title}</span>
                      </div>
                      <div className="text-[11px] text-muted truncate mt-0.5 font-mono">
                        {act.subtitle}
                      </div>
                    </div>
                  </div>
                  {act.badge && (
                    <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-panel border border-line text-muted uppercase shrink-0">
                      {act.badge}
                    </span>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer shortcuts */}
        <div className="px-3 py-2 border-t border-line bg-panel flex items-center justify-between text-[11px] text-muted">
          <div className="flex items-center gap-3">
            <span>
              <kbd className="px-1 py-0.5 rounded bg-raised border border-line font-mono">&uarr;</kbd>{' '}
              <kbd className="px-1 py-0.5 rounded bg-raised border border-line font-mono">&darr;</kbd>{' '}
              to navigate
            </span>
            <span>
              <kbd className="px-1.5 py-0.5 rounded bg-raised border border-line font-mono">Enter</kbd>{' '}
              to select
            </span>
          </div>
          <span>
            <kbd className="px-1.5 py-0.5 rounded bg-raised border border-line font-mono">Esc</kbd>{' '}
            to close
          </span>
        </div>
      </div>
    </dialog>
  );
};
