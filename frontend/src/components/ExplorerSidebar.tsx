import React, { useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  FileCode,
  Filter,
  Folder,
  RefreshCcw,
  Search,
  Sparkles,
  Unlink,
} from 'lucide-react';
import type { FileNode } from '../types/repodna';

interface ExplorerSidebarProps {
  allFiles: FileNode[];
  filteredFiles: FileNode[];
  selectedFileId: string | null;
  onSelectFile: (fileId: string) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  languageFilter: string;
  onLanguageFilterChange: (lang: string) => void;
  supportFilter: string;
  onSupportFilterChange: (sup: string) => void;
  cyclesOnly: boolean;
  onCyclesOnlyChange: (v: boolean) => void;
  hubsOnly: boolean;
  onHubsOnlyChange: (v: boolean) => void;
  orphansOnly: boolean;
  onOrphansOnlyChange: (v: boolean) => void;
  onResetFilters: () => void;
}

export const ExplorerSidebar: React.FC<ExplorerSidebarProps> = ({
  allFiles,
  filteredFiles,
  selectedFileId,
  onSelectFile,
  searchQuery,
  onSearchChange,
  languageFilter,
  onLanguageFilterChange,
  supportFilter,
  onSupportFilterChange,
  cyclesOnly,
  onCyclesOnlyChange,
  hubsOnly,
  onHubsOnlyChange,
  orphansOnly,
  onOrphansOnlyChange,
  onResetFilters,
}) => {
  const [collapsedDirs, setCollapsedDirs] = useState<Set<string>>(new Set());

  const uniqueLanguages = useMemo(() => {
    const s = new Set<string>();
    for (const f of allFiles) s.add(f.language);
    return Array.from(s).sort();
  }, [allFiles]);

  const groupedByDirectory = useMemo(() => {
    const map = new Map<string, FileNode[]>();
    for (const f of filteredFiles) {
      const dir = f.directory || '(root)';
      const list = map.get(dir) ?? [];
      list.push(f);
      map.set(dir, list);
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [filteredFiles]);

  const toggleDir = (dir: string) => {
    setCollapsedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(dir)) next.delete(dir);
      else next.add(dir);
      return next;
    });
  };

  const hasActiveFilters =
    searchQuery.trim() !== '' ||
    languageFilter !== 'ALL' ||
    supportFilter !== 'ALL' ||
    cyclesOnly ||
    hubsOnly ||
    orphansOnly;

  return (
    <aside
      aria-label="Repository Explorer and Filters"
      className="w-full lg:w-80 shrink-0 border-b lg:border-b-0 lg:border-r border-slate-800/80 bg-slate-950/60 flex flex-col max-h-[38vh] lg:max-h-none"
    >
      {/* Search & Filters Header */}
      <div className="p-3 border-b border-slate-800/80 flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-300 m-0 flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-sky-400" aria-hidden="true" />
            Explorer ({filteredFiles.length}/{allFiles.length})
          </h2>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={onResetFilters}
              className="text-[11px] text-sky-400 hover:text-sky-300 font-medium cursor-pointer"
            >
              Reset filters
            </button>
          )}
        </div>

        {/* Search Input */}
        <div className="relative">
          <label htmlFor="explorer-search-input" className="visually-hidden">
            Filter modules by path or symbol name
          </label>
          <Search
            className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
            aria-hidden="true"
          />
          <input
            id="explorer-search-input"
            type="search"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search file path or symbol..."
            className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-2.5 py-1.5 text-xs text-slate-100 placeholder:text-slate-500"
          />
        </div>

        {/* Language & Support Dropdowns */}
        <div className="grid grid-cols-2 gap-1.5 text-xs">
          <div>
            <label htmlFor="filter-language-select" className="visually-hidden">
              Filter by Language
            </label>
            <select
              id="filter-language-select"
              value={languageFilter}
              onChange={(e) => onLanguageFilterChange(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-200"
            >
              <option value="ALL">All Languages</option>
              {uniqueLanguages.map((lang) => (
                <option key={lang} value={lang}>
                  {lang}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="filter-support-select" className="visually-hidden">
              Filter by AST Support Level
            </label>
            <select
              id="filter-support-select"
              value={supportFilter}
              onChange={(e) => onSupportFilterChange(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-200"
            >
              <option value="ALL">All Support Levels</option>
              <option value="full_ast">Full AST Only</option>
              <option value="partial_static">Partial Static</option>
              <option value="unsupported">Unsupported Only</option>
            </select>
          </div>
        </div>

        {/* Quick Toggle Chips */}
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => onCyclesOnlyChange(!cyclesOnly)}
            aria-pressed={cyclesOnly}
            className={`px-2 py-1 rounded-md text-[11px] font-medium flex items-center gap-1 border cursor-pointer ${
              cyclesOnly
                ? 'bg-red-500/20 text-red-300 border-red-500/50'
                : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
            }`}
          >
            <RefreshCcw className="w-3 h-3" aria-hidden="true" />
            In Cycle
          </button>

          <button
            type="button"
            onClick={() => onHubsOnlyChange(!hubsOnly)}
            aria-pressed={hubsOnly}
            className={`px-2 py-1 rounded-md text-[11px] font-medium flex items-center gap-1 border cursor-pointer ${
              hubsOnly
                ? 'bg-sky-500/20 text-sky-300 border-sky-500/50'
                : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
            }`}
          >
            <Sparkles className="w-3 h-3" aria-hidden="true" />
            Hubs
          </button>

          <button
            type="button"
            onClick={() => onOrphansOnlyChange(!orphansOnly)}
            aria-pressed={orphansOnly}
            className={`px-2 py-1 rounded-md text-[11px] font-medium flex items-center gap-1 border cursor-pointer ${
              orphansOnly
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/50'
                : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
            }`}
          >
            <Unlink className="w-3 h-3" aria-hidden="true" />
            Orphans
          </button>
        </div>
      </div>

      {/* Hierarchical Directory & File Tree */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {groupedByDirectory.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-400">
            No modules match the active filters.
          </div>
        ) : (
          groupedByDirectory.map(([dirName, files]) => {
            const isCollapsed = collapsedDirs.has(dirName);
            return (
              <div key={dirName} className="virtual-panel-section rounded-lg border border-slate-900/80 bg-slate-900/30">
                <button
                  type="button"
                  onClick={() => toggleDir(dirName)}
                  aria-expanded={!isCollapsed}
                  className="w-full px-2.5 py-1.5 flex items-center justify-between text-xs font-semibold text-slate-300 hover:bg-slate-800/50 rounded-t-lg cursor-pointer"
                >
                  <span className="flex items-center gap-1.5 truncate">
                    {isCollapsed ? (
                      <ChevronRight className="w-3.5 h-3.5 text-slate-500 shrink-0" aria-hidden="true" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5 text-slate-500 shrink-0" aria-hidden="true" />
                    )}
                    <Folder className="w-3.5 h-3.5 text-sky-400/80 shrink-0" aria-hidden="true" />
                    <span className="truncate font-mono text-[11px]">{dirName}</span>
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 px-1.5 py-0.5 rounded bg-slate-900">
                    {files.length}
                  </span>
                </button>

                {!isCollapsed && (
                  <ul role="list" className="m-0 p-1 space-y-0.5 list-none">
                    {files.map((file) => {
                      const isSelected = file.id === selectedFileId;
                      return (
                        <li key={file.id}>
                          <button
                            type="button"
                            data-testid={`explorer-file-${file.id}`}
                            onClick={() => onSelectFile(file.id)}
                            aria-current={isSelected ? 'true' : undefined}
                            className={`w-full px-2.5 py-1.5 rounded-md text-left text-xs flex items-center justify-between gap-2 transition cursor-pointer ${
                              isSelected
                                ? 'bg-sky-500/20 text-sky-200 border border-sky-500/40 font-semibold'
                                : 'text-slate-300 hover:bg-slate-800/60 border border-transparent'
                            }`}
                          >
                            <span className="flex items-center gap-1.5 truncate">
                              <FileCode
                                className={`w-3.5 h-3.5 shrink-0 ${
                                  file.in_cycle
                                    ? 'text-red-400'
                                    : file.support_level === 'unsupported'
                                    ? 'text-amber-400'
                                    : 'text-sky-400'
                                }`}
                                aria-hidden="true"
                              />
                              <span className="truncate font-mono text-[11px]">{file.name}</span>
                            </span>

                            <span className="flex items-center gap-1 shrink-0">
                              {file.in_cycle && (
                                <span
                                  title="Participates in circular dependency"
                                  className="px-1.5 py-0.2 rounded text-[9px] font-bold uppercase bg-red-500/25 text-red-300 border border-red-500/40"
                                >
                                  Cycle
                                </span>
                              )}
                              <span className="text-[10px] font-mono text-slate-400">
                                {file.lines_code}L
                              </span>
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
