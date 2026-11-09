import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '../i18n';
import { GuardianOverview } from '../components/GuardianOverview';
import { ContractInspector } from '../components/ContractInspector';
import { PassportViewer } from '../components/PassportViewer';
import type { AnalysisResult, ArchitectureContract, GuardianReport, RepositoryPassport } from '../types/repodna';
import * as apiClient from '../api/client';

const mockAnalysis: AnalysisResult = {
  analysis_id: 'test_123',
  repo_name: 'acme-commerce',
  source_type: 'local',
  target_display: './acme-commerce',
  is_demo: false,
  analyzed_at: '2026-11-09T20:00:00Z',
  duration_ms: 120,
  total_files: 5,
  total_lines_code: 350,
  total_lines_all: 500,
  total_size_bytes: 12000,
  languages: [
    {
      language: 'TypeScript',
      support_level: 'full_ast',
      file_count: 5,
      lines_code: 350,
      lines_total: 500,
      size_bytes: 12000,
      percentage_of_code: 100,
    },
  ],
  files: [],
  edges: [],
  cycles: [],
  graph_metrics: {
    total_nodes: 5,
    total_edges: 4,
    connected_components: 1,
    scc_count: 0,
    cycle_count: 0,
    nodes_in_cycles: 0,
    orphan_files_count: 1,
    hub_files_count: 1,
    max_fan_in: 3,
    max_fan_out: 2,
    average_instability: 0.4,
    graph_density: 0.16,
  },
  health_report: {
    overall_score: 92.5,
    grade: 'A',
    status: 'evaluated',
    confidence: 'high',
    methodology: 'Standard',
    category_scores: [],
    findings: [],
    passed_rules: ['ARCH-001'],
    summary_metrics: {},
  },
  git_insights: {
    is_git_repo: true,
    recent_commits: [],
    hotspots: [],
    total_commits_scanned: 10,
    unique_contributors: 2,
    bus_factor_estimate: 2,
  },
  transparency: {
    supported_languages_detected: ['TypeScript'],
    unsupported_languages_detected: [],
    unsupported_files_count: 0,
    unresolved_internal_imports_count: 0,
    dynamic_imports_count: 0,
    skipped_files: [],
    truncated_by_limits: false,
    parser_engine_info: {},
  },
};

describe('GuardianOverview Component', () => {
  it('renders title, base/head inputs and assess button', () => {
    render(<GuardianOverview result={mockAnalysis} defaultWorkspacePath="." />);
    expect(screen.getByText(/PR Architecture Guardian/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Assess PR/i })).toBeInTheDocument();
  });

  it('renders report details when assessment succeeds', async () => {
    const mockReport: GuardianReport = {
      generated_at: '2026-11-09T20:00:00Z',
      base_provenance: {
        ref_name: 'main',
        is_working_tree: false,
        analyzed_at: '2026-11-09T19:00:00Z',
        total_files: 5,
        total_lines_code: 350,
        ast_coverage_pct: 100,
        health_grade: 'A',
      },
      head_provenance: {
        ref_name: 'HEAD',
        is_working_tree: false,
        analyzed_at: '2026-11-09T20:00:00Z',
        total_files: 5,
        total_lines_code: 350,
        ast_coverage_pct: 100,
        health_grade: 'A',
      },
      verdict: 'PASS',
      verdict_reason: 'Architecture clean: no new circular dependencies detected.',
      risk_assessment: {
        risk_score: 0,
        risk_level: 'LOW',
        risk_factors: ['No architectural regression indicators detected.'],
        mitigation_advice: [],
      },
      mode: 'enforce',
      added_modules: [],
      removed_modules: [],
      renamed_modules: [],
      added_edges: [],
      removed_edges: [],
      new_cycles: [],
      resolved_cycles: [],
      persisting_cycles_count: 0,
      contract_evaluated: false,
      new_contract_violations: [],
      resolved_contract_violations: [],
      existing_baseline_violations: [],
      unknown_evaluations: [],
      coupling_deltas: [],
      health_delta: {
        score_before: 92.5,
        score_after: 92.5,
        score_delta: 0,
        grade_before: 'A',
        grade_after: 'A',
        status_before: 'evaluated',
        status_after: 'evaluated',
      },
      coverage_delta: {
        ast_loc_coverage_before: 100,
        ast_loc_coverage_after: 100,
        ast_loc_coverage_delta: 0,
        supported_langs_before: ['TypeScript'],
        supported_langs_after: ['TypeScript'],
        caveats: [],
      },
      diff_summary: 'Diff clean',
      summary_markdown: '## Markdown clean',
      metadata: {},
    };

    vi.spyOn(apiClient, 'assessPRGuardian').mockResolvedValueOnce(mockReport);

    render(<GuardianOverview result={mockAnalysis} defaultWorkspacePath="." />);
    const runBtn = screen.getByRole('button', { name: /Assess PR/i });
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText(/PASS — ARCHITECTURE CLEAN/i)).toBeInTheDocument();
      expect(screen.getByText(/Architecture clean: no new circular dependencies detected./i)).toBeInTheDocument();
    });
  });
});

describe('ContractInspector Component', () => {
  it('renders contract rules when contract is loaded', async () => {
    const mockContract: ArchitectureContract = {
      version: 1,
      policy: { mode: 'enforce', unknown_behavior: 'warn' },
      rules: [
        {
          id: 'LAYER-001',
          title: 'Domain Layer Isolation',
          description: 'Domain must not import infra',
          from: ['domain/**'],
          disallow_imports: ['infra/**'],
          severity: 'critical',
          remediation: 'Use interfaces',
        },
      ],
    };

    vi.spyOn(apiClient, 'fetchArchitectureContract').mockResolvedValueOnce(mockContract);

    render(<ContractInspector result={mockAnalysis} defaultWorkspacePath="." />);

    await waitFor(() => {
      expect(screen.getByText(/LAYER-001/i)).toBeInTheDocument();
      expect(screen.getByText(/Domain Layer Isolation/i)).toBeInTheDocument();
    });
  });

  it('renders starter callout when no contract is found', async () => {
    vi.spyOn(apiClient, 'fetchArchitectureContract').mockResolvedValueOnce(null);

    render(<ContractInspector result={mockAnalysis} defaultWorkspacePath="." />);

    await waitFor(() => {
      expect(screen.getByText(/No Architecture Contract Found/i)).toBeInTheDocument();
      expect(screen.getByText(/repodna contract init/i)).toBeInTheDocument();
    });
  });
});

describe('PassportViewer Component', () => {
  it('renders structural passport manifest identity card', async () => {
    const mockPassport: RepositoryPassport = {
      schema_version: '1.0.0',
      repo_name: 'acme-commerce',
      git_revision: 'c0ffee12',
      analyzed_at: '2026-11-09T20:00:00Z',
      repodna_version: '0.4.0',
      primary_languages: [
        {
          language: 'TypeScript',
          support_level: 'full_ast',
          file_count: 5,
          lines_code: 350,
          percentage: 100,
        },
      ],
      ast_coverage: {
        ast_file_coverage_pct: 100,
        ast_loc_coverage_pct: 100,
        supported_languages: ['TypeScript'],
        partial_static_languages: [],
        unsupported_languages: [],
      },
      confidence: 'high',
      architectural_hubs: [
        {
          file_id: 'src/services/order.ts',
          fan_in: 4,
          fan_out: 1,
          instability: 0.2,
          is_hub: true,
        },
      ],
      module_inventory: [
        {
          id: 'src/services/order.ts',
          language: 'TypeScript',
          lines_code: 120,
          fan_in: 4,
          fan_out: 1,
          instability: 0.2,
          in_cycle: false,
          is_hub: true,
        },
      ],
      dependency_summary: {
        total_modules: 5,
        total_internal_edges: 4,
        cycle_count: 0,
        cyclic_scc_count: 0,
        orphan_modules_count: 1,
        hub_modules_count: 1,
        average_instability: 0.4,
      },
      identified_boundaries: ['src'],
      architecture_health: {
        score: 92.5,
        grade: 'A',
        status: 'evaluated',
        confidence: 'high',
        confidence_reason: '100% AST coverage',
      },
      verified_findings: [],
      unknown_unverified: [],
      contract_status: {
        has_contract: false,
        rules_count: 0,
        active_violations_count: 0,
      },
      evidence_references: [],
      truncation_metadata: {
        is_truncated: false,
        total_inventory_count: 5,
        returned_inventory_count: 5,
      },
    };

    vi.spyOn(apiClient, 'fetchRepositoryPassport').mockResolvedValueOnce(mockPassport);

    render(<PassportViewer result={mockAnalysis} defaultWorkspacePath="." />);

    await waitFor(() => {
      expect(screen.getByText('acme-commerce')).toBeInTheDocument();
      expect(screen.getByText('c0ffee12')).toBeInTheDocument();
      expect(screen.getAllByText('src/services/order.ts').length).toBeGreaterThanOrEqual(1);
    });
  });
});
