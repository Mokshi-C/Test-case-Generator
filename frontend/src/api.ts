export type JobState = 'queued' | 'running' | 'completed' | 'failed';

export interface Artifact {
  id: string;
  name: string;
  kind: string;
  size?: number;
  download_url: string;
}

export interface JobStatus {
  job_id: string;
  state: JobState;
  message: string;
  progress: number;
  result?: Record<string, unknown>;
  error?: string;
}

export interface ConfigOptions {
  providers: string[];
  languages: string[];
  frameworks: Record<string, string[]>;
  output_formats: string[];
  defaults: Record<string, string>;
}

export interface AutomationFile {
  name: string;
  content: string;
  size: number;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getConfigOptions(): Promise<ConfigOptions> {
  return parseResponse<ConfigOptions>(await fetch('/api/config/options'));
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return parseResponse<JobStatus>(await fetch(`/api/jobs/${jobId}`));
}

export async function ingestDocuments(formData: FormData): Promise<{ job_id: string }> {
  return parseResponse(await fetch('/api/ingest/documents', { method: 'POST', body: formData }));
}

export async function ingestCode(payload: {
  source_path: string;
  collection_name?: string;
}): Promise<{ job_id: string }> {
  return parseResponse(
    await fetch('/api/ingest/code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  );
}

export async function generateTests(payload: {
  query: string;
  collection_name?: string;
  num_retrieved: number;
  output_format: string;
}): Promise<{ job_id: string }> {
  return parseResponse(
    await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  );
}

export async function generateAutomation(payload: {
  test_case_content?: string;
  artifact_id?: string;
  collection_name?: string;
  language: string;
  framework: string;
  num_context_docs: number;
}): Promise<{ job_id: string }> {
  return parseResponse(
    await fetch('/api/automate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  );
}

