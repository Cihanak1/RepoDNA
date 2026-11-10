import type {
  AgentContextResponse,
  AnalysisResult,
  ArchitectureContract,
  DirectoryBrowseResponse,
  EvidenceLedgerResponse,
  EvidenceReference,
  GuardianReport,
  HealthCheckResponse,
  RepositoryPassport,
  RepositoryPassportV2,
  ScanProgress,
  ScanRequest,
  SearchResponse,
  SymbolQueryResponse,
  SymbolTraceResult,
} from '../types/repodna';

const API_BASE = '/api';

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

async function handleResponse<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let code = 'HTTP_ERROR';
    let message = `Request failed with status ${resp.status}`;
    try {
      const data = await resp.json();
      if (data?.detail && typeof data.detail === 'object') {
        code = data.detail.code || code;
        message = data.detail.message || message;
      } else if (typeof data?.detail === 'string') {
        message = data.detail;
      }
    } catch {
      // fallback
    }
    throw new ApiError(code, message, resp.status);
  }
  return resp.json() as Promise<T>;
}

export async function fetchBackendHealth(): Promise<HealthCheckResponse> {
  const resp = await fetch(`${API_BASE}/health`);
  return handleResponse<HealthCheckResponse>(resp);
}

export async function startAsyncScanJob(request: ScanRequest): Promise<ScanProgress> {
  const resp = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<ScanProgress>(resp);
}

export async function fetchJobProgress(jobId: string): Promise<ScanProgress> {
  const resp = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`);
  return handleResponse<ScanProgress>(resp);
}

export async function cancelScanJob(jobId: string): Promise<ScanProgress> {
  const resp = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  });
  return handleResponse<ScanProgress>(resp);
}

export async function fetchJobResult(jobId: string): Promise<AnalysisResult> {
  const resp = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}/result`);
  return handleResponse<AnalysisResult>(resp);
}

export async function fetchJobResultWithRetry(
  jobId: string,
  options?: { maxRetries?: number; baseDelayMs?: number }
): Promise<AnalysisResult> {
  const maxRetries = options?.maxRetries ?? 5;
  const baseDelayMs = options?.baseDelayMs ?? 80;

  let attempt = 0;
  while (true) {
    try {
      return await fetchJobResult(jobId);
    } catch (err) {
      const isTransientNotReady =
        err instanceof ApiError &&
        (err.status === 409 || err.code === 'RESULT_NOT_READY');

      if (!isTransientNotReady || attempt >= maxRetries) {
        throw err;
      }

      const backoffMs = baseDelayMs * Math.pow(2, attempt);
      attempt += 1;
      await new Promise<void>((resolve) => window.setTimeout(resolve, backoffMs));
    }
  }
}

export async function runSyncScan(request: ScanRequest): Promise<AnalysisResult> {
  const resp = await fetch(`${API_BASE}/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<AnalysisResult>(resp);
}

export async function browseDirectories(path?: string): Promise<DirectoryBrowseResponse> {
  const qs = path ? `?path=${encodeURIComponent(path)}` : '';
  const resp = await fetch(`${API_BASE}/fs/browse${qs}`);
  return handleResponse<DirectoryBrowseResponse>(resp);
}

export function getExportUrl(analysisId: string, format: 'json' | 'html'): string {
  return `${API_BASE}/analyses/${encodeURIComponent(analysisId)}/export/${format}`;
}

export async function fetchRepositoryPassport(
  analysisId: string,
  maxModules: number = 150
): Promise<RepositoryPassport> {
  const resp = await fetch(
    `${API_BASE}/analyses/${encodeURIComponent(analysisId)}/passport?max_modules=${maxModules}`
  );
  return handleResponse<RepositoryPassport>(resp);
}

export async function fetchArchitectureContract(path: string = '.'): Promise<ArchitectureContract | null> {
  try {
    const resp = await fetch(`${API_BASE}/contract?path=${encodeURIComponent(path)}`);
    if (resp.status === 404) return null;
    return await handleResponse<ArchitectureContract>(resp);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export async function assessPRGuardian(params: {
  target: string;
  base_ref: string;
  head_ref: string;
  mode?: string;
}): Promise<GuardianReport> {
  const resp = await fetch(`${API_BASE}/guardian/assess`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  return handleResponse<GuardianReport>(resp);
}

// ----------------------------------------------------------------------------
// Repository Brain API Calls (v0.5.0)
// ----------------------------------------------------------------------------

export async function searchBrainCode(
  analysisId: string,
  params: {
    query: string;
    limit?: number;
    kind?: string;
    path_filter?: string;
    language?: string;
  }
): Promise<SearchResponse> {
  const resp = await fetch(`${API_BASE}/analyses/${encodeURIComponent(analysisId)}/brain/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  return handleResponse<SearchResponse>(resp);
}

export async function fetchBrainSymbols(
  analysisId: string,
  params?: {
    name?: string;
    kind?: string;
    language?: string;
    file_path?: string;
    container?: string;
    limit?: number;
  }
): Promise<SymbolQueryResponse> {
  const qs = new URLSearchParams();
  if (params?.name) qs.set('name', params.name);
  if (params?.kind) qs.set('kind', params.kind);
  if (params?.language) qs.set('language', params.language);
  if (params?.file_path) qs.set('file_path', params.file_path);
  if (params?.container) qs.set('container', params.container);
  if (params?.limit) qs.set('limit', String(params.limit));

  const queryStr = qs.toString() ? `?${qs.toString()}` : '';
  const resp = await fetch(
    `${API_BASE}/analyses/${encodeURIComponent(analysisId)}/brain/symbols${queryStr}`
  );
  return handleResponse<SymbolQueryResponse>(resp);
}

export async function traceBrainSymbol(
  analysisId: string,
  symbolId: string
): Promise<SymbolTraceResult> {
  const resp = await fetch(
    `${API_BASE}/analyses/${encodeURIComponent(analysisId)}/brain/symbols/${encodeURIComponent(symbolId)}/trace`
  );
  return handleResponse<SymbolTraceResult>(resp);
}

export async function fetchBrainEvidence(
  analysisId: string,
  params?: {
    evidence_id?: string;
    file_path?: string;
    symbol_name?: string;
    evidence_type?: string;
    check_staleness?: boolean;
    limit?: number;
  }
): Promise<EvidenceLedgerResponse> {
  const qs = new URLSearchParams();
  if (params?.evidence_id) qs.set('evidence_id', params.evidence_id);
  if (params?.file_path) qs.set('file_path', params.file_path);
  if (params?.symbol_name) qs.set('symbol_name', params.symbol_name);
  if (params?.evidence_type) qs.set('evidence_type', params.evidence_type);
  if (params?.check_staleness !== undefined) qs.set('check_staleness', String(params.check_staleness));
  if (params?.limit) qs.set('limit', String(params.limit));

  const queryStr = qs.toString() ? `?${qs.toString()}` : '';
  const resp = await fetch(
    `${API_BASE}/analyses/${encodeURIComponent(analysisId)}/brain/evidence${queryStr}`
  );
  return handleResponse<EvidenceLedgerResponse>(resp);
}

export async function fetchBrainEvidenceItem(
  analysisId: string,
  evidenceId: string,
  checkStaleness: boolean = true
): Promise<EvidenceReference> {
  const resp = await fetch(
    `${API_BASE}/analyses/${encodeURIComponent(analysisId)}/brain/evidence/${encodeURIComponent(evidenceId)}?check_staleness=${checkStaleness}`
  );
  return handleResponse<EvidenceReference>(resp);
}

export async function buildBrainContext(
  analysisId: string,
  params: {
    mode?: string;
    query?: string;
    target_files?: string[];
    max_tokens?: number;
    max_chars?: number;
    minimal_contract?: boolean;
  }
): Promise<AgentContextResponse> {
  const resp = await fetch(`${API_BASE}/analyses/${encodeURIComponent(analysisId)}/brain/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  return handleResponse<AgentContextResponse>(resp);
}

export async function fetchRepositoryPassportV2(
  analysisId: string,
  maxModules: number = 150
): Promise<RepositoryPassportV2> {
  const resp = await fetch(
    `${API_BASE}/analyses/${encodeURIComponent(analysisId)}/passport/v2?max_modules=${maxModules}`
  );
  return handleResponse<RepositoryPassportV2>(resp);
}

export async function validatePassportJson(manifestJson: string): Promise<{
  valid: boolean;
  schema_version: string;
  repo_name: string;
  git_revision: string;
  primary_languages: string[];
  violations: string[];
}> {
  const resp = await fetch(`${API_BASE}/passport/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ manifest_json: manifestJson }),
  });
  return handleResponse<{
    valid: boolean;
    schema_version: string;
    repo_name: string;
    git_revision: string;
    primary_languages: string[];
    violations: string[];
  }>(resp);
}

export async function migratePassportV1ToV2(manifestJson: string): Promise<RepositoryPassportV2> {
  const resp = await fetch(`${API_BASE}/passport/migrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ manifest_json: manifestJson }),
  });
  return handleResponse<RepositoryPassportV2>(resp);
}

