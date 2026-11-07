import type {
  AnalysisResult,
  DirectoryBrowseResponse,
  HealthCheckResponse,
  ScanProgress,
  ScanRequest,
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
