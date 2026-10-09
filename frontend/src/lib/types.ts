export type Role = 'customer' | 'admin';
export type Status =
  | 'created'
  | 'intake_done'
  | 'extracted'
  | 'needs_review'
  | 'reviewed'
  | 'exported'
  | 'delivered'
  | 'closed'
  | 'failed';
export type Output = 'excel' | 'csv' | 'qb_csv3' | 'qb_csv4' | 'xero_csv' | 'ofx';
export type Effort = 'provider_default' | 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';
export type Verdict =
  'VERIFIED' | 'VERIFIED_BY_TOTALS' | 'VERIFIED_WITH_FIXES' | 'NEEDS_REVIEW' | 'UNVERIFIABLE';
export interface Row {
  id: string;
  date: string;
  description: string;
  debit: string;
  credit: string;
  balance: string;
  page: number;
  engine: 'text' | 'docling' | 'ai';
  flags: string[];
  fixed: boolean;
  sourceReviewed: boolean;
  category: string;
}
export interface Job {
  intake?: NewJob;
  id: string;
  name: string;
  status: Status;
  revision: number;
  exportRevision: number | null;
  rows: Row[];
  files: { name: string; pages: number; kind: 'text' | 'scanned' | 'blank' }[];
  currency: string;
  dateOrder: string;
  outputs: Output[];
  merge: boolean;
  accountGroup: string;
  accountConfirmed: boolean;
  categorize: boolean;
  sourceChecked: boolean;
  spotNote: string;
  verdict: Verdict;
  aiConsent: boolean;
  consentNote: string;
  aiPagesUsed: number;
  aiPageCap: number;
  deletionPending: boolean;
  certificate: string | null;
  history: string[];
}
export interface NewJob {
  name: string;
  files: string[];
  currency: string;
  dateOrder: string;
  outputs: Output[];
  merge: boolean;
  accountGroup: string;
  accountConfirmed: boolean;
  categorize: boolean;
  combine: boolean;
  profile: string;
  engine: string;
  pages: string;
}
export interface Edit {
  id: string;
  action: 'fix' | 'delete' | 'insert_after';
  date: string;
  description: string;
  debit: string;
  credit: string;
  balance: string;
  note: string;
}
export interface Model {
  id: string;
  efforts: Effort[];
  source: 'unknown' | 'operator_documentation' | 'provider_metadata';
  reference: string;
}
export interface Connection {
  id: string;
  name: string;
  url: string;
  style: 'chat' | 'responses';
  model: string;
  effort: Effort;
  models: Model[];
  terms: boolean;
  schema: 'prompt_json' | 'json_object' | 'json_schema';
  effortStyle: 'reasoning_effort' | 'reasoning' | 'none';
  tokenField: 'max_tokens' | 'max_completion_tokens' | 'max_output_tokens';
  modelsRoute: string;
  completionRoute: string;
  temperature: boolean;
}
export interface Rule {
  id: string;
  category: string;
  match: string;
  direction: 'both' | 'debit' | 'credit';
}
export interface Settings {
  currency: string;
  dateFormat: string;
  sourceOrder: string;
  retentionDays: number;
  outputs: Output[];
}
export interface Snapshot {
  jobs: Job[];
  connections: Connection[];
  rules: Rule[];
  settings: Settings;
}
export interface Api {
  mode: 'demo' | 'api';
  snapshot(): Promise<Snapshot>;
  create(input: NewJob): Promise<Job>;
  process(id: string): Promise<void>;
  saveEdits(id: string, revision: number, edits: Edit[]): Promise<void>;
  spotcheck(id: string, revision: number, note: string): Promise<void>;
  consent(id: string, grant: boolean, note: string): Promise<void>;
  confirmAiSource(id: string): Promise<void>;
  export(id: string): Promise<void>;
  close(id: string, abandon: boolean, simulatePartial?: boolean): Promise<void>;
  saveConnection(connection: Connection): Promise<void>;
  removeConnection(id: string): Promise<void>;
  saveRules(rules: Rule[]): Promise<void>;
  saveSettings(settings: Settings): Promise<void>;
  reset(): Promise<void>;
}
export const outputs: { id: Output; name: string; detail: string; sample: string }[] = [
  {
    id: 'excel',
    name: 'Excel workbook',
    detail: 'Transactions, Summary and Issues',
    sample: 'sample.xlsx',
  },
  {
    id: 'csv',
    name: 'Generic CSV',
    detail: 'ISO dates, checks and provenance',
    sample: 'sample.csv',
  },
  {
    id: 'qb_csv3',
    name: 'QuickBooks · 3 columns',
    detail: 'Date, Description and Amount',
    sample: 'sample-qb3.csv',
  },
  {
    id: 'qb_csv4',
    name: 'QuickBooks · 4 columns',
    detail: 'Date, Description, Credit and Debit',
    sample: 'sample-qb4.csv',
  },
  {
    id: 'xero_csv',
    name: 'Xero CSV',
    detail: 'Statement import headers',
    sample: 'sample-xero.csv',
  },
  {
    id: 'ofx',
    name: 'Bank/card OFX',
    detail: 'Confirmed identity required; no .qbo',
    sample: 'sample.ofx',
  },
];
export const statusLabels: Record<Status, string> = {
  created: 'Draft',
  intake_done: 'Ready to process',
  extracted: 'Checking',
  needs_review: 'Review needed',
  reviewed: 'Source check / export',
  exported: 'Files generated',
  delivered: 'Package ready',
  closed: 'Data removed',
  failed: 'Needs recovery',
};
export const verdictLabels: Record<Verdict, string> = {
  VERIFIED: 'Numbers reconcile',
  VERIFIED_BY_TOTALS: 'Reconciles by totals',
  VERIFIED_WITH_FIXES: 'Reconciles after corrections',
  NEEDS_REVIEW: 'Differences need review',
  UNVERIFIABLE: 'Not enough evidence',
};
