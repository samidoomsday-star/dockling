import { createApi } from '../src/lib/mode';
import { it, expect, vi } from 'vitest';
import { HttpApi } from '../src/lib/api';
import { initialSnapshot } from '../src/lib/fixtures';
it('never substitutes fixtures for an unavailable API', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('unavailable', { status: 503 })));
  await expect(new HttpApi().snapshot()).rejects.toThrow('No demo results');
  vi.unstubAllGlobals();
});
it('rejects an unauthorized workspace', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 401 })));
  await expect(new HttpApi().snapshot()).rejects.toThrow('Sign-in');
  vi.unstubAllGlobals();
});
it('validates server data and does not accept malformed snapshots', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ jobs: [] }), { status: 200 })),
  );
  await expect(new HttpApi().snapshot()).rejects.toThrow('unsupported workspace');
  vi.unstubAllGlobals();
});
it('requires server CSRF binding before mutations', async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
  await expect(new HttpApi().process('job')).rejects.toThrow('CSRF');
  expect(fetchMock).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});
it('uses same-origin credentials and server-provided CSRF without storing secrets', async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify(initialSnapshot()), {
        headers: { 'X-CSRF-Token': 'fixture-csrf' },
      }),
    )
    .mockResolvedValueOnce(new Response(null, { status: 204 }));
  vi.stubGlobal('fetch', fetchMock);
  const api = new HttpApi();
  await api.snapshot();
  await api.process('id/with slash');
  expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/jobs/id%2Fwith%20slash/process');
  expect(fetchMock.mock.calls[1][1]).toMatchObject({
    credentials: 'same-origin',
    headers: { 'X-CSRF-Token': 'fixture-csrf' },
  });
  expect(localStorage.length).toBe(0);
  vi.unstubAllGlobals();
});

it('rejects an unknown mode instead of falling back to demo', () => {
  expect(() => createApi('production')).toThrow('Unsupported');
  expect(createApi('api').mode).toBe('api');
  expect(createApi('demo').mode).toBe('demo');
});
