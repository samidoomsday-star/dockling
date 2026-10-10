import { useEffect, useState, useId } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  FoundationApi,
  FoundationError,
  type CurrentJob,
  type ServerRow,
  type ServerSession,
} from './lib/foundation';

const api = new FoundationApi();
const unsavedCorrections = new Set<string>();
export const hasUnsavedCorrections = () => unsavedCorrections.size > 0;
const formats = ['excel', 'csv', 'qb_csv3', 'qb_csv4', 'xero_csv', 'ofx'];
const labels: Record<string, string> = {
  excel: 'Excel',
  csv: 'CSV',
  qb_csv3: 'QuickBooks (3 columns)',
  qb_csv4: 'QuickBooks (4 columns)',
  xero_csv: 'Xero',
  ofx: 'OFX',
};
export function Correction({
  row,
  save,
  disabled,
  revision,
}: {
  revision: number;
  row: ServerRow;
  save: (
    action: string,
    changes: Record<string, string | null> | undefined,
    expectedRevision: number,
  ) => Promise<void>;
  disabled: boolean;
}) {
  const editorId = useId();
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState('fix');
  const [draft, setDraft] = useState({
    date: row.date ?? '',
    description: row.description,
    debit: row.debit ?? '',
    credit: row.credit ?? '',
    balance: row.balance ?? '',
  });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [baseline, setBaseline] = useState({ row, revision });
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (!open || saved) return;
    unsavedCorrections.add(editorId);
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    const navigate = (event: MouseEvent) => {
      const target = event.target;
      if (
        target instanceof Element &&
        target.closest('a') &&
        !window.confirm('You have an unsaved correction. Leave this page?')
      )
        event.preventDefault();
    };
    window.addEventListener('beforeunload', warn);
    document.addEventListener('click', navigate, true);
    return () => {
      unsavedCorrections.delete(editorId);
      window.removeEventListener('beforeunload', warn);
      document.removeEventListener('click', navigate, true);
    };
  }, [open, saved, editorId]);
  if (!open)
    return (
      <button
        disabled={disabled}
        onClick={() => {
          setOpen(true);
          setBaseline({ row, revision });
          setDraft({
            date: row.date ?? '',
            description: row.description,
            debit: row.debit ?? '',
            credit: row.credit ?? '',
            balance: row.balance ?? '',
          });
        }}
        aria-label={'Correct ' + row.description}
      >
        Correct
      </button>
    );
  return (
    <form
      className="review-editor"
      onSubmit={(e) => {
        e.preventDefault();
        const changes: Record<string, string | null> = {};
        for (const [field, value] of Object.entries(draft))
          if (
            action === 'insert_after' ||
            value !== (baseline.row[field as keyof typeof draft] ?? '')
          )
            changes[field] = value || null;
        setSaving(true);
        setError('');
        void save(action, action === 'delete' ? undefined : changes, baseline.revision)
          .then(() => {
            setSaved(true);
            setOpen(false);
          })
          .catch((e: unknown) =>
            setError(
              e instanceof FoundationError
                ? e.message
                : 'The correction could not be saved. Your draft is still here.',
            ),
          )
          .finally(() => setSaving(false));
      }}
    >
      <h3>Correct transaction</h3>
      {error && <p role="alert">{error}</p>}
      {baseline.revision !== revision && (
        <p role="alert">
          This job changed while you were editing. Keep a copy of your draft, then discard and
          reopen the current row.
        </p>
      )}
      <label>
        Action
        <select value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="fix">Correct fields</option>
          <option value="insert_after">Add a row after this one</option>
          <option value="delete">Delete this row</option>
        </select>
      </label>
      {action !== 'delete' &&
        Object.entries(draft).map(([field, value]) => (
          <label key={field}>
            {field === 'date'
              ? 'Date (YYYY-MM-DD)'
              : field.charAt(0).toUpperCase() + field.slice(1)}
            <input
              value={value}
              maxLength={field === 'description' ? 2000 : 24}
              onChange={(e) => setDraft({ ...draft, [field]: e.target.value })}
            />
          </label>
        ))}
      <p className="fine">
        Leave an amount blank to clear it. Saving repeats financial checks and requires new source
        review.
      </p>
      <div className="actions">
        <button className="button primary" disabled={disabled || saving}>
          {action === 'delete' ? 'Confirm row deletion' : 'Save correction'}
        </button>
        <button type="button" onClick={() => setOpen(false)}>
          Discard
        </button>
      </div>
    </form>
  );
}
export function PrivacyPanel({
  session,
  id,
  refresh,
}: {
  session: ServerSession;
  id: string;
  refresh: () => Promise<void>;
}) {
  const q = useQuery({
    queryKey: ['foundation', session.workspace_id, 'job', id, 'privacy'],
    queryFn: () => api.privacy(id),
    retry: false,
    refetchInterval: (q) =>
      ['pending', 'partial'].includes(q.state.data?.deletion_state ?? '') ? 2000 : false,
  });
  const [confirm, setConfirm] = useState(false);
  const [abandon, setAbandon] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const p = q.data;
  return (
    <section className="card section peach">
      <h2>Data and privacy</h2>
      <p>
        Removal blocks access immediately. A certificate appears after live files, saved results and
        worker copies are cleared. Backup expiry depends on the hosting policy and has not been set.
      </p>
      {q.isError && <p role="alert">Privacy status could not be loaded.</p>}
      {p && (
        <>
          <p>
            Status: <strong>{p.deletion_state}</strong>
          </p>
          {p.deletion_state === 'pending' && (
            <p role="status">
              Cleanup is queued or running. It may wait for a worker to finish clearing its copies.
            </p>
          )}
          {p.deletion_state === 'partial' && (
            <p role="alert">
              Some cleanup remains. No certificate has been issued. Retry removal to continue.
            </p>
          )}
          {p.certificate && (
            <div className="notice">
              <strong>Live removal verified</strong>
              <p>
                Completed {new Date(p.certificate.completed_at).toLocaleString()}.{' '}
                {p.certificate.object_versions_removed} stored object versions removed.
              </p>
              <a
                download="live-removal-certificate.json"
                href={
                  'data:application/json;charset=utf-8,' +
                  encodeURIComponent(JSON.stringify(p.certificate, null, 2))
                }
              >
                Download certificate
              </a>
            </div>
          )}
          {session.role === 'owner' && ['active', 'partial'].includes(p.deletion_state) && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setBusy(true);
                void api
                  .close(session, id, p.revision, abandon)
                  .then(async () => {
                    setConfirm(false);
                    await refresh();
                    await q.refetch();
                  })
                  .catch((e: unknown) =>
                    setMessage(
                      e instanceof FoundationError ? e.message : 'Removal could not be started.',
                    ),
                  )
                  .finally(() => setBusy(false));
              }}
            >
              <label className="check">
                <input
                  type="checkbox"
                  checked={confirm}
                  onChange={(e) => setConfirm(e.target.checked)}
                />
                I confirm permanent live data removal.
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={abandon}
                  onChange={(e) => setAbandon(e.target.checked)}
                />
                Abandon this job if it has not been delivered.
              </label>
              <button className="button secondary" disabled={!confirm || busy}>
                {' '}
                {p.deletion_state === 'partial' ? 'Retry removal' : 'Remove live data'}
              </button>
            </form>
          )}
        </>
      )}
      {message && <p role="alert">{message}</p>}
    </section>
  );
}
export default function ReviewWorkspace({
  session,
  job,
  running,
  act,
  showSource,
}: {
  session: ServerSession;
  job: CurrentJob;
  running: boolean;
  act: (fn: () => Promise<unknown>) => Promise<void>;
  showSource: (file: string, page: number) => void;
}) {
  const prefix = ['foundation', session.workspace_id, 'job', job.id];
  const sample = useQuery({
    queryKey: [...prefix, 'sample', job.revision],
    queryFn: () => api.sourceCheck(job.id),
    retry: false,
  });
  const ai = useQuery({
    queryKey: [...prefix, 'ai-source', job.revision],
    queryFn: () => api.sourceCheck(job.id, true),
    retry: false,
  });
  const exports = useQuery({
    queryKey: [...prefix, 'exports'],
    queryFn: () => api.workflow(job.id, 'exports'),
    retry: false,
  });
  const books = useQuery({
    queryKey: [...prefix, 'workbooks'],
    queryFn: () => api.workflow(job.id, 'review-workbooks'),
    retry: false,
  });
  const packages = useQuery({
    queryKey: [...prefix, 'delivery'],
    queryFn: () => api.workflow(job.id, 'delivery'),
    retry: false,
  });
  const [viewed, setViewed] = useState<string[]>([]);
  const [outputs, setOutputs] = useState<string[]>(job.options.outputs as string[]);
  const [date, setDate] = useState(String(job.options.output_date_format ?? 'ISO'));
  const [merge, setMerge] = useState(Boolean(job.options.merge));
  const [categorize, setCategorize] = useState(Boolean(job.options.categorize));
  const [group, setGroup] = useState('');
  const [groupConfirmed, setGroupConfirmed] = useState(false);
  const ruleData = useQuery({
    queryKey: [...prefix, 'category-rules'],
    queryFn: () => api.rules(job.id),
    retry: false,
  });
  const [category, setCategory] = useState('');
  const [contains, setContains] = useState('');
  const [direction, setDirection] = useState<'debit' | 'credit' | 'any'>('any');
  const writable = session.role !== 'viewer';
  const disabled = !writable || running;
  const download = (id: string) => '/api/v1/jobs/' + job.id + '/artifacts/' + id + '/download';
  return (
    <>
      <section className="card section mint">
        <h2>4. Compare with the source</h2>
        <p>
          Compare each listed row’s date, description and amounts with its source page. The sample
          includes every corrected row. Financial checks alone cannot confirm the text.
        </p>
        {[sample, ai].map((q, index) => (
          <div key={index}>
            {index === 1 && q.data?.items.length ? <h3>All AI-produced rows</h3> : null}
            {q.isError && <p role="alert">Source-check rows could not be loaded.</p>}
            {q.data?.items.map((r) => (
              <div className="source-review-item" key={r.id}>
                <button onClick={() => showSource(r.file_id, r.page)}>
                  Open source page {r.page}
                </button>
                <p>
                  <strong>{r.date ?? 'Missing date'}</strong> · {r.description}
                </p>
                <small>
                  Debit {r.debit ?? '—'} · Credit {r.credit ?? '—'} · Balance {r.balance ?? '—'}
                </small>
                <label className="check">
                  <input
                    type="checkbox"
                    disabled={disabled}
                    checked={viewed.includes(r.id + index)}
                    onChange={(e) =>
                      setViewed(
                        e.target.checked
                          ? [...viewed, r.id + index]
                          : viewed.filter((v) => v !== r.id + index),
                      )
                    }
                  />
                  I compared this row with the source.
                </label>
              </div>
            ))}
            {q.data && (index === 0 || q.data.items.length > 0) && (
              <div className="actions">
                <button
                  className="button primary"
                  disabled={disabled || !q.data.row_ids.every((r) => viewed.includes(r + index))}
                  onClick={() =>
                    void act(() =>
                      api.confirmSource(
                        session,
                        job.id,
                        job.revision,
                        q.data!.row_ids,
                        true,
                        index === 1,
                      ),
                    )
                  }
                >
                  {q.data.passed ? 'Source check recorded' : 'Confirm source check'}
                </button>
                <button
                  disabled={disabled}
                  onClick={() =>
                    void act(() =>
                      api.confirmSource(
                        session,
                        job.id,
                        job.revision,
                        q.data!.row_ids,
                        false,
                        index === 1,
                      ),
                    )
                  }
                >
                  Source does not match
                </button>
              </div>
            )}
          </div>
        ))}
      </section>
      <section className="card section blue">
        <h2>5. Prepare your downloads</h2>
        <p>
          Choose your formats. All files are generated from your current reviewed data, with
          verified hashes.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void act(() =>
              api.outputOptions(session, job.id, job.revision, {
                outputs,
                output_date_format: date,
                merge,
                categorize,
              }),
            );
          }}
        >
          <fieldset disabled={disabled}>
            <legend>File formats</legend>
            <div className="grid three">
              {formats.map((format) => (
                <label className="check" key={format}>
                  <input
                    type="checkbox"
                    checked={outputs.includes(format)}
                    onChange={(e) =>
                      setOutputs(
                        e.target.checked
                          ? [...outputs, format]
                          : outputs.filter((f) => f !== format),
                      )
                    }
                  />
                  {labels[format]}
                </label>
              ))}
            </div>
            <label>
              Import date format
              <select
                aria-label="Import date format"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              >
                <option value="ISO">YYYY-MM-DD</option>
                <option value="MM/DD/YYYY">MM/DD/YYYY</option>
                <option value="DD/MM/YYYY">DD/MM/YYYY</option>
              </select>
            </label>
            <label className="check">
              <input type="checkbox" checked={merge} onChange={(e) => setMerge(e.target.checked)} />
              Include monthly merged workbook (one account with continuous periods).
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={categorize}
                onChange={(e) => setCategorize(e.target.checked)}
              />
              Apply category rules.
            </label>
            <button disabled={!outputs.length}>Save download options</button>
          </fieldset>
        </form>
        <details>
          <summary>Account confirmation for OFX and merging</summary>
          <p>
            Only group statements that belong to one account. Known conflicting account identities
            remain blocked.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void act(() => api.accountGroup(session, job.id, job.revision, group));
            }}
          >
            <label>
              Your private account label
              <input
                disabled={disabled}
                value={group}
                maxLength={100}
                onChange={(e) => setGroup(e.target.value)}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={groupConfirmed}
                onChange={(e) => setGroupConfirmed(e.target.checked)}
              />
              I checked that these statements belong to the same account.
            </label>
            <button disabled={disabled || !group.trim() || !groupConfirmed}>Confirm account</button>
          </form>
        </details>
        <div className="actions">
          <button
            className="button primary"
            disabled={
              disabled || !sample.data?.passed || (ai.data?.items.length ? !ai.data.passed : false)
            }
            onClick={() => void act(() => api.prepare(session, job.id, 'exports', job.revision))}
          >
            Generate downloads
          </button>
          <button
            className="button secondary"
            disabled={disabled || !exports.data?.items.length}
            onClick={() => void act(() => api.prepare(session, job.id, 'delivery', job.revision))}
          >
            Prepare delivery ZIP
          </button>
        </div>
        {[exports, packages].map((q, i) => (
          <div key={i}>
            {q.isError && <p role="alert">Downloads could not be loaded.</p>}
            {q.data?.items.map((item) => (
              <div className="pipeline-file" key={item.id}>
                <a className="button secondary" href={download(item.id)}>
                  Download {item.name}
                </a>
                <small>
                  {Math.ceil(item.bytes / 1024)} KB · Current revision {q.data!.revision}
                </small>
              </div>
            ))}
          </div>
        ))}
      </section>
      <section className="card section">
        <details>
          <summary>Advanced: Excel review and categories</summary>
          <p>
            Download a review workbook, change the Fix columns and choose an Action, then upload it
            here. Use “clear” to remove an amount. Old workbooks are rejected after corrections.
          </p>
          <button
            disabled={disabled}
            onClick={() =>
              void act(() => api.prepare(session, job.id, 'review-workbooks', job.revision))
            }
          >
            Generate Excel review workbooks
          </button>
          {books.data?.items.map((b) => (
            <div className="pipeline-file" key={b.id}>
              <a href={download(b.id)}>Download {b.name}</a>
              <label>
                Apply edited {b.name}
                <input
                  type="file"
                  accept=".xlsx"
                  disabled={disabled}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file)
                      void act(() => api.applyWorkbook(session, job.id, b.id, job.revision, file));
                    e.target.value = '';
                  }}
                />
              </label>
            </div>
          ))}
          <h3>Job category rules</h3>
          <p>
            Rules match description text in order. Job rules run before your workspace defaults.
          </p>
          {ruleData.isError && <p role="alert">Category rules could not be loaded.</p>}
          <ol>
            {ruleData.data?.rules.map((r, index) => (
              <li key={index}>
                <strong>{r.category}</strong> · contains {r.match.join(', ')} · {r.direction}
                <button
                  disabled={disabled || index === 0}
                  aria-label={'Move ' + r.category + ' up'}
                  onClick={() =>
                    void act(() => {
                      const next = [...ruleData.data!.rules];
                      [next[index - 1], next[index]] = [next[index], next[index - 1]];
                      return api.saveRules(session, job.id, job.revision, next);
                    })
                  }
                >
                  Move up
                </button>
                <button
                  disabled={disabled}
                  aria-label={'Remove ' + r.category + ' rule'}
                  onClick={() =>
                    void act(() =>
                      api.saveRules(
                        session,
                        job.id,
                        job.revision,
                        ruleData.data!.rules.filter((_, i) => i !== index),
                      ),
                    )
                  }
                >
                  Remove
                </button>
              </li>
            ))}
          </ol>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void act(() =>
                api.saveRules(session, job.id, job.revision, [
                  ...(ruleData.data?.rules ?? []),
                  { category, match: [contains], direction },
                ]),
              );
            }}
          >
            <label>
              Category name
              <input
                value={category}
                maxLength={80}
                required
                disabled={disabled}
                onChange={(e) => setCategory(e.target.value)}
              />
            </label>
            <label>
              Description contains
              <input
                value={contains}
                maxLength={120}
                required
                disabled={disabled}
                onChange={(e) => setContains(e.target.value)}
              />
            </label>
            <label>
              Apply to
              <select
                value={direction}
                disabled={disabled}
                onChange={(e) => setDirection(e.target.value as 'debit' | 'credit' | 'any')}
              >
                <option value="any">All transactions</option>
                <option value="debit">Spending (debits)</option>
                <option value="credit">Income (credits)</option>
              </select>
            </label>
            <button disabled={disabled || !ruleData.data}>Add category rule</button>
          </form>
        </details>
      </section>
    </>
  );
}
