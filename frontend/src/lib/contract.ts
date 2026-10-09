import { z } from 'zod';
import type { Job, Snapshot } from './types';
const output = z.enum(['excel', 'csv', 'qb_csv3', 'qb_csv4', 'xero_csv', 'ofx']);
const effort = z.enum(['provider_default', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']);
const row = z.object({
  id: z.string(),
  date: z.string(),
  description: z.string(),
  debit: z.string(),
  credit: z.string(),
  balance: z.string(),
  page: z.number().int().positive(),
  engine: z.enum(['text', 'docling', 'ai']),
  flags: z.array(z.string()),
  fixed: z.boolean(),
  sourceReviewed: z.boolean(),
  category: z.string(),
});
const intake = z.object({
  name: z.string(),
  files: z.array(z.string()),
  currency: z.string(),
  dateOrder: z.string(),
  outputs: z.array(output),
  merge: z.boolean(),
  accountGroup: z.string(),
  accountConfirmed: z.boolean(),
  categorize: z.boolean(),
  combine: z.boolean(),
  profile: z.string(),
  engine: z.string(),
  pages: z.string(),
});
export const jobSchema: z.ZodType<Job> = z.object({
  intake: intake.optional(),
  id: z.string(),
  name: z.string(),
  status: z.enum([
    'created',
    'intake_done',
    'extracted',
    'needs_review',
    'reviewed',
    'exported',
    'delivered',
    'closed',
    'failed',
  ]),
  revision: z.number().int().positive(),
  exportRevision: z.number().int().positive().nullable(),
  rows: z.array(row),
  files: z.array(
    z.object({
      name: z.string(),
      pages: z.number().int().nonnegative(),
      kind: z.enum(['text', 'scanned', 'blank']),
    }),
  ),
  currency: z.string(),
  dateOrder: z.string(),
  outputs: z.array(output),
  merge: z.boolean(),
  accountGroup: z.string(),
  accountConfirmed: z.boolean(),
  categorize: z.boolean(),
  sourceChecked: z.boolean(),
  spotNote: z.string(),
  verdict: z.enum([
    'VERIFIED',
    'VERIFIED_BY_TOTALS',
    'VERIFIED_WITH_FIXES',
    'NEEDS_REVIEW',
    'UNVERIFIABLE',
  ]),
  aiConsent: z.boolean(),
  consentNote: z.string(),
  aiPagesUsed: z.number().int().nonnegative(),
  aiPageCap: z.number().int().nonnegative(),
  deletionPending: z.boolean(),
  certificate: z.string().nullable(),
  history: z.array(z.string()),
});
export const snapshotSchema: z.ZodType<Snapshot> = z.object({
  jobs: z.array(jobSchema),
  connections: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      url: z.string(),
      style: z.enum(['chat', 'responses']),
      model: z.string(),
      effort,
      models: z.array(
        z.object({
          id: z.string(),
          efforts: z.array(effort),
          source: z.enum(['unknown', 'operator_documentation', 'provider_metadata']),
          reference: z.string(),
        }),
      ),
      terms: z.boolean(),
      schema: z.enum(['prompt_json', 'json_object', 'json_schema']),
      effortStyle: z.enum(['reasoning_effort', 'reasoning', 'none']),
      tokenField: z.enum(['max_tokens', 'max_completion_tokens', 'max_output_tokens']),
      modelsRoute: z.string(),
      completionRoute: z.string(),
      temperature: z.boolean(),
    }),
  ),
  rules: z.array(
    z.object({
      id: z.string(),
      category: z.string(),
      match: z.string(),
      direction: z.enum(['both', 'debit', 'credit']),
    }),
  ),
  settings: z.object({
    currency: z.string(),
    dateFormat: z.string(),
    sourceOrder: z.string(),
    retentionDays: z.number().int().nonnegative(),
    outputs: z.array(output),
  }),
});
export function parseSnapshot(value: unknown) {
  const parsed = snapshotSchema.safeParse(value);
  if (!parsed.success)
    throw new Error(
      'The backend returned an unsupported workspace format. No sample data was substituted.',
    );
  return parsed.data;
}
