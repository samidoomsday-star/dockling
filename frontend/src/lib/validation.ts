import { z } from 'zod';
import type { Connection, Edit, Effort, Job, NewJob } from './types';
export const exactMoney = z
  .string()
  .refine(
    (s) => s === '' || /^\d+(\.\d{1,2})?$/.test(s),
    'Use a nonnegative exact amount with at most two decimals, or blank.',
  );
const date = z
  .string()
  .refine(
    (s) =>
      /^\d{4}-\d{2}-\d{2}$/.test(s) &&
      !Number.isNaN(Date.parse(s)) &&
      new Date(s).toISOString().slice(0, 10) === s,
    'Use a valid YYYY-MM-DD date.',
  );
export const editSchema = z.object({
  id: z.string(),
  action: z.enum(['fix', 'delete', 'insert_after']),
  date,
  description: z
    .string()
    .trim()
    .min(1, 'A description is required.')
    .refine((s) => !s.startsWith('='), 'Use plain text, not a formula.'),
  debit: exactMoney,
  credit: exactMoney,
  balance: z
    .string()
    .refine(
      (s) => s === '' || /^-?\d+(\.\d{1,2})?$/.test(s),
      'Use an exact signed balance, or blank.',
    ),
  note: z.string(),
});
export function validateEdit(edit: Edit) {
  const value = editSchema.parse(edit);
  if (value.action !== 'delete' && !value.debit && !value.credit)
    throw new Error('A movement amount is required.');
  return value;
}
export function validateNewJob(job: NewJob) {
  if (!job.files.length) throw new Error('Choose a synthetic sample file.');
  if (!/^[A-Z]{3}$/.test(job.currency))
    throw new Error('Choose a three-letter uppercase currency.');
  if (!job.outputs.length) throw new Error('Choose at least one output.');
  if (job.merge && (!job.accountConfirmed || !job.accountGroup.trim()))
    throw new Error('Confirm a private account group before merging.');
  if (job.pages && !/^[1-9]\d*(?:-[1-9]\d*)?(?:,[1-9]\d*(?:-[1-9]\d*)?)*$/.test(job.pages))
    throw new Error('Use page groups such as 1-4,5-9.');
  if (job.pages) {
    let last = 0;
    for (const group of job.pages.split(',')) {
      const [start, end = start] = group.split('-').map(Number);
      if (
        !Number.isSafeInteger(start) ||
        !Number.isSafeInteger(end) ||
        end < start ||
        start <= last
      )
        throw new Error('Page groups must be ordered and non-overlapping.');
      last = end;
    }
  }
  return job;
}
export function highestEffort(efforts: Effort[]): Effort {
  const ranking: Effort[] = [
    'provider_default',
    'minimal',
    'low',
    'medium',
    'high',
    'xhigh',
    'max',
  ];
  return (
    [...efforts].sort((a, b) => ranking.indexOf(b) - ranking.indexOf(a))[0] ?? 'provider_default'
  );
}
export function validateConnection(c: Connection) {
  const url = new URL(c.url);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash)
    throw new Error('Use an HTTPS base URL without credentials, query or fragment.');
  if (!c.name.trim()) throw new Error('Enter a connection nickname.');
  const model = c.models.find((m) => m.id === c.model);
  if (!model || !model.efforts.includes(c.effort))
    throw new Error('Choose an effort supported by this model.');
  if (model.source === 'unknown' && c.effort !== 'provider_default')
    throw new Error('Unknown model capabilities allow provider default only.');
  if (c.effortStyle === 'none' && c.effort !== 'provider_default')
    throw new Error('This adapter does not support an effort parameter.');
  if (!/^\/[A-Za-z0-9_/-]+$/.test(c.completionRoute) || !/^\/[A-Za-z0-9_/-]+$/.test(c.modelsRoute))
    throw new Error('Use relative API routes.');
  return c;
}
export function exportBlock(job: Job): string | null {
  if (job.status === 'closed') return 'This job was removed.';
  if (!['reviewed', 'exported', 'delivered'].includes(job.status))
    return 'Finish the review before preparing exports.';
  if (job.verdict === 'NEEDS_REVIEW') return 'Resolve the flagged rows first.';
  if (job.verdict === 'UNVERIFIABLE')
    return 'An authorized exceptional export requires backend approval.';
  if (job.rows.some((r) => r.engine === 'ai' && !r.sourceReviewed))
    return 'Compare every AI row with its source first.';
  if (job.merge && (!job.accountConfirmed || !job.accountGroup))
    return 'Confirm the account before merging.';
  if (job.outputs.includes('ofx') && !job.accountConfirmed)
    return 'OFX needs confirmed account identity.';
  if (!job.sourceChecked) return 'Complete the source check first.';
  return null;
}
export function errorMessage(error: unknown): string {
  if (error instanceof z.ZodError) return error.issues.map((i) => i.message).join(' ');
  return error instanceof Error ? error.message : 'The action could not finish. Please retry.';
}
