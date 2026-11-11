import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '../i18n';
import { RefactoringAdvisorView } from '../components/RefactoringAdvisorView';
import type { RefactoringAdvisorReport } from '../types/advisor';
import type { AnalysisResult } from '../types/repodna';
import * as apiClient from '../api/client';

const mockAnalysis: AnalysisResult = {
  analysis_id: 'test_advisor_analysis',
  repo_name: 'acme-commerce',
  source_type: 'local',
  target_display: './acme-commerce',
  is_demo: false,
  analyzed_at: '2026-11-11T12:00:00Z',
  duration_ms: 120,
  total_files: 10,
  total_lines_code: 800,
  total_lines_all: 1000,
  total_size_bytes: 25000,
  languages: [
    {
      language: 'TypeScript',
      support_level: 'full_ast',
      file_count: 10,
      lines_code: 800,
      lines_total: 1000,
      size_bytes: 25000,
      percentage_of_code: 100,
    },
  ],
  files: [],
  edges: [],
  cycles: [],
  graph_metrics: {
    total_nodes: 10,
    total_edges: 12,
    connected_components: 1,
    scc_count: 1,
    cycle_count: 1,
    nodes_in_cycles: 2,
    orphan_files_count: 0,
    hub_files_count: 1,
    max_fan_in: 5,
    max_fan_out: 4,
    average_instability: 0.45,
    graph_density: 0.12,
  },
  health_report: {
    overall_score: 78.0,
    grade: 'B',
    status: 'evaluated',
    confidence: 'high',
    confidence_reason: '100% AST coverage',
    ast_file_coverage_pct: 100,
    ast_loc_coverage_pct: 100,
    dependency_graph_evaluated: true,
    cycle_analysis_summary: '1 cycle detected',
    methodology: 'Static AST graph analysis',
    category_scores: [],
    findings: [],
    passed_rules: [],
    unverified_rules: [],
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

const mockReport: RefactoringAdvisorReport = {
  schema_version: '1.0.0',
  repo_identity: 'acme-commerce',
  total_recommendations: 2,
  total_modules_analyzed: 10,
  by_category: {
    circular_dependency_reduction: 1,
    high_coupling_module_review: 1,
    layer_boundary_improvement: 0,
    oversized_architectural_hub_review: 0,
  },
  by_severity: {
    critical: 1,
    high: 0,
    medium: 1,
    low: 0,
  },
  recommendations: [
    {
      recommendation_id: 'ref_cycle_111122223333',
      target_module: 'src/services/order.ts',
      category: 'circular_dependency_reduction',
      severity: 'critical',
      title: 'Break circular dependency: order.ts <-> payment.ts',
      description: 'Tight cycle creates high coupling and complicates independent unit testing.',
      evidence_snippets: ['Import payment.ts line 12'],
      revision_source: 'snapshot-v1',
      affected_modules: ['src/services/payment.ts'],
      expected_architectural_benefit: 'Removes circular cycle and enables independent deployments.',
      suggested_action_steps: [
        'Extract shared OrderEvent interface into src/types/events.ts',
        'Invert dependency by publishing events to an EventEmitter',
        'Remove direct import from payment.ts to order.ts',
      ],
      risks_and_limitations: 'Ensure event subscriptions are initialized before checkout flow.',
      support_level: 'verified',
      metric_delta_preview: {
        cycle_reduction: 1,
        breaking_edge: 'src/services/order.ts -> src/services/payment.ts',
      },
    },
    {
      recommendation_id: 'ref_coupling_444455556666',
      target_module: 'src/controllers/gateway.ts',
      category: 'high_coupling_module_review',
      severity: 'medium',
      title: 'Decouple high efferent coupling in gateway.ts',
      description: 'Module directly imports 8 internal services.',
      evidence_snippets: ['Imports 8 services'],
      revision_source: 'snapshot-v1',
      affected_modules: [],
      expected_architectural_benefit: 'Reduces blast radius from 8 to 4.',
      suggested_action_steps: [
        'Group services under a Facade',
        'Pass service instances via constructor injection',
      ],
      risks_and_limitations: 'Minimal risk with facade pattern.',
      support_level: 'verified',
      metric_delta_preview: {
        current_fan_out: 8,
        target_fan_out: 4,
      },
    },
  ],
  summary_text: 'RepoDNA Architectural Refactoring Advisory Report',
};

describe('RefactoringAdvisorView Component', () => {
  it('renders title, summary KPI strip, and recommendation cards', async () => {
    vi.spyOn(apiClient, 'fetchRefactoringRecommendations').mockResolvedValue(mockReport);
    const selectFileSpy = vi.fn();

    render(
      <RefactoringAdvisorView
        result={mockAnalysis}
        onSelectFileInStudio={selectFileSpy}
      />
    );

    // Verify title and version badge
    expect(screen.getByText('Architecture Refactoring Advisor')).toBeInTheDocument();
    expect(screen.getByText('v0.7.0 Portfolio Release')).toBeInTheDocument();

    // Verify cards loaded
    await waitFor(() => {
      expect(screen.getByText('Break circular dependency: order.ts <-> payment.ts')).toBeInTheDocument();
      expect(screen.getByText('Decouple high efferent coupling in gateway.ts')).toBeInTheDocument();
    });

    // Verify KPI numbers
    expect(screen.getByText('Total Recommendations')).toBeInTheDocument();
    expect(screen.getByText('Critical Cycles')).toBeInTheDocument();

    // Verify action checklist items
    expect(screen.getByText('Extract shared OrderEvent interface into src/types/events.ts')).toBeInTheDocument();

    // Test Inspect in Graph button click
    const inspectBtn = screen.getByTestId('inspect-graph-btn-ref_cycle_111122223333');
    fireEvent.click(inspectBtn);
    expect(selectFileSpy).toHaveBeenCalledWith('src/services/order.ts');
  });

  it('filters recommendations by category', async () => {
    const fetchSpy = vi.spyOn(apiClient, 'fetchRefactoringRecommendations').mockResolvedValue(mockReport);

    render(
      <RefactoringAdvisorView
        result={mockAnalysis}
        onSelectFileInStudio={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('filter-cat-circular_dependency_reduction')).toBeInTheDocument();
    });

    // Click on Cycles filter
    fireEvent.click(screen.getByTestId('filter-cat-circular_dependency_reduction'));
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        'test_advisor_analysis',
        'circular_dependency_reduction',
        undefined
      );
    });
  });

  it('renders clean baseline state when zero recommendations exist', async () => {
    const cleanReport: RefactoringAdvisorReport = {
      ...mockReport,
      total_recommendations: 0,
      by_category: {
        circular_dependency_reduction: 0,
        high_coupling_module_review: 0,
        layer_boundary_improvement: 0,
        oversized_architectural_hub_review: 0,
      },
      recommendations: [],
    };
    vi.spyOn(apiClient, 'fetchRefactoringRecommendations').mockResolvedValue(cleanReport);

    render(
      <RefactoringAdvisorView
        result={mockAnalysis}
        onSelectFileInStudio={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Clean Architectural Baseline')).toBeInTheDocument();
    });
  });
});
