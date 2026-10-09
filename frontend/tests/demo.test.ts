import { describe, it, expect } from 'vitest';
import { DemoApi } from '../src/lib/demo';
import {
  highestEffort,
  validateConnection,
  validateNewJob,
  validateEdit,
  exportBlock,
} from '../src/lib/validation';
import { initialSnapshot } from '../src/lib/fixtures';
import type { Edit, NewJob } from '../src/lib/types';
const fix: Edit = {
  id: 'row-a',
  action: 'fix',
  date: '2026-01-02',
  description: 'Fake café, grocery',
  debit: '12.50',
  credit: '',
  balance: '987.50',
  note: 'Compared the synthetic PDF',
};
const job: NewJob = {
  name: 'Practice',
  files: ['fake.pdf'],
  currency: 'USD',
  dateOrder: 'YMD',
  outputs: ['excel'],
  merge: false,
  accountGroup: '',
  accountConfirmed: false,
  categorize: false,
  combine: false,
  engine: 'auto',
  profile: 'generic',
  pages: '',
};
describe('revision-aware review and export gates', () => {
  it('blocks unresolved rows, then allows correction, source check and export', async () => {
    const api = new DemoApi();
    await expect(api.export('sample-review')).rejects.toThrow('review');
    await api.saveEdits('sample-review', 1, [fix]);
    let current = (await api.snapshot()).jobs.find((j) => j.id === 'sample-review')!;
    expect(current.verdict).toBe('VERIFIED_WITH_FIXES');
    expect(current.revision).toBe(2);
    expect(current.sourceChecked).toBe(false);
    await expect(api.export(current.id)).rejects.toThrow('source check');
    await api.spotcheck(current.id, 2, 'Compared both rows');
    await api.export(current.id);
    current = (await api.snapshot()).jobs.find((j) => j.id === current.id)!;
    expect(current.status).toBe('delivered');
    expect(current.exportRevision).toBe(2);
  });
  it('rejects a stale batch without applying any rows', async () => {
    const api = new DemoApi();
    await api.saveEdits('sample-review', 1, [fix]);
    const before = await api.snapshot();
    await expect(api.saveEdits('sample-review', 1, [{ ...fix, debit: '100' }])).rejects.toThrow(
      'changed',
    );
    expect(await api.snapshot()).toEqual(before);
  });
  it('applies a batch atomically when a later row is missing', async () => {
    const api = new DemoApi();
    const before = await api.snapshot();
    await expect(
      api.saveEdits('sample-review', 1, [fix, { ...fix, id: 'missing' }]),
    ).rejects.toThrow('no longer');
    expect(await api.snapshot()).toEqual(before);
  });
  it('invalidates source checks and old package readiness after edits', async () => {
    const api = new DemoApi();
    await api.saveEdits('sample-review', 1, [fix]);
    await api.spotcheck('sample-review', 2, 'Compared');
    await api.saveEdits('sample-review', 2, [{ ...fix, description: 'Changed description' }]);
    const current = (await api.snapshot()).jobs.find((j) => j.id === 'sample-review')!;
    expect(current.sourceChecked).toBe(false);
    expect(current.exportRevision).toBeNull();
    await expect(api.spotcheck(current.id, 2, 'old')).rejects.toThrow('stale');
  });
  it('accepts exact equivalent decimal strings without floating-point math', async () => {
    const api = new DemoApi();
    await api.saveEdits('sample-review', 1, [{ ...fix, debit: '12.5' }]);
    expect((await api.snapshot()).jobs.find((j) => j.id === 'sample-review')!.verdict).toBe(
      'VERIFIED_WITH_FIXES',
    );
  });
  it.each(['insert_after', 'delete'] as const)(
    'supports %s and reruns fixture checks',
    async (action) => {
      const api = new DemoApi();
      await api.saveEdits('sample-review', 1, [{ ...fix, action }]);
      const current = (await api.snapshot()).jobs.find((j) => j.id === 'sample-review')!;
      expect(current.rows).toHaveLength(action === 'delete' ? 1 : 3);
      expect(current.verdict).toBe('NEEDS_REVIEW');
    },
  );
  it('can clear one amount while preserving a movement', () => {
    expect(validateEdit({ ...fix, debit: '', credit: '12.50' }).debit).toBe('');
    expect(() => validateEdit({ ...fix, debit: '', credit: '' })).toThrow('movement');
  });
  it.each(['12.501', '-12.50', 'NaN', '1e2'])('rejects invalid debit %s', (debit) => {
    expect(() => validateEdit({ ...fix, debit })).toThrow();
  });
  it('rejects invalid calendar dates and formulas', () => {
    expect(() => validateEdit({ ...fix, date: '2026-02-30' })).toThrow('valid');
    expect(() => validateEdit({ ...fix, description: '=SUM(A1)' })).toThrow('plain text');
  });
  it('does not allow AI source confirmation to fabricate a money correction', async () => {
    const api = new DemoApi();
    await expect(api.spotcheck('sample-scanned', 1, 'checked')).rejects.toThrow('AI-derived');
    await api.confirmAiSource('sample-scanned');
    const current = (await api.snapshot()).jobs.find((j) => j.id === 'sample-scanned')!;
    expect(current.rows.every((r) => r.sourceReviewed)).toBe(true);
    expect(current.rows.every((r) => !r.fixed)).toBe(true);
    expect(current.verdict).toBe('VERIFIED');
  });
  it('requires explicit account identity for merge and OFX', () => {
    expect(() => validateNewJob({ ...job, merge: true })).toThrow('account');
    const current = initialSnapshot().jobs.find((j) => j.id === 'sample-ready')!;
    current.outputs = ['ofx'];
    current.accountConfirmed = false;
    expect(exportBlock(current)).toContain('identity');
  });
  it('captures intake and distinguishes fixture processing from real extraction', async () => {
    const api = new DemoApi();
    const created = await api.create(job);
    expect(created.status).toBe('intake_done');
    await api.process(created.id);
    const current = (await api.snapshot()).jobs.find((j) => j.id === created.id)!;
    expect(current.status).toBe('needs_review');
    expect(current.history.at(-1)).toContain('not OCR');
    await expect(api.process(created.id)).rejects.toThrow('already');
  });
  it('recovers an explicitly failed fixture job', async () => {
    const api = new DemoApi();
    await api.process('sample-failed');
    expect((await api.snapshot()).jobs.find((j) => j.id === 'sample-failed')!.status).toBe(
      'needs_review',
    );
  });
  it.each(['3-1', '1-3,2-5', '0', 'a-b'])('rejects invalid page groups %s', (pages) => {
    expect(() => validateNewJob({ ...job, pages })).toThrow();
  });
});
describe('privacy and BYOK configuration', () => {
  it('requires abandonment and confirmation flow for unfinished jobs', async () => {
    const api = new DemoApi();
    await expect(api.close('sample-review', false)).rejects.toThrow('abandonment');
    await api.consent('sample-review', true, 'synthetic permission');
    await api.close('sample-review', true);
    const current = (await api.snapshot()).jobs.find((j) => j.id === 'sample-review')!;
    expect(current.rows).toEqual([]);
    expect(current.files).toEqual([]);
    expect(current.consentNote).toBe('');
    expect(current.aiConsent).toBe(false);
    expect(current.certificate).toContain('not a real deletion certificate');
    await expect(api.saveEdits(current.id, 1, [fix])).rejects.toThrow('removed');
  });
  it('issues no certificate after a partial failure and can retry', async () => {
    const api = new DemoApi();
    await api.close('sample-ready', false, true);
    let current = (await api.snapshot()).jobs.find((j) => j.id === 'sample-ready')!;
    expect(current.deletionPending).toBe(true);
    expect(current.certificate).toBeNull();
    expect(current.rows).toHaveLength(2);
    await api.close(current.id, false, false);
    current = (await api.snapshot()).jobs.find((j) => j.id === current.id)!;
    expect(current.status).toBe('closed');
    expect(current.deletionPending).toBe(false);
  });
  it('requires a consent record and revokes permission without resetting usage', async () => {
    const api = new DemoApi();
    await expect(api.consent('sample-scanned', true, '')).rejects.toThrow('consent');
    await api.consent('sample-scanned', true, 'approved fixture');
    await api.consent('sample-scanned', false, '');
    const current = (await api.snapshot()).jobs.find((j) => j.id === 'sample-scanned')!;
    expect(current.aiConsent).toBe(false);
    expect(current.aiPagesUsed).toBe(1);
  });
  it('selects the highest supported effort including Max only when documented', () => {
    expect(highestEffort(['low', 'max', 'high'])).toBe('max');
    expect(highestEffort(['provider_default'])).toBe('provider_default');
    const c = initialSnapshot().connections[0];
    c.model = 'unknown-capability-model';
    c.effort = 'max';
    expect(() => validateConnection(c)).toThrow('supported');
    c.effort = 'provider_default';
    expect(validateConnection(c)).toEqual(c);
  });
  it.each([
    'http://provider.example/v1',
    'https://key@provider.example/v1',
    'https://provider.example/v1?key=secret',
  ])('rejects unsafe URL %s', (url) => {
    expect(() => validateConnection({ ...initialSnapshot().connections[0], url })).toThrow('HTTPS');
  });
  it('revokes existing consent on connection changes while keeping AI budget usage', async () => {
    const api = new DemoApi();
    await api.consent('sample-scanned', true, 'approved');
    const c = initialSnapshot().connections[0];
    c.effort = 'max';
    await api.saveConnection(c);
    const current = (await api.snapshot()).jobs.find((j) => j.id === 'sample-scanned')!;
    expect(current.aiConsent).toBe(false);
    expect(current.aiPagesUsed).toBe(1);
  });
  it('returns isolated snapshots and resets preview state', async () => {
    const api = new DemoApi();
    const copy = await api.snapshot();
    copy.jobs[0].name = 'bad';
    expect((await api.snapshot()).jobs[0].name).not.toBe('bad');
    await api.close('sample-review', true);
    await api.reset();
    expect((await api.snapshot()).jobs.find((j) => j.id === 'sample-review')!.status).toBe(
      'needs_review',
    );
  });
});
