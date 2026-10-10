import { z } from 'zod';
const role = z.enum(['owner', 'editor', 'viewer']);
const uuid = z.uuid();
export const sessionSchema = z
  .object({
    user_id: uuid,
    workspace_id: uuid.nullable(),
    role: role.nullable(),
    platform_admin: z.boolean(),
    csrf_token: z.string(),
    expires_at: z.string(),
  })
  .strict();
const workspace = z.object({ id: uuid, name: z.string(), role }).strict();
const job = z
  .object({
    id: uuid,
    name: z.string(),
    status: z.string(),
    revision: z.number().int(),
    currency: z.string(),
    created_at: z.string(),
    deletion_state: z.string(),
  })
  .strict();
const page = <T extends z.ZodType>(item: T) =>
  z.object({ items: z.array(item), next_cursor: z.string().nullable() }).strict();
export type ServerSession = z.infer<typeof sessionSchema>;
export type ServerJob = z.infer<typeof job>;
const fileSchema = z
  .object({
    id: uuid,
    display_name: z.string(),
    bytes: z.number().int(),
    sha256: z.string(),
    pages: z.number().int(),
    kind: z.enum(['pdf', 'image']),
    password_required: z.boolean(),
    revision: z.number().int(),
  })
  .strict();
const operationSchema = z
  .object({
    id: uuid,
    job_id: uuid,
    input_revision: z.number().int(),
    action: z.string(),
    state: z.enum([
      'queued',
      'running',
      'awaiting_input',
      'succeeded',
      'failed',
      'cancel_requested',
      'cancelled',
      'uncertain',
    ]),
    stage: z.string().nullable(),
    pages_done: z.number().int().nullable(),
    pages_total: z.number().int().nullable(),
    error_code: z.string().nullable(),
  })
  .strict();
const money = z
  .string()
  .regex(/^-?(?:0|[1-9][0-9]*)\.[0-9]{2}$/)
  .nullable();
const rowSchema = z
  .object({
    id: z.string(),
    statement_id: z.string(),
    sequence: z.number().int(),
    date: z.string().nullable(),
    description: z.string(),
    debit: money,
    credit: money,
    balance: money,
    file_id: uuid,
    page: z.number().int(),
    engine: z.enum(['text', 'docling', 'ai']),
    flags: z.array(z.string()),
    fixed_by: z.string().nullable(),
    source_reviewed: z.boolean(),
    category: z.string().nullable(),
  })
  .strict();
export type ServerFile = z.infer<typeof fileSchema>;
export type ServerOperation = z.infer<typeof operationSchema>;
export class FoundationError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export class FoundationApi {
  async request<T>(
    path: string,
    schema: z.ZodType<T>,
    session?: ServerSession,
    body?: unknown,
    method = 'GET',
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (method !== 'GET') {
      if (!session) throw new FoundationError(401, 'Please sign in again.');
      headers['X-CSRF-Token'] = session.csrf_token;
      headers['Idempotency-Key'] = crypto.randomUUID();
      headers['Content-Type'] = 'application/json';
    }
    const response = await fetch('/api/v1' + path, {
      method,
      headers,
      credentials: 'same-origin',
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: 'no-store',
    });
    if (!response.ok) {
      // Only use the service's bounded error message; never display arbitrary response bodies.
      const error = z
        .object({ message: z.string().max(250), code: z.string().max(80), request_id: uuid })
        .safeParse(await response.json().catch(() => null));
      throw new FoundationError(
        response.status,
        error.success ? error.data.message : 'The service is unavailable. Please try again.',
      );
    }
    return schema.parse(response.status === 204 ? undefined : await response.json());
  }
  session() {
    return this.request('/session', sessionSchema);
  }
  workspaces(cursor: string | null = null) {
    return this.request(
      '/workspaces' + (cursor ? '?cursor=' + encodeURIComponent(cursor) : ''),
      page(workspace),
    );
  }
  jobs(cursor: string | null = null, search = '') {
    const params = new URLSearchParams();
    if (cursor) params.set('cursor', cursor);
    if (search) params.set('search', search);
    return this.request('/jobs' + (params.size ? '?' + params.toString() : ''), page(job));
  }
  job(id: string) {
    return this.request(
      '/jobs/' + encodeURIComponent(id),
      job
        .extend({
          options: z.record(z.string(), z.unknown()),
          content_digest: z.string().nullable(),
          export_revision: z.number().nullable(),
          source_checked: z.boolean(),
          ai_source_checked: z.boolean(),
        })
        .strict(),
    );
  }
  create(
    session: ServerSession,
    name: string,
    currency: string,
    options: Record<string, unknown> = {},
  ) {
    return this.request(
      '/jobs',
      z.object({ id: uuid }).passthrough(),
      session,
      { name, currency, date_order: 'auto', outputs: ['excel', 'csv'], ...options },
      'POST',
    );
  }
  intakeOptions() {
    return this.request(
      '/intake-options',
      z
        .object({
          upload_bytes: z.number().int(),
          job_files: z.number().int(),
          job_pages: z.number().int(),
          profiles: z.array(z.object({ id: z.string(), name: z.string() }).strict()),
        })
        .strict(),
    );
  }
  files(id: string) {
    return this.request('/jobs/' + encodeURIComponent(id) + '/files', page(fileSchema));
  }
  operations(id: string) {
    return this.request('/jobs/' + encodeURIComponent(id) + '/operations', page(operationSchema));
  }
  statements(id: string) {
    return this.request(
      '/jobs/' + encodeURIComponent(id) + '/statements',
      page(
        z
          .object({
            id: z.string(),
            profile_id: z.string(),
            verdict: z.string(),
            rows: z.number().int(),
            flags: z.array(z.string()),
            checks: z.record(z.string(), z.boolean().nullable()),
            version: z.string(),
            source_checked: z.boolean(),
          })
          .strict(),
      ).extend({ revision: z.number().int() }),
    );
  }
  rows(id: string, cursor: string | null = null) {
    return this.request(
      '/jobs/' +
        encodeURIComponent(id) +
        '/rows' +
        (cursor ? '?cursor=' + encodeURIComponent(cursor) : ''),
      page(rowSchema).extend({ revision: z.number().int() }),
    );
  }
  async upload(
    session: ServerSession,
    id: string,
    file: File,
    expected_revision: number,
    requestKey: string,
  ) {
    const response = await fetch('/api/v1/jobs/' + encodeURIComponent(id) + '/files', {
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/octet-stream',
        'X-CSRF-Token': session.csrf_token,
        'Idempotency-Key': requestKey,
        'X-Expected-Revision': String(expected_revision),
        'X-File-Name': encodeURIComponent(file.name),
        'X-Synthetic-Confirmed': 'true',
      },
      body: file,
    });
    if (!response.ok) {
      const error = z
        .object({ message: z.string().max(250), code: z.string().max(80), request_id: uuid })
        .safeParse(await response.json().catch(() => null));
      throw new FoundationError(
        response.status,
        error.success ? error.data.message : 'The upload could not be confirmed. Retry this file.',
      );
    }
    return fileSchema.parse(await response.json());
  }
  intake(session: ServerSession, id: string, expected_revision: number) {
    return this.request(
      '/jobs/' + id + '/intake',
      operationSchema,
      session,
      { expected_revision },
      'POST',
    );
  }
  convert(session: ServerSession, id: string, expected_revision: number) {
    return this.request(
      '/jobs/' + id + '/operations',
      operationSchema,
      session,
      { expected_revision, action: 'extract' },
      'POST',
    );
  }
  retry(session: ServerSession, id: string, expected_revision: number, retry_operation_id: string) {
    return this.request(
      '/jobs/' + id + '/operations',
      operationSchema,
      session,
      { expected_revision, action: 'retry', retry_operation_id },
      'POST',
    );
  }
  cancel(session: ServerSession, id: string, expected_revision: number, operationId: string) {
    return this.request(
      '/jobs/' + id + '/operations/' + operationId + '/cancel',
      operationSchema,
      session,
      { expected_revision },
      'POST',
    );
  }
  unlock(
    session: ServerSession,
    id: string,
    expected_revision: number,
    fileId: string,
    password: string,
  ) {
    return this.request(
      '/jobs/' + id + '/files/' + fileId + '/unlock',
      operationSchema,
      session,
      { expected_revision, password },
      'POST',
    );
  }
  reorder(session: ServerSession, id: string, expected_revision: number, file_ids: string[]) {
    return this.request(
      '/jobs/' + id + '/file-order',
      z.object({ id: uuid }).passthrough(),
      session,
      { expected_revision, file_ids },
      'PUT',
    );
  }
  switch(session: ServerSession, workspace_id: string) {
    return this.request('/session/workspace', sessionSchema, session, { workspace_id }, 'POST');
  }
  logout(session: ServerSession) {
    return this.request('/session/logout', z.undefined(), session, undefined, 'POST');
  }
  members(cursor: string | null = null) {
    return this.request(
      '/members' + (cursor ? '?cursor=' + encodeURIComponent(cursor) : ''),
      page(
        z
          .object({
            id: uuid,
            display_name: z.string(),
            role,
            active: z.boolean(),
            version: z.number().int(),
          })
          .strict(),
      ),
    );
  }
  changeMember(
    session: ServerSession,
    id: string,
    expected_version: number,
    newRole: z.infer<typeof role>,
    active: boolean,
  ) {
    return this.request(
      '/members/' + id,
      z.object({ id: uuid }).passthrough(),
      session,
      { expected_version, role: newRole, active },
      'PATCH',
    );
  }
  invite(session: ServerSession, email: string, inviteRole: 'editor' | 'viewer') {
    return this.request(
      '/invitations',
      z.object({ id: uuid, accept_url: z.url() }).passthrough(),
      session,
      { email, role: inviteRole },
      'POST',
    );
  }
  revoke(session: ServerSession, id: string) {
    return this.request('/invitations/' + id, z.undefined(), session, undefined, 'DELETE');
  }
  accept(session: ServerSession, token: string) {
    return this.request('/invitations/accept', workspace, session, { token }, 'POST');
  }
  settings() {
    return this.request(
      '/settings',
      z
        .object({
          version: z.number(),
          currency: z.string(),
          date_order: z.string(),
          output_date_format: z.string(),
          outputs: z.array(z.string()),
          retention_days: z.number().nullable(),
        })
        .strict(),
    );
  }
  health() {
    return this.request(
      '/admin/health',
      z
        .object({
          database: z.string(),
          storage: z.string(),
          worker: z.string(),
          models: z.string(),
        })
        .strict(),
    );
  }
}
