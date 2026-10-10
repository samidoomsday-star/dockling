import { afterEach, describe, expect, it, vi } from 'vitest';
import { FoundationApi, FoundationError, type ServerSession } from '../src/lib/foundation';
const id = 'c1a6e3de-e7fb-4dd2-921f-8c92a32ab8ef';
const session: ServerSession = {
  user_id: id,
  workspace_id: id,
  role: 'editor',
  csrf_token: 'synthetic-csrf',
  platform_admin: false,
  expires_at: '2026-10-10T00:00:00Z',
};
afterEach(() => vi.unstubAllGlobals());
describe('foundation contract adapter', () => {
  it('uses same-origin server session and CSRF without a browser role header', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id }), { status: 201 }));
    vi.stubGlobal('fetch', fetch);
    await new FoundationApi().create(session, 'Synthetic', 'USD');
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe('/api/v1/jobs');
    expect(init.credentials).toBe('same-origin');
    expect(init.headers['X-CSRF-Token']).toBe('synthetic-csrf');
    expect(init.headers['Idempotency-Key']).toBeTruthy();
    expect(JSON.parse(init.body)).not.toHaveProperty('role');
  });
  it('fails with an API error without substituting demo jobs', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            message: 'Please sign in again.',
            code: 'SIGN_IN_REQUIRED',
            request_id: id,
          }),
          { status: 401 },
        ),
      ),
    );
    await expect(new FoundationApi().jobs()).rejects.toEqual(
      new FoundationError(401, 'Please sign in again.'),
    );
  });
  it('rejects malformed records and never displays raw error bodies', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ items: [{ id: 'bad', name: 'fabricated' }], next_cursor: null }),
          ),
        ),
    );
    await expect(new FoundationApi().jobs()).rejects.toThrow();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('private provider trace', { status: 503 })),
    );
    await expect(new FoundationApi().session()).rejects.toThrow(
      'The service is unavailable. Please try again.',
    );
  });
  it('preserves the supplied CSRF through unrelated GET requests', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(session)));
    vi.stubGlobal('fetch', fetch);
    const api = new FoundationApi();
    await api.session();
    fetch.mockResolvedValue(new Response(JSON.stringify({ id }), { status: 201 }));
    await api.create(session, 'Synthetic', 'USD');
    expect(fetch.mock.calls[1][1].headers['X-CSRF-Token']).toBe(session.csrf_token);
  });
});
