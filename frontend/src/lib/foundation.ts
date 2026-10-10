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
  create(session: ServerSession, name: string, currency: string) {
    return this.request(
      '/jobs',
      z.object({ id: uuid }).passthrough(),
      session,
      { name, currency, date_order: 'auto', outputs: ['excel', 'csv'] },
      'POST',
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
