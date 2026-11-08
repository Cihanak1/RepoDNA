import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
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
      className="w-full lg:w-80 shrink-0 border-b lg:border-b-0 lg:border-r border-line bg-canvas flex flex-col max-h-[38vh] lg:max-h-none"
    >
      {/* Search & Filters Header */}
      <div className="p-3 border-b border-line flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold tracking-wide text-muted m-0 flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-accent" aria-hidden="true" />
            {t('explorer.title')} ({filteredFiles.length}/{allFiles.length})
          </h2>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={onResetFilters}
              className="text-[11px] text-accent hover:underline font-medium cursor-pointer"
            >
              {t('explorer.clearFilters')}
            </button>
          )}
        </div>

        {/* Search Input */}
        <div className="relative">
          <label htmlFor="explorer-search-input" className="visually-hidden">
            Filter modules by path or symbol name
          </label>
          <Search
            className="w-3.5 h-3.5 text-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
            aria-hidden="true"
          />
          <input
            id="explorer-search-input"
            type="search"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={t('explorer.searchPlaceholder')}
            className="w-full bg-panel border border-line rounded-lg pl-8 pr-2.5 py-1.5 text-xs text-ink placeholder:text-muted"
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
              className="w-full bg-panel border border-line rounded-lg px-2 py-1 text-xs text-ink"
            >
              <option value="ALL">{t('explorer.allLanguages')}</option>
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
              className="w-full bg-panel border border-line rounded-lg px-2 py-1 text-xs text-ink"
            >
              <option value="ALL">{t('explorer.allSupport')}</option>
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
                ? 'bg-danger/20 text-danger border-danger/50'
                : 'bg-panel text-muted border-line hover:text-ink'
            }`}
          >
            <RefreshCcw className="w-3 h-3" aria-hidden="true" />
            {t('explorer.inCycleFilter')}
          </button>

          <button
            type="button"
            onClick={() => onHubsOnlyChange(!hubsOnly)}
            aria-pressed={hubsOnly}
            className={`px-2 py-1 rounded-md text-[11px] font-medium flex items-center gap-1 border cursor-pointer ${
              hubsOnly
                ? 'bg-accent/20 text-accent border-accent/50'
                : 'bg-panel text-muted border-line hover:text-ink'
            }`}
          >
            <Sparkles className="w-3 h-3" aria-hidden="true" />
            {t('explorer.hubsFilter')}
          </button>

          <button
            type="button"
            onClick={() => onOrphansOnlyChange(!orphansOnly)}
            aria-pressed={orphansOnly}
            className={`px-2 py-1 rounded-md text-[11px] font-medium flex items-center gap-1 border cursor-pointer ${
              orphansOnly
                ? 'bg-warning/20 text-warning border-warning/50'
                : 'bg-panel text-muted border-line hover:text-ink'
            }`}
          >
            <Unlink className="w-3 h-3" aria-hidden="true" />
            {t('explorer.orphansFilter')}
          </button>
        </div>
      </div>

      {/* Directory & File Tree */}
      <div
        tabIndex={0}
        role="region"
        aria-label="Files list"
        className="flex-1 overflow-y-auto p-2 space-y-1 text-xs"
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            const buttons = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>('[data-testid^="explorer-file-"]'));
            if (!buttons.length) return;
            const idx = buttons.indexOf(document.activeElement as HTMLButtonElement);
            e.preventDefault();
            if (e.key === 'ArrowDown') {
              const next = idx < buttons.length - 1 ? buttons[idx + 1] : buttons[0];
              next?.focus();
            } else {
              const prev = idx > 0 ? buttons[idx - 1] : buttons[buttons.length - 1];
              prev?.focus();
            }
          }
        }}
      >
        {groupedByDirectory.length === 0 ? (
          <div className="p-4 text-center text-muted text-xs">
            {t('explorer.noResults')}
          </div>
        ) : (
          groupedByDirectory.map(([dir, files]) => {
            const isCollapsed = collapsedDirs.has(dir);
            return (
              <div key={dir} className="explorer-directory">
                <button
                  type="button"
                  onClick={() => toggleDir(dir)}
                  className="w-full flex items-center justify-between px-2 py-1.5 rounded-md hover:bg-raised text-muted text-xs font-medium cursor-pointer"
                  aria-expanded={!isCollapsed}
                >
                  <div className="flex items-center gap-1.5 truncate">
                    {isCollapsed ? (
                      <ChevronRight className="w-3.5 h-3.5 text-muted shrink-0" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5 text-muted shrink-0" />
                    )}
                    <Folder className="w-3.5 h-3.5 text-accent shrink-0" />
                    <span className="font-mono text-ink truncate">{dir}</span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-canvas border border-line text-muted">
                    {files.length}
                  </span>
                </button>

                {!isCollapsed && (
                  <div className="pl-4 space-y-0.5 mt-0.5">
                    {files.map((file) => {
                      const isSelected = selectedFileId === file.id;
                      const hasCycle = file.in_cycle;
                      return (
                        <button
                          key={file.id}
                          type="button"
                          data-testid={`explorer-file-${file.id}`}
                          onClick={() => onSelectFile(file.id)}
                          className={`w-full flex items-center justify-between px-2 py-1 rounded-md text-left font-mono text-[11px] cursor-pointer transition ${
                            isSelected
                              ? 'bg-accent/20 text-accent font-semibold border border-accent/40'
                              : 'text-ink hover:bg-raised border border-transparent'
                          }`}
                          title={`${file.id} (${file.lines_code} LOC, ${file.language})`}
                        >
                          <div className="flex items-center gap-1.5 truncate min-w-0">
                            <FileCode
                              className={`w-3 h-3 shrink-0 ${
                                hasCycle ? 'text-danger' : isSelected ? 'text-accent' : 'text-muted'
                              }`}
                            />
                            <span className="truncate">
                              {searchQuery && file.name.toLowerCase().includes(searchQuery.toLowerCase()) ? (
                                <>
                                  {file.name.slice(0, file.name.toLowerCase().indexOf(searchQuery.toLowerCase()))}
                                  <mark>{file.name.slice(file.name.toLowerCase().indexOf(searchQuery.toLowerCase()), file.name.toLowerCase().indexOf(searchQuery.toLowerCase()) + searchQuery.length)}</mark>
                                  {file.name.slice(file.name.toLowerCase().indexOf(searchQuery.toLowerCase()) + searchQuery.length)}
                                </>
                              ) : (
                                file.name
                              )}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0 ml-1">
                            {hasCycle && (
                              <span className="text-[9px] px-1 py-0.2 rounded bg-danger/20 text-danger border border-danger/40 font-sans font-bold">
                                CYCLE
                              </span>
                            )}
                            <span className="text-[10px] text-muted">{file.lines_code}L</span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
