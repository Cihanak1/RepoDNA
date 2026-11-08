import React, { useEffect, useRef, useState } from 'react';
import { CornerLeftUp, Folder, FolderGit2, X } from 'lucide-react';
import { browseDirectories } from '../api/client';
import type { DirectoryBrowseResponse } from '../types/repodna';

interface FolderBrowserDialogProps {
  isOpen: boolean;
  initialPath: string;
  onClose: () => void;
  onSelectFolder: (selectedPath: string) => void;
}

export const FolderBrowserDialog: React.FC<FolderBrowserDialogProps> = ({
  isOpen,
  initialPath,
  onClose,
  onSelectFolder,
}) => {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const [browseData, setBrowseData] = useState<DirectoryBrowseResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (isOpen && !dialog.open) {
      dialog.showModal();
      void loadDirectory(initialPath || undefined);
    } else if (!isOpen && dialog.open) {
      dialog.close();
    }
  }, [isOpen, initialPath]);

  // Fallback for browsers that do not yet support declarative closedby="any"
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const handleClose = () => {
      dialog.returnValue = '';
      onClose();
    };
    dialog.addEventListener('close', handleClose);

    let handleBackdropClick: ((event: MouseEvent) => void) | null = null;
    if (!('closedBy' in HTMLDialogElement.prototype)) {
      handleBackdropClick = (event: MouseEvent) => {
        if (event.target !== dialog) return;
        const rect = dialog.getBoundingClientRect();
        const isDialogContent =
          rect.top <= event.clientY &&
          event.clientY <= rect.top + rect.height &&
          rect.left <= event.clientX &&
          event.clientX <= rect.left + rect.width;
        if (isDialogContent) return;
        dialog.close();
      };
      dialog.addEventListener('click', handleBackdropClick);
    }

    return () => {
      dialog.removeEventListener('close', handleClose);
      if (handleBackdropClick) {
        dialog.removeEventListener('click', handleBackdropClick);
      }
    };
  }, [onClose]);

  async function loadDirectory(targetPath?: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await browseDirectories(targetPath);
      setBrowseData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to list directory');
    } finally {
      setLoading(false);
    }
  }

  return (
    <dialog
      ref={dialogRef}
      {...({ closedby: 'any' } as React.DialogHTMLAttributes<HTMLDialogElement>)}
      aria-labelledby="folder-dialog-title"
    >
      <div className="p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between border-b border-line pb-3">
          <h2 id="folder-dialog-title" className="text-base font-semibold flex items-center gap-2 m-0">
            <Folder className="w-5 h-5 text-accent" aria-hidden="true" />
            Select Local Repository Directory
          </h2>
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            aria-label="Close folder browser"
            className="p-1.5 rounded-lg hover:bg-raised text-muted hover:text-ink cursor-pointer"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        <p className="text-xs text-muted m-0">
          RepoDNA never scans files until you explicitly confirm and click <strong>Analyze Repository</strong>.
        </p>

        {browseData && (
          <div className="flex items-center justify-between gap-2 bg-panel border border-line rounded-lg px-3 py-2 text-xs font-mono">
            <span className="truncate" title={browseData.current_path}>
              {browseData.current_path}
            </span>
            {browseData.parent_path && (
              <button
                type="button"
                onClick={() => void loadDirectory(browseData.parent_path!)}
                className="flex items-center gap-1 px-2 py-1 rounded bg-raised hover:bg-raised text-ink shrink-0 cursor-pointer"
              >
                <CornerLeftUp className="w-3.5 h-3.5" aria-hidden="true" />
                Up
              </button>
            )}
          </div>
        )}

        {error && (
          <div role="alert" className="text-xs text-danger bg-danger/10 border border-danger/60 rounded-lg p-3">
            {error}
          </div>
        )}

        <div className="max-h-64 overflow-y-auto border border-line rounded-lg divide-y divide-line">
          {loading ? (
            <div className="p-6 text-center text-xs text-muted">Loading subdirectories...</div>
          ) : browseData && browseData.directories.length > 0 ? (
            browseData.directories.map((dir) => (
              <div
                key={dir.path}
                className="flex items-center justify-between px-3 py-2 hover:bg-raised text-xs"
              >
                <button
                  type="button"
                  onClick={() => void loadDirectory(dir.path)}
                  className="flex items-center gap-2 text-left font-medium hover:text-accent truncate flex-1 cursor-pointer"
                >
                  {dir.is_git_repo ? (
                    <FolderGit2 className="w-4 h-4 text-success shrink-0" aria-hidden="true" />
                  ) : (
                    <Folder className="w-4 h-4 text-muted shrink-0" aria-hidden="true" />
                  )}
                  <span className="truncate">{dir.name}</span>
                  {dir.is_git_repo && (
                    <span className="text-[11px] px-1.5 py-0.5 rounded bg-success/15 text-success border border-success/30">
                      .git
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onSelectFolder(dir.path);
                    dialogRef.current?.close();
                  }}
                  aria-label={`Select folder ${dir.name}`}
                  className="px-2.5 py-1 rounded bg-accent/20 hover:bg-accent/30 text-accent border border-accent/30 text-xs font-medium cursor-pointer"
                >
                  Select
                </button>
              </div>
            ))
          ) : (
            <div className="p-6 text-center text-xs text-muted">No subdirectories found in this folder.</div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-line">
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            className="px-3 py-1.5 rounded-lg border border-line text-xs hover:bg-raised cursor-pointer"
          >
            Cancel
          </button>
          {browseData && (
            <button
              type="button"
              onClick={() => {
                onSelectFolder(browseData.current_path);
                dialogRef.current?.close();
              }}
              className="px-4 py-1.5 rounded-lg bg-accent-solid hover:bg-accent-solid text-white text-xs font-semibold cursor-pointer"
            >
              Use Current Folder
            </button>
          )}
        </div>
      </div>
    </dialog>
  );
};
