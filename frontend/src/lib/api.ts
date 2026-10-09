import { jobSchema, parseSnapshot } from './contract';
import type { Api, Connection, Edit, NewJob, Rule, Settings } from './types';
export class HttpApi implements Api {
  mode = 'api' as const;
  private csrfToken: string | null = null;
  private async request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    if (method !== 'GET' && !this.csrfToken)
      throw new Error('The backend must provide an authenticated CSRF token before this action.');
    const response = await fetch('/api/v1' + path, {
      method,
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(method !== 'GET' && this.csrfToken ? { 'X-CSRF-Token': this.csrfToken } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });
    if (!response.ok)
      throw new Error(
        response.status === 401
          ? 'Sign-in is required by the server.'
          : 'The backend is unavailable or rejected this action (' +
              response.status +
              '). No demo results were substituted.',
      );
    if (method === 'GET') this.csrfToken = response.headers.get('X-CSRF-Token');
    return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
  }
  async snapshot() {
    return parseSnapshot(await this.request<unknown>('/workspace'));
  }
  async create(input: NewJob) {
    return jobSchema.parse(await this.request<unknown>('/jobs', 'POST', input));
  }
  process(id: string) {
    return this.request<void>('/jobs/' + encodeURIComponent(id) + '/process', 'POST', {});
  }
  saveEdits(id: string, revision: number, edits: Edit[]) {
    return this.request<void>('/jobs/' + encodeURIComponent(id) + '/review', 'POST', {
      revision,
      edits,
    });
  }
  spotcheck(id: string, revision: number, note: string) {
    return this.request<void>('/jobs/' + encodeURIComponent(id) + '/spotcheck', 'POST', {
      revision,
      note,
    });
  }
  consent(id: string, grant: boolean, note: string) {
    return this.request<void>('/jobs/' + encodeURIComponent(id) + '/consent', 'POST', {
      grant,
      note,
    });
  }
  confirmAiSource(id: string) {
    return this.request<void>('/jobs/' + encodeURIComponent(id) + '/ai-source', 'POST', {});
  }
  export(id: string) {
    return this.request<void>('/jobs/' + encodeURIComponent(id) + '/exports', 'POST', {});
  }
  close(id: string, abandon: boolean) {
    return this.request<void>('/jobs/' + encodeURIComponent(id) + '/close', 'POST', { abandon });
  }
  saveConnection(connection: Connection) {
    return this.request<void>(
      '/connections/' + encodeURIComponent(connection.id),
      'PUT',
      connection,
    );
  }
  removeConnection(id: string) {
    return this.request<void>('/connections/' + encodeURIComponent(id), 'DELETE');
  }
  saveRules(rules: Rule[]) {
    return this.request<void>('/rules', 'PUT', { rules });
  }
  saveSettings(settings: Settings) {
    return this.request<void>('/settings', 'PUT', settings);
  }
  async reset() {
    throw new Error('Reset sample data is only available in demo mode.');
  }
}
