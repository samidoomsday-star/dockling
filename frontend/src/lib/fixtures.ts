import type { Job, Row, Snapshot } from './types';
export const sourceRows: Row[] = [
  {
    id: 'row-a',
    date: '2026-01-02',
    description: 'Fake café, grocery',
    debit: '12.50',
    credit: '',
    balance: '987.50',
    page: 1,
    engine: 'text',
    flags: [],
    fixed: false,
    sourceReviewed: false,
    category: '',
  },
  {
    id: 'row-b',
    date: '2026-01-03',
    description: 'Fake salary',
    debit: '',
    credit: '2000.00',
    balance: '2987.50',
    page: 1,
    engine: 'text',
    flags: [],
    fixed: false,
    sourceReviewed: false,
    category: '',
  },
];
export function makeJob(id = 'sample-review', name = 'January · bank account 1234'): Job {
  return {
    id,
    name,
    status: 'needs_review',
    revision: 1,
    exportRevision: null,
    rows: sourceRows.map((r, i) => ({
      ...r,
      debit: i === 0 ? '12.59' : r.debit,
      flags: i === 0 ? ['BALANCE_DIFFERENCE'] : [],
    })),
    files: [{ name: 'synthetic-january.pdf', pages: 1, kind: 'text' }],
    currency: 'USD',
    dateOrder: 'YMD',
    outputs: ['excel', 'csv'],
    merge: false,
    accountGroup: '',
    accountConfirmed: false,
    categorize: false,
    sourceChecked: false,
    spotNote: '',
    verdict: 'NEEDS_REVIEW',
    aiConsent: false,
    consentNote: '',
    aiPagesUsed: 0,
    aiPageCap: 20,
    deletionPending: false,
    certificate: null,
    history: ['Synthetic fixture loaded; one deliberately changed debit.'],
  };
}
export function initialSnapshot(): Snapshot {
  const ready = makeJob('sample-ready', 'Practice · reconciled statement');
  ready.rows = structuredClone(sourceRows);
  ready.status = 'delivered';
  ready.verdict = 'VERIFIED';
  ready.sourceChecked = true;
  ready.exportRevision = 1;
  ready.accountConfirmed = true;
  ready.accountGroup = 'synthetic-account';
  ready.history = ['Synthetic source comparison recorded.', 'Sample package available.'];
  const scanned = makeJob('sample-scanned', 'Scanned · source comparison');
  scanned.rows = sourceRows.map((r) => ({
    ...r,
    engine: 'ai',
    flags: ['AI_UNTRUSTED', 'SOURCE_CHECK_REQUIRED'],
  }));
  scanned.status = 'needs_review';
  scanned.verdict = 'NEEDS_REVIEW';
  scanned.files = [{ name: 'synthetic-scan.pdf', pages: 1, kind: 'scanned' }];
  scanned.aiPagesUsed = 1;
  return {
    jobs: [
      {
        ...makeJob('sample-failed', 'Processing recovery sample'),
        status: 'failed',
        history: ['Simulated worker interruption. This is a synthetic recovery example.'],
      },
      makeJob(),
      ready,
      scanned,
    ],
    connections: [
      {
        id: 'sample-provider',
        name: 'Example provider',
        url: 'https://provider.example/v1',
        style: 'chat',
        model: 'documented-sample-model',
        effort: 'max',
        models: [
          {
            id: 'documented-sample-model',
            efforts: ['provider_default', 'low', 'high', 'max'],
            source: 'operator_documentation',
            reference: 'Synthetic capability fixture; not a real provider',
          },
          {
            id: 'unknown-capability-model',
            efforts: ['provider_default'],
            source: 'unknown',
            reference: '',
          },
        ],
        terms: false,
        schema: 'prompt_json',
        effortStyle: 'reasoning_effort',
        tokenField: 'max_tokens',
        modelsRoute: '/models',
        completionRoute: '/chat/completions',
        temperature: false,
      },
    ],
    rules: [
      { id: 'rule-1', category: 'Groceries', match: 'grocery', direction: 'debit' },
      { id: 'rule-2', category: 'Income', match: 'salary', direction: 'credit' },
    ],
    settings: {
      currency: 'USD',
      dateFormat: '%m/%d/%Y',
      sourceOrder: 'auto',
      retentionDays: 7,
      outputs: ['excel', 'csv'],
    },
  };
}
