import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from '../App';
import { fetchJobResultWithRetry } from '../api/client';
import { buildFlowElements, filterFiles } from '../utils/graphLayout';
import type { DependencyEdge, FileNode } from '../types/repodna';

const sampleFiles: FileNode[] = [
  {
    id: 'src/api.py',
    name: 'api.py',
    directory: 'src',
    extension: '.py',
    language: 'Python',
    support_level: 'full_ast',
    size_bytes: 1200,
    lines_total: 50,
    lines_code: 40,
    lines_comment: 5,
    lines_blank: 5,
    imports_internal: ['src/service.py'],
    imported_by: [],
    imports_external: ['fastapi'],
    unresolved_imports: [],
    symbols: [{ name: 'create_app', kind: 'function', line: 10 }],
    fan_in: 0,
    fan_out: 1,
    instability: 1.0,
    in_cycle: false,
    cycle_ids: [],
    is_orphan: false,
    is_hub: false,
    git_commits: 5,
    secret_warnings: [],
  },
  {
    id: 'src/service.py',
    name: 'service.py',
    directory: 'src',
    extension: '.py',
    language: 'Python',
    support_level: 'full_ast',
    size_bytes: 2400,
    lines_total: 90,
    lines_code: 75,
    lines_comment: 5,
    lines_blank: 10,
    imports_internal: ['src/billing.py'],
    imported_by: ['src/api.py', 'src/billing.py'],
    imports_external: [],
    unresolved_imports: [],
    symbols: [{ name: 'OrderService', kind: 'class', line: 8 }],
    fan_in: 2,
    fan_out: 1,
    instability: 0.33,
    in_cycle: true,
    cycle_ids: ['CYCLE-001'],
    is_orphan: false,
    is_hub: true,
    git_commits: 12,
    secret_warnings: [],
  },
  {
    id: 'src/billing.py',
    name: 'billing.py',
    directory: 'src',
    extension: '.py',
    language: 'Python',
    support_level: 'full_ast',
    size_bytes: 1800,
    lines_total: 60,
    lines_code: 50,
    lines_comment: 5,
    lines_blank: 5,
    imports_internal: ['src/service.py'],
    imported_by: ['src/service.py'],
    imports_external: [],
    unresolved_imports: [],
    symbols: [],
    fan_in: 1,
    fan_out: 1,
    instability: 0.5,
    in_cycle: true,
    cycle_ids: ['CYCLE-001'],
    is_orphan: false,
    is_hub: false,
    git_commits: 8,
    secret_warnings: [],
  },
];

const sampleEdges: DependencyEdge[] = [
  {
    id: 'src/api.py->src/service.py',
    source: 'src/api.py',
    target: 'src/service.py',
    import_names: ['OrderService'],
    line: 3,
    in_cycle: false,
  },
  {
    id: 'src/service.py->src/billing.py',
    source: 'src/service.py',
    target: 'src/billing.py',
    import_names: ['charge'],
    line: 5,
    in_cycle: true,
  },
  {
    id: 'src/billing.py->src/service.py',
    source: 'src/billing.py',
    target: 'src/service.py',
    import_names: ['OrderService'],
    line: 6,
    in_cycle: true,
  },
];

describe('graphLayout utilities', () => {
  it('keeps compact nodes and large directory groups from overlapping', () => {
    const files = Array.from({ length: 30 }, (_, index) => ({ ...sampleFiles[0], id: `group${index < 20 ? 1 : index}/file${index}.py`, directory: `group${index < 20 ? 1 : index}` }));
    for (const mode of ['layered', 'cluster'] as const) {
      const { nodes } = buildFlowElements(files, [], mode, null, new Set(), true, 'compact', 'files');
      for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i].position, b = nodes[j].position;
        expect(Math.abs(a.x - b.x) >= 256 || Math.abs(a.y - b.y) >= 100).toBe(true);
      }
    }
  });

  it('does not present a mixed-support package as fully AST analyzed', () => {
    const files = [sampleFiles[0], { ...sampleFiles[1], support_level: 'partial_static' as const }];
    const { nodes } = buildFlowElements(files, [], 'layered', sampleFiles[0].id, new Set(), true, 'balanced', 'directories');
    expect(nodes[0].data.file.support_level).toBe('partial_static');
    expect(nodes[0]).toMatchObject({ width: 256, height: 100 });
  });
  it('filters by cycle participation and symbol search', () => {
    const cycleRes = filterFiles(sampleFiles, sampleEdges, {
      searchQuery: '',
      languageFilter: 'ALL',
      supportFilter: 'ALL',
      cyclesOnly: true,
      hubsOnly: false,
      orphansOnly: false,
      focusSelectedNeighborhood: false,
      selectedFileId: null,
      highlightCycles: true,
    });
    expect(cycleRes.filteredFiles.map((f) => f.id)).toEqual(['src/service.py', 'src/billing.py']);
    expect(cycleRes.filteredEdges.length).toBe(2);

    const symRes = filterFiles(sampleFiles, sampleEdges, {
      searchQuery: 'create_app',
      languageFilter: 'ALL',
      supportFilter: 'ALL',
      cyclesOnly: false,
      hubsOnly: false,
      orphansOnly: false,
      focusSelectedNeighborhood: false,
      selectedFileId: null,
      highlightCycles: true,
    });
    expect(symRes.filteredFiles.map((f) => f.id)).toEqual(['src/api.py']);
  });

  it('builds deterministic coordinates for layered, cluster, and radial layouts', () => {
    for (const mode of ['layered', 'cluster', 'radial'] as const) {
      const { nodes, edges } = buildFlowElements(
        sampleFiles,
        sampleEdges,
        mode,
        'src/service.py',
        new Set(['src/api.py', 'src/billing.py']),
        true
      );
      expect(nodes.length).toBe(3);
      expect(edges.length).toBe(3);
      for (const n of nodes) {
        expect(Number.isFinite(n.position.x)).toBe(true);
        expect(Number.isFinite(n.position.y)).toBe(true);
      }
    }
  });

  it('collapses files into package clusters when groupingMode is directories', () => {
    const { nodes, edges } = buildFlowElements(
      sampleFiles,
      sampleEdges,
      'layered',
      'src/service.py',
      new Set(),
      true,
      'balanced',
      'directories'
    );
    expect(nodes.length).toBe(1);
    expect(nodes[0].id).toBe('dir:src');
    expect(edges.length).toBe(0);
  });
});

describe('App Explicit Consent Launchpad', () => {
  it('renders launchpad without auto-scanning local files until user clicks Analyze', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: 'ok',
        version: '1.0.0',
        parsers: { Python: 'tree-sitter' },
        default_workspace: 'C:/RepoDNA',
      }),
    } as Response);

    render(<App />);
    expect(screen.getByTestId('welcome-launchpad')).toBeInTheDocument();
    expect(screen.getByText(/Files are read only when you start a scan/i)).toBeInTheDocument();

    // Verify empty target shows validation alert if user clears input and submits
    const input = screen.getByLabelText(/Local Repository Directory Path/i);
    await waitFor(() => expect(input).toHaveValue('C:/RepoDNA'));
    fireEvent.change(input, { target: { value: '   ' } });
    const submitBtn = screen.getByTestId('analyze-submit-btn');
    fireEvent.click(submitBtn);
    expect(screen.getByTestId('error-alert-banner')).toHaveTextContent('EMPTY_TARGET');
  });

  it('retries transient 409 RESULT_NOT_READY in fetchJobResultWithRetry and propagates permanent errors', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    // First 2 calls return 409 RESULT_NOT_READY, 3rd call succeeds with 200 OK
    fetchSpy
      .mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({
          detail: { code: 'RESULT_NOT_READY', message: "Job is currently in status 'completed'." },
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({
          detail: { code: 'RESULT_NOT_READY', message: "Job is currently in status 'completed'." },
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          analysis_id: 'res-123',
          repo_name: 'NiceWP',
          total_files: 12,
        }),
      } as Response);

    const res = await fetchJobResultWithRetry('job-race-1', { maxRetries: 4, baseDelayMs: 5 });
    expect(res.repo_name).toBe('NiceWP');

    // Permanent 500 error should NOT be retried and should be thrown immediately
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({
        detail: { code: 'INTERNAL_SCAN_ERROR', message: 'Permanent failure' },
      }),
    } as Response);

    await expect(
      fetchJobResultWithRetry('job-fail-1', { maxRetries: 3, baseDelayMs: 5 })
    ).rejects.toThrow('Permanent failure');
  });
});
