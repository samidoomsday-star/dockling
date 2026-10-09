import { initialSnapshot, makeJob, sourceRows } from './fixtures';
import { exportBlock, validateConnection, validateEdit, validateNewJob } from './validation';
import type { Api, Connection, Edit, Job, NewJob, Rule, Settings } from './types';
function canonical(value: string) {
  if (!value) return '';
  const [integer, fraction = ''] = value.split('.');
  return integer.replace(/^(-?)0+(?=\d)/, '$1') + '.' + fraction.padEnd(2, '0');
}
export class DemoApi implements Api {
  mode = 'demo' as const;
  private data = initialSnapshot();
  async snapshot() {
    return structuredClone(this.data);
  }
  private job(id: string) {
    const job = this.data.jobs.find((j) => j.id === id);
    if (!job) throw new Error('Conversion not found.');
    if (job.status === 'closed') throw new Error('The sample data has already been removed.');
    return job;
  }
  private revised(job: Job, note: string) {
    job.revision++;
    job.exportRevision = null;
    job.sourceChecked = false;
    job.history.push(note);
  }
  private compare(job: Job) {
    const correct =
      job.rows.length === sourceRows.length &&
      job.rows.every(
        (r, i) =>
          canonical(r.debit) === canonical(sourceRows[i]?.debit ?? '') &&
          canonical(r.credit) === canonical(sourceRows[i]?.credit ?? '') &&
          canonical(r.balance) === canonical(sourceRows[i]?.balance ?? ''),
      );
    job.rows.forEach((r, i) => {
      r.flags = r.flags.filter((f) => f !== 'BALANCE_DIFFERENCE');
      if (!correct && i === 0) r.flags.push('BALANCE_DIFFERENCE');
    });
    job.verdict = correct
      ? job.rows.some((r) => r.fixed)
        ? 'VERIFIED_WITH_FIXES'
        : 'VERIFIED'
      : 'NEEDS_REVIEW';
    job.status = correct ? 'reviewed' : 'needs_review';
    if (job.rows.some((r) => r.engine === 'ai' && !r.sourceReviewed)) {
      job.verdict = 'NEEDS_REVIEW';
      job.status = 'needs_review';
    }
  }
  async create(input: NewJob) {
    validateNewJob(input);
    const job = makeJob(crypto.randomUUID(), input.name.trim() || 'New practice conversion');
    Object.assign(job, {
      status: 'intake_done',
      intake: structuredClone(input),
      currency: input.currency,
      dateOrder: input.dateOrder,
      outputs: input.outputs,
      merge: input.merge,
      accountGroup: input.accountGroup,
      accountConfirmed: input.accountConfirmed,
      categorize: input.categorize,
      files: input.files.map((name) => ({ name, pages: 1, kind: 'text' })),
      history: ['Preview files selected. Content was not uploaded or extracted.'],
    });
    this.data.jobs.unshift(job);
    return structuredClone(job);
  }
  async process(id: string) {
    const j = this.job(id);
    if (j.status === 'failed') {
      j.status = 'intake_done';
    }
    if (!['intake_done', 'created'].includes(j.status))
      throw new Error('This preview conversion has already been processed.');
    j.status = 'needs_review';
    j.history.push('Synthetic fixture applied. This is not OCR of the selected file.');
  }
  async saveEdits(id: string, revision: number, edits: Edit[]) {
    const j = this.job(id);
    if (j.revision !== revision)
      throw new Error('Rows changed after you opened the editor. Reload before saving.');
    if (!['needs_review', 'reviewed'].includes(j.status))
      throw new Error('Open a reviewable job before editing.');
    const validated = edits.map(validateEdit);
    const rows = structuredClone(j.rows);
    for (const e of validated) {
      const i = rows.findIndex((r) => r.id === e.id);
      if (i < 0) throw new Error('That source row no longer exists.');
      if (e.action === 'delete') {
        rows.splice(i, 1);
        continue;
      }
      const next = {
        ...rows[i],
        date: e.date,
        description: e.description,
        debit: e.debit,
        credit: e.credit,
        balance: e.balance,
        fixed: true,
        sourceReviewed: false,
      };
      if (e.action === 'insert_after') rows.splice(i + 1, 0, { ...next, id: crypto.randomUUID() });
      else rows[i] = next;
    }
    j.rows = rows;
    this.revised(
      j,
      'Staged preview edits applied; fixture comparison rerun. ' +
        edits.map((e) => e.action + ': ' + e.note).join('; '),
    );
    this.compare(j);
  }
  async spotcheck(id: string, revision: number, note: string) {
    const j = this.job(id);
    if (j.revision !== revision)
      throw new Error('The source check is stale. Compare the current rows again.');
    if (!note.trim()) throw new Error('Add a source-check note.');
    if (j.rows.some((r) => r.engine === 'ai' && !r.sourceReviewed))
      throw new Error('Confirm every AI-derived row before the sample spot-check.');
    j.sourceChecked = true;
    j.spotNote = note;
    j.history.push('Sample source comparison acknowledged at revision ' + revision);
  }
  async consent(id: string, grant: boolean, note: string) {
    if (grant && !note.trim()) throw new Error('Record where and when consent was given.');
    const j = this.job(id);
    j.aiConsent = grant;
    j.consentNote = grant ? note : '';
    j.history.push(
      grant ? 'Preview consent recorded; no model was contacted.' : 'Preview consent revoked.',
    );
  }
  async confirmAiSource(id: string) {
    const j = this.job(id);
    j.rows = j.rows.map((r) =>
      r.engine === 'ai'
        ? {
            ...r,
            sourceReviewed: true,
            flags: r.flags.filter((f) => f !== 'AI_UNTRUSTED' && f !== 'SOURCE_CHECK_REQUIRED'),
          }
        : r,
    );
    this.revised(j, 'AI source confirmation recorded separately from money fixes.');
    this.compare(j);
  }
  async export(id: string) {
    const j = this.job(id);
    const blocked = exportBlock(j);
    if (blocked) throw new Error(blocked);
    j.exportRevision = j.revision;
    j.status = 'delivered';
    j.history.push('Preview package ready. Bundled samples remain fixed reference files.');
  }
  async close(id: string, abandon: boolean, simulatePartial = false) {
    const j = this.job(id);
    if (j.status !== 'delivered' && !abandon)
      throw new Error('Confirm abandonment to remove an unfinished sample job.');
    if (simulatePartial) {
      j.deletionPending = true;
      j.certificate = null;
      j.history.push('Simulated locked artifact: no certificate issued.');
      return;
    }
    j.status = 'closed';
    delete j.intake;
    j.deletionPending = false;
    j.rows = [];
    j.files = [];
    j.name = 'Removed conversion';
    j.consentNote = '';
    j.aiConsent = false;
    j.accountConfirmed = false;
    j.accountGroup = '';
    j.spotNote = '';
    j.history = ['Preview job scrubbed. No physical disk or backup deletion is certified.'];
    j.certificate =
      'Synthetic preview: sample job data removed from this in-memory session. This is not a real deletion certificate.';
  }
  async saveConnection(connection: Connection) {
    validateConnection(connection);
    this.data.connections = this.data.connections.filter((c) => c.id !== connection.id);
    this.data.connections.push(structuredClone(connection));
    for (const job of this.data.jobs) {
      job.aiConsent = false;
      job.consentNote = '';
    }
  }
  async removeConnection(id: string) {
    this.data.connections = this.data.connections.filter((c) => c.id !== id);
    for (const job of this.data.jobs) {
      job.aiConsent = false;
      job.consentNote = '';
    }
  }
  async saveRules(rules: Rule[]) {
    if (rules.some((r) => !r.category.trim() || !r.match.trim()))
      throw new Error('Each rule needs a category and match.');
    this.data.rules = structuredClone(rules);
  }
  async saveSettings(settings: Settings) {
    if (
      !/^[A-Z]{3}$/.test(settings.currency) ||
      !Number.isInteger(settings.retentionDays) ||
      settings.retentionDays < 0 ||
      settings.retentionDays > 365 ||
      !settings.outputs.length
    )
      throw new Error('Check currency, retention and outputs.');
    this.data.settings = structuredClone(settings);
  }
  async reset() {
    this.data = initialSnapshot();
  }
}
