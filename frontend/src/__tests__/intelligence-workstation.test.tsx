import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '../i18n';
import { CodeExplorerView } from '../components/CodeExplorerView';
import { SymbolRelationshipView } from '../components/SymbolRelationshipView';
import { EvidenceInspectorView } from '../components/EvidenceInspectorView';
import { ContextPanel } from '../components/ContextPanel';
import { IntelligenceWorkstation } from '../components/IntelligenceWorkstation';
import { PassportViewer } from '../components/PassportViewer';
import type {
  AnalysisResult,
  AgentContextResponse,
  CodeSearchResult,
  EvidenceLedgerResponse,
  EvidenceReference,
  RepositoryPassportV2,
  SearchResponse,
  SymbolDefinition,
  SymbolQueryResponse,
  SymbolTraceResult,
} from '../types/repodna';
import * as apiClient from '../api/client';

const mockAnalysis: AnalysisResult = {
  analysis_id: 'test_brain_456',
  repo_name: 'acme-brain',
  source_type: 'local',
  target_display: './acme-brain',
  is_demo: false,
  analyzed_at: '2026-11-10T12:00:00Z',
  duration_ms: 150,
  total_files: 8,
  total_lines_code: 600,
  total_lines_all: 800,
  total_size_bytes: 20000,
  languages: [
    {
      language: 'Python',
      support_level: 'full_ast',
      file_count: 8,
      lines_code: 600,
      lines_total: 800,
      size_bytes: 20000,
      percentage_of_code: 100,
    },
  ],
  files: [],
  edges: [],
  cycles: [],
  graph_metrics: {
    total_nodes: 8,
    total_edges: 7,
    connected_components: 1,
    scc_count: 0,
    cycle_count: 0,
    nodes_in_cycles: 0,
    orphan_files_count: 1,
    hub_files_count: 1,
    max_fan_in: 4,
    max_fan_out: 2,
    average_instability: 0.33,
    graph_density: 0.12,
  },
  health_report: {
    overall_score: 94.0,
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
    total_commits_scanned: 15,
    unique_contributors: 3,
    bus_factor_estimate: 2,
  },
  transparency: {
    supported_languages_detected: ['Python'],
    unsupported_languages_detected: [],
    unsupported_files_count: 0,
    unresolved_internal_imports_count: 0,
    dynamic_imports_count: 0,
    skipped_files: [],
    truncated_by_limits: false,
    parser_engine_info: {},
  },
};

const mockEvidence1: EvidenceReference = {
  evidence_id: 'ev_1',
  repository_revision: 'c0ffee12',
  file_path: 'backend/services/order.py',
  line_start: 10,
  line_end: 80,
  evidence_type: 'symbol_definition',
  support_level: 'full_ast',
  confidence_reason: 'AST tree-sitter parsed definition',
  created_at: '2026-11-10T12:00:00Z',
  is_stale: false,
  staleness_reason: 'fresh',
  code_snippet: 'class OrderService:\n    def process_order(self):\n        pass',
};

const mockEvidence2: EvidenceReference = {
  evidence_id: 'ev_2',
  repository_revision: 'c0ffee12',
  file_path: 'backend/services/order.py',
  line_start: 20,
  line_end: 25,
  evidence_type: 'import_statement',
  support_level: 'full_ast',
  confidence_reason: 'Static import resolution',
  created_at: '2026-11-10T12:00:00Z',
  is_stale: true,
  staleness_reason: 'line_shift',
  staleness_details: 'Lines shifted by +2',
  line_shift_delta: 2,
  code_snippet: 'import payment_gateway',
};

const mockSymbol1: SymbolDefinition = {
  id: 'sym_order_srv_1',
  name: 'OrderService',
  kind: 'class',
  file_path: 'backend/services/order.py',
  line_start: 10,
  line_end: 80,
  language: 'python',
  container_name: 'CoreServices',
  is_exported: true,
  evidence_id: 'ev_1',
};

const mockSymbol2: SymbolDefinition = {
  id: 'sym_order_srv_2',
  name: 'OrderService',
  kind: 'class',
  file_path: 'frontend/src/services/order.ts',
  line_start: 5,
  line_end: 45,
  language: 'typescript',
  is_exported: true,
  evidence_id: 'ev_fe_1',
};

const mockSearchResultItem: CodeSearchResult = {
  file_id: 'backend/services/order.py',
  score: 42.5,
  relevance_tier: 'HIGH',
  match_reasons: ['Exact filename match', 'Contains OrderService class definition'],
  matched_symbols: [mockSymbol1],
  evidence_items: [mockEvidence1],
  language: 'python',
  lines_code: 150,
  fan_in: 3,
  fan_out: 1,
  is_hub: true,
  in_cycle: false,
  snippet: 'class OrderService:\n    def process_order(self):\n        pass',
};

const mockSearchResponse: SearchResponse = {
  query: 'order processing',
  total_matches: 1,
  matches: [mockSearchResultItem],
  summary_text: 'Found 1 module matching order processing',
  query_intent: 'Find business logic for order processing',
  tokens_evaluated: ['order', 'processing'],
};

const mockSymbolResponse: SymbolQueryResponse = {
  total_symbols: 2,
  symbols: [mockSymbol1, mockSymbol2],
  summary_text: 'Found 2 symbols named OrderService',
};

const mockTraceResult: SymbolTraceResult = {
  symbol: mockSymbol1,
  definition_evidence: mockEvidence1,
  references: [
    {
      file_path: 'backend/api/routes.py',
      line: 25,
      symbol_name: 'OrderService',
      reference_kind: 'call',
      source_symbol_name: 'create_order_endpoint',
      is_verified: true,
      resolution_status: 'verified',
      confidence_reason: 'AST call edge',
    },
  ],
  candidate_references: [
    {
      file_path: 'backend/tests/test_order.py',
      line: 12,
      symbol_name: 'OrderService',
      reference_kind: 'call',
      source_symbol_name: 'test_order',
      is_verified: false,
      resolution_status: 'candidate',
      confidence_reason: 'Name match in test scope',
    },
  ],
  importing_modules: ['backend/api/routes.py'],
  calling_modules: ['backend/api/routes.py'],
  downstream_dependents: ['backend/api/routes.py'],
  downstream_impact_count: 1,
  is_ambiguous: false,
  summary_text: 'Traced OrderService',
};

const mockEvidenceResponse: EvidenceLedgerResponse = {
  total_evidence: 2,
  stale_count: 1,
  evidence_items: [mockEvidence1, mockEvidence2],
  summary_text: 'Evidence ledger with 2 entries',
};

const mockContextResponse: AgentContextResponse = {
  repository: 'acme-brain',
  revision: 'c0ffee12',
  generated_at: '2026-11-10T12:00:00Z',
  analysis_version: '0.5.0',
  mode: 'focused',
  analysis_coverage: {},
  confidence_level: 'high',
  requested_scope: { query: 'How does payment processing work?' },
  summary: 'Architectural context for payment processing.\nOrderService calls PaymentGateway',
  relevant_modules: [
    { id: 'backend/services/order.py', language: 'python', fan_in: 3, fan_out: 1 },
  ],
  evidence: ['ev_1: backend/services/order.py:10-80'],
  limitations: [],
  truncated: false,
  continuation_token: null,
  minimal_contract: false,
  estimated_tokens: 420,
  token_savings_pct: 68.5,
  is_savings_estimated: false,
  token_counting_method: 'exact_tiktoken_cl100k',
};

const mockPassportV2: RepositoryPassportV2 = {
  schema_version: '2.0.0',
  repo_name: 'acme-brain',
  git_revision: 'c0ffee12',
  analyzed_at: '2026-11-10T12:00:00Z',
  repodna_version: '0.5.0',
  primary_languages: [
    {
      language: 'Python',
      support_level: 'full_ast',
      file_count: 8,
      lines_code: 600,
      percentage: 100,
    },
  ],
  ast_coverage: {
    ast_file_coverage_pct: 100,
    ast_loc_coverage_pct: 100,
    supported_languages: ['Python'],
    partial_static_languages: [],
    unsupported_languages: [],
  },
  confidence: 'high',
  architectural_hubs: [],
  module_inventory: [],
  dependency_summary: {
    total_modules: 8,
    total_internal_edges: 7,
    cycle_count: 0,
    cyclic_scc_count: 0,
    orphan_modules_count: 1,
    hub_modules_count: 1,
    average_instability: 0.33,
  },
  identified_boundaries: ['backend'],
  architecture_health: {
    score: 94.0,
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
    total_inventory_count: 8,
    returned_inventory_count: 8,
  },
  symbol_index_summary: {
    total_symbols: 42,
    language_counts: { python: 42 },
    symbols_by_kind: { class: 12, function: 30 },
    total_verified_references: 18,
    total_candidate_references: 4,
    total_unresolved_references: 1,
  },
  architectural_entrypoints: [
    {
      file_path: 'backend/cli/main.py',
      role: 'cli_command',
      primary_symbol: 'main',
      evidence_id: 'ev_cli_1',
    },
  ],
  major_module_roles: [
    {
      file_path: 'backend/services/order.py',
      role: 'business_logic',
      responsibility: 'Core domain service orchestrating order workflow',
    },
  ],
  verified_reference_counts: 18,
  candidate_unresolved_counts: { candidate: 4, unresolved: 1 },
  evidence_ledger_summary: {
    total_evidence: 25,
    fresh_count: 24,
    stale_count: 1,
    evidence_by_type: { SYMBOL_DEF: 15, CALL: 10 },
  },
  retrieval_capabilities: {
    supports_semantic_search: true,
    supports_symbol_resolution: true,
    supports_cross_module_trace: true,
    supports_blast_radius: true,
    token_budgeting: true,
  },
  analysis_limitations: [],
  source_revision: 'c0ffee12',
};

describe('CodeExplorerView Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders search input and triggers smart retrieval', async () => {
    const searchSpy = vi.spyOn(apiClient, 'searchBrainCode').mockResolvedValue(mockSearchResponse);

    render(<CodeExplorerView analysisId="test_brain_456" />);

    const searchInput = screen.getByPlaceholderText(/Search symbols, services, controllers/i);
    fireEvent.change(searchInput, { target: { value: 'order processing' } });

    const searchBtn = screen.getByRole('button', { name: /Search/i });
    fireEvent.click(searchBtn);

    await waitFor(() => {
      expect(searchSpy).toHaveBeenCalledWith('test_brain_456', expect.objectContaining({
        query: 'order processing',
      }));
      expect(screen.getByText('backend/services/order.py')).toBeInTheDocument();
      expect(screen.getByText('OrderService')).toBeInTheDocument();
      expect(screen.getByText(/Exact filename match/i)).toBeInTheDocument();
    });
  });

  it('filters by language and kind', async () => {
    const searchSpy = vi.spyOn(apiClient, 'searchBrainCode').mockResolvedValue(mockSearchResponse);

    render(<CodeExplorerView analysisId="test_brain_456" />);

    const searchInput = screen.getByPlaceholderText(/Search symbols, services, controllers/i);
    fireEvent.change(searchInput, { target: { value: 'order' } });

    const langSelect = screen.getByLabelText(/Filter by language/i);
    fireEvent.change(langSelect, { target: { value: 'Python' } });

    const searchBtn = screen.getByRole('button', { name: /Search/i });
    fireEvent.click(searchBtn);

    await waitFor(() => {
      expect(searchSpy).toHaveBeenCalledWith('test_brain_456', expect.objectContaining({
        query: 'order',
        language: 'Python',
      }));
    });
  });
});

describe('SymbolRelationshipView Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('handles duplicate symbol names with disambiguation selector and renders callers', async () => {
    const symbolsSpy = vi.spyOn(apiClient, 'fetchBrainSymbols').mockResolvedValue(mockSymbolResponse);
    const traceSpy = vi.spyOn(apiClient, 'traceBrainSymbol').mockResolvedValue(mockTraceResult);

    render(<SymbolRelationshipView analysisId="test_brain_456" />);

    const symbolInput = screen.getByPlaceholderText(/Search symbol by identifier name/i);
    fireEvent.change(symbolInput, { target: { value: 'OrderService' } });

    const lookupBtn = screen.getByRole('button', { name: /Lookup Symbol/i });
    fireEvent.click(lookupBtn);

    await waitFor(() => {
      expect(symbolsSpy).toHaveBeenCalledWith('test_brain_456', expect.objectContaining({
        name: 'OrderService',
      }));
      // Disambiguation candidates should appear
      expect(screen.getByText(/backend\/services\/order\.py/i)).toBeInTheDocument();
      expect(screen.getByText(/frontend\/src\/services\/order\.ts/i)).toBeInTheDocument();
    });

    // Click on the first candidate
    const firstOption = screen.getByText(/backend\/services\/order\.py/i);
    fireEvent.click(firstOption);

    await waitFor(() => {
      expect(traceSpy).toHaveBeenCalledWith('test_brain_456', 'sym_order_srv_1');
      expect(screen.getByText('backend/api/routes.py')).toBeInTheDocument();
      expect(screen.getByText('create_order_endpoint')).toBeInTheDocument();
    });
  });
});

describe('EvidenceInspectorView Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders evidence ledger entries and staleness badges', async () => {
    const evidenceSpy = vi.spyOn(apiClient, 'fetchBrainEvidence').mockResolvedValue(mockEvidenceResponse);

    render(<EvidenceInspectorView analysisId="test_brain_456" />);

    await waitFor(() => {
      expect(evidenceSpy).toHaveBeenCalledWith('test_brain_456', expect.any(Object));
      expect(screen.getAllByText('ev_1').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('ev_2').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('FRESH').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('LINE SHIFT').length).toBeGreaterThanOrEqual(1);
    });
  });
});

describe('ContextPanel Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('builds context with selected mode and displays token metrics', async () => {
    const contextSpy = vi.spyOn(apiClient, 'buildBrainContext').mockResolvedValue(mockContextResponse);

    render(<ContextPanel analysisId="test_brain_456" />);

    const queryInput = screen.getByPlaceholderText(/auth session token validation/i);
    fireEvent.change(queryInput, { target: { value: 'How does payment processing work?' } });

    const buildBtn = screen.getByRole('button', { name: /Build Context/i });
    fireEvent.click(buildBtn);

    await waitFor(() => {
      expect(contextSpy).toHaveBeenCalledWith('test_brain_456', expect.objectContaining({
        query: 'How does payment processing work?',
        mode: 'focused',
      }));
      expect(screen.getByText(/420 tokens/i)).toBeInTheDocument();
      expect(screen.getByText(/68\.5% reduction vs codebase/i)).toBeInTheDocument();
    });
  });
});

describe('IntelligenceWorkstation Container', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('switches between tabs and maintains navigation state', async () => {
    vi.spyOn(apiClient, 'searchBrainCode').mockResolvedValue(mockSearchResponse);
    vi.spyOn(apiClient, 'fetchBrainEvidence').mockResolvedValue(mockEvidenceResponse);

    render(
      <IntelligenceWorkstation
        result={mockAnalysis}
        onSelectFileInStudio={() => {}}
      />
    );

    // Default tab is search
    expect(screen.getByText('Smart Search')).toBeInTheDocument();

    // Click on Evidence Ledger tab
    const evidenceTab = screen.getByRole('button', { name: /Evidence Ledger/i });
    fireEvent.click(evidenceTab);

    await waitFor(() => {
      expect(screen.getByText(/Architectural Evidence Ledger/i)).toBeInTheDocument();
    });

    // Click on Agent Context tab
    const contextTab = screen.getByRole('button', { name: /Agent Context/i });
    fireEvent.click(contextTab);

    expect(screen.getByText(/AI Agent Architecture Context Generator/i)).toBeInTheDocument();
  });
});

describe('PassportViewer v2 Enhancements', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders Passport v2 intelligence data and architectural entrypoints', async () => {
    vi.spyOn(apiClient, 'fetchRepositoryPassportV2').mockResolvedValue(mockPassportV2);

    render(<PassportViewer result={mockAnalysis} defaultWorkspacePath="." />);

    await waitFor(() => {
      expect(screen.getByText('acme-brain')).toBeInTheDocument();
      expect(screen.getByText('backend/cli/main.py')).toBeInTheDocument();
      expect(screen.getByText('business_logic')).toBeInTheDocument();
      expect(screen.getByText(/Symbol Intelligence Summary/i)).toBeInTheDocument();
    });
  });
});
