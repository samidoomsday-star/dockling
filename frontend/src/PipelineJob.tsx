import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { FoundationApi, FoundationError, type ServerSession } from './lib/foundation';
import ReviewWorkspace, { Correction, PrivacyPanel } from './ReviewWorkspace';
import AiPanel from './AiPanel';
import { JobOwnerTools } from './OwnerOperations';
const api = new FoundationApi();
const explain = (e: unknown) =>
  e instanceof FoundationError ? e.message : 'The service is unavailable. Please try again.';
const human = (value: string) => value.replaceAll('_', ' ').toLowerCase();
export default function PipelineJob({ session, id }: { session: ServerSession; id: string }) {
  const client = useQueryClient();
  const prefix = ['foundation', session.workspace_id, 'job', id];
  const ops = useQuery({
    queryKey: [...prefix, 'operations'],
    queryFn: () => api.operations(id),
    retry: false,
    refetchInterval: (q) =>
      q.state.data?.items.some((o) => ['queued', 'running', 'cancel_requested'].includes(o.state))
        ? 2000
        : false,
  });
  const latest = ops.data?.items[0];
  const running = !!ops.data?.items.some((o) =>
    ['queued', 'running', 'cancel_requested'].includes(o.state),
  );
  const q = useQuery({ queryKey: [...prefix, 'record'], queryFn: () => api.job(id), retry: false });
  const files = useQuery({
    queryKey: [...prefix, 'files'],
    queryFn: () => api.files(id),
    retry: false,
  });
  const statements = useQuery({
    queryKey: [...prefix, 'statements'],
    queryFn: () => api.statements(id),
    retry: false,
  });
  const [cursor, setCursor] = useState<string | null>(null);
  const rows = useQuery({
    queryKey: [...prefix, 'rows', cursor],
    queryFn: () => api.rows(id, cursor),
    retry: false,
  });
  const limits = useQuery({
    queryKey: ['foundation', session.workspace_id, 'intake-options'],
    queryFn: () => api.intakeOptions(),
    retry: false,
  });
  const [selected, setSelected] = useState<File[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [passwords, setPasswords] = useState<Record<string, string>>({});
  const [source, setSource] = useState<{ file: string; page: number } | null>(null);
  const attempts = useRef(new Map<File, { key: string; revision: number }>());
  const fileInput = useRef<HTMLInputElement>(null);
  const sourcePanel = useRef<HTMLElement>(null);
  useEffect(() => {
    if (source) sourcePanel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [source]);
  useEffect(() => {
    setCursor(null);
    void client.invalidateQueries({ queryKey: ['foundation', session.workspace_id, 'job', id] });
  }, [latest?.state, session.workspace_id, id, client]);
  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    setMessage('');
    try {
      await action();
      setCursor(null);
      await client.invalidateQueries({ queryKey: prefix });
    } catch (e) {
      setMessage(explain(e));
    } finally {
      setBusy(false);
    }
  }
  async function upload() {
    if (!confirmed || !selected.length || !q.data || !limits.data) return;
    await act(async () => {
      for (let index = 0; index < selected.length; index++) {
        const file = selected[index];
        if (file.size > limits.data!.upload_bytes)
          throw new FoundationError(413, 'This file exceeds the upload limit.');
        setMessage('Uploading ' + file.name + '…');
        let attempt = attempts.current.get(file);
        if (!attempt) {
          const current = await api.job(id);
          attempt = { key: crypto.randomUUID(), revision: current.revision };
          attempts.current.set(file, attempt);
        }
        await api.upload(session, id, file, attempt.revision, attempt.key);
        attempts.current.delete(file);
        setSelected(selected.slice(index + 1));
      }
      setMessage('Files uploaded. Inspect them before conversion.');
      if (fileInput.current) fileInput.current.value = '';
      setConfirmed(false);
    });
  }
  if (q.isPending) return <p>Opening your job…</p>;
  if (q.isError)
    return (
      <>
        <p role="alert">{explain(q.error)}</p>
        <PrivacyPanel
          session={session}
          id={id}
          refresh={async () => {
            await client.cancelQueries({ queryKey: prefix });
            client.removeQueries({ queryKey: prefix });
          }}
        />
      </>
    );
  const job = q.data;
  const writable = session.role !== 'viewer';
  const canUpload = ['created', 'intake_done'].includes(job.status) && !running;
  return (
    <>
      <div className="page-heading" data-job-revision={job.revision}>
        <div>
          <span className="eyebrow">Your document workspace</span>
          <h1>{job.name}</h1>
          <p>Upload, inspect, then convert. Your source stays available alongside the results.</p>
        </div>
        <Link to="/app/jobs">Back to jobs</Link>
      </div>
      <div className="grid three metrics">
        <section className="card blue">
          <span>Job status</span>
          <strong className="pipeline-status">{human(job.status)}</strong>
        </section>
        <section className="card peach">
          <span>Documents</span>
          <strong>{files.data?.items.length ?? '—'}</strong>
        </section>
        <section className="card mint">
          <span>Inspected pages</span>
          <strong>{files.data?.items.reduce((n, f) => n + f.pages, 0) ?? '—'}</strong>
        </section>
      </div>
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}
      {[files, ops, statements, rows, limits].map((query, index) =>
        query.isError ? (
          <p role="alert" key={index}>
            {explain(query.error)}
          </p>
        ) : null,
      )}
      <section className="card section">
        <h2>1. Add your statements</h2>
        <p>
          PDF, JPEG, PNG or TIFF. This development version accepts synthetic test documents only.
        </p>
        {limits.data && (
          <p className="fine">
            Up to {Math.floor(limits.data.upload_bytes / 1024 / 1024)} MB per file,{' '}
            {limits.data.job_files} files and {limits.data.job_pages} pages per job.
          </p>
        )}
        {writable && canUpload ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void upload();
            }}
          >
            <label>
              Choose statement files
              <input
                type="file"
                ref={fileInput}
                multiple
                accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff"
                disabled={busy}
                onChange={(e) => {
                  attempts.current.clear();
                  setSelected(Array.from(e.target.files ?? []));
                }}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              These are fictional test documents, with no real customer information.
            </label>
            {selected.length > 0 && <p>{selected.length} file(s) selected.</p>}
            <button
              className="button primary"
              disabled={busy || !confirmed || !selected.length || !limits.data}
            >
              Upload files
            </button>
          </form>
        ) : (
          <p>
            {writable
              ? 'Uploads pause during processing and after conversion.'
              : 'Your viewer access can read the documents and results.'}
          </p>
        )}
        {files.data?.items.map((file, index) => (
          <div className="pipeline-file" key={file.id}>
            <div>
              <strong>{file.display_name}</strong>
              <small>
                {file.kind.toUpperCase()} · {Math.ceil(file.bytes / 1024)} KB ·{' '}
                {file.pages ? file.pages + ' inspected page(s)' : 'Awaiting inspection'}
              </small>
              <a href={'/api/v1/jobs/' + id + '/files/' + file.id + '/download'}>
                Download original
              </a>
            </div>
            <div className="actions">
              {file.pages > 0 && (
                <button onClick={() => setSource({ file: file.id, page: 1 })}>View source</button>
              )}
              {writable && canUpload && index > 0 && (
                <button
                  disabled={busy}
                  aria-label={'Move ' + file.display_name + ' up'}
                  onClick={() =>
                    void act(() => {
                      const order = files.data!.items.map((f) => f.id);
                      [order[index - 1], order[index]] = [order[index], order[index - 1]];
                      return api.reorder(session, id, job.revision, order);
                    })
                  }
                >
                  Move up
                </button>
              )}
            </div>
            {file.password_required && writable && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const password = passwords[file.id];
                  setPasswords((v) => ({ ...v, [file.id]: '' }));
                  void act(() => api.unlock(session, id, job.revision, file.id, password));
                }}
              >
                <label>
                  PDF password for {file.display_name}
                  <input
                    type="password"
                    autoComplete="off"
                    required
                    maxLength={512}
                    value={passwords[file.id] ?? ''}
                    onChange={(e) => setPasswords((v) => ({ ...v, [file.id]: e.target.value }))}
                  />
                </label>
                <small>Used once in memory. If the server restarts, enter it again.</small>
                <button disabled={busy || running} className="button secondary">
                  Unlock and continue inspection
                </button>
              </form>
            )}
          </div>
        ))}
        {files.data?.items.length === 0 && <p>No documents uploaded yet.</p>}
      </section>
      <section className="card section">
        <h2>2. Inspect and convert</h2>
        <p>
          Inspection checks document pages first. Conversion then runs the text/OCR engines and
          financial checks.
        </p>
        {writable && (
          <div className="actions">
            <button
              className="button secondary"
              disabled={busy || running || !files.data?.items.length || !canUpload}
              onClick={() => void act(() => api.intake(session, id, job.revision))}
            >
              Inspect documents
            </button>
            <button
              className="button primary"
              disabled={
                busy ||
                running ||
                !['intake_done', 'needs_review', 'extracted'].includes(job.status)
              }
              onClick={() => void act(() => api.convert(session, id, job.revision))}
            >
              Convert statements
            </button>
          </div>
        )}
        {latest ? (
          <div className="notice" role="status">
            <div>
              <strong>
                {human(latest.action)} · {human(latest.state)}
              </strong>
              <p>
                {running
                  ? 'Current stage: ' + human(latest.stage ?? 'queued')
                  : latest.state === 'succeeded'
                    ? 'Finished. The records below reflect this run.'
                    : latest.state === 'awaiting_input'
                      ? 'A document needs its PDF password above.'
                      : latest.state === 'failed'
                        ? 'The run stopped safely. Check the document and retry.'
                        : latest.state === 'cancelled'
                          ? 'Cancelled. This attempt cannot publish results.'
                          : ''}
              </p>
              {latest.pages_done !== null && (
                <small>Pages completed in this attempt: {latest.pages_done}</small>
              )}
              {latest.error_code && latest.state !== 'awaiting_input' && (
                <small>{human(latest.error_code)}</small>
              )}
              {writable && running && (
                <button
                  disabled={busy}
                  onClick={() => void act(() => api.cancel(session, id, job.revision, latest.id))}
                >
                  Cancel operation
                </button>
              )}
              {writable && ['failed', 'cancelled'].includes(latest.state) && (
                <button
                  disabled={busy || running}
                  onClick={() => void act(() => api.retry(session, id, job.revision, latest.id))}
                >
                  Retry operation
                </button>
              )}
            </div>
          </div>
        ) : (
          <p>No processing has started.</p>
        )}
      </section>
      <section className="card section">
        <h2>3. Results and source comparison</h2>
        <p>
          Financial reconciliation checks amounts and balances. Dates and descriptions still require
          source review. Corrections and source confirmation are required before final downloads.
        </p>
        {statements.data?.items.map((s) => (
          <div className="notice" key={s.id}>
            <div>
              <strong>
                Statement {s.id} · {s.rows} rows
              </strong>
              <p>
                Financial verdict: {human(s.verdict)} · Source review:{' '}
                {s.source_checked ? 'sample confirmed' : 'required'}
              </p>
              <details>
                <summary>Financial check details</summary>
                <dl>
                  {Object.entries(s.checks).map(([check, result]) => (
                    <div key={check}>
                      <dt>{human(check)}</dt>
                      <dd>
                        {result === null ? 'Unavailable' : result ? 'Passed' : 'Check required'}
                      </dd>
                    </div>
                  ))}
                </dl>
              </details>
              {s.flags.length > 0 && <small>{s.flags.map(human).join(' · ')}</small>}
            </div>
          </div>
        ))}
        {rows.data?.items.length ? (
          <div
            className="table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Extracted transactions"
          >
            <table>
              <caption className="sr-only">
                Extracted rows, with corrections and links to source pages
              </caption>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Description</th>
                  <th>Debit</th>
                  <th>Credit</th>
                  <th>Balance</th>
                  <th>Source</th>
                  {writable && <th>Correction</th>}
                </tr>
              </thead>
              <tbody>
                {rows.data.items.map((row) => (
                  <tr key={row.statement_id + row.id}>
                    <td>{row.date ?? 'Check date'}</td>
                    <td>
                      {row.description}
                      {row.flags.length > 0 && <small>{row.flags.map(human).join(' · ')}</small>}
                    </td>
                    <td>{row.debit ?? '—'}</td>
                    <td>{row.credit ?? '—'}</td>
                    <td>{row.balance ?? '—'}</td>
                    <td>
                      <button onClick={() => setSource({ file: row.file_id, page: row.page })}>
                        Page {row.page} · {row.engine}
                      </button>
                    </td>
                    {writable && (
                      <td>
                        <Correction
                          key={row.id}
                          row={row}
                          revision={job.revision}
                          disabled={busy || running}
                          save={async (action, changes, expectedRevision) => {
                            await api.editRows(session, id, expectedRevision, [
                              {
                                statement_id: row.statement_id,
                                row_id: row.id,
                                action,
                                ...(changes ? { changes } : {}),
                              },
                            ]);
                            await client.invalidateQueries({ queryKey: prefix });
                          }}
                        />
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>
            {statements.data?.items.length
              ? 'No transaction rows could be extracted. Compare the source and try a suitable profile or engine in a new job.'
              : 'Converted rows will appear here after processing.'}
          </p>
        )}
        {cursor && <button onClick={() => setCursor(null)}>First rows</button>}
        {rows.data?.next_cursor && (
          <button onClick={() => setCursor(rows.data!.next_cursor)}>Next rows</button>
        )}
      </section>
      {!!statements.data?.items.length && (
        <ReviewWorkspace
          key={job.revision}
          session={session}
          job={job}
          running={running || busy}
          act={act}
          showSource={(file, page) => setSource({ file, page })}
        />
      )}
      <AiPanel session={session} id={id} />
      <JobOwnerTools
        session={session}
        job={q.data}
        files={files.data?.items ?? []}
        running={running}
      />
      <PrivacyPanel
        session={session}
        id={id}
        refresh={async () => {
          setSource(null);
          await client.cancelQueries({ queryKey: prefix });
          client.removeQueries({ queryKey: prefix });
          await q.refetch();
        }}
      />
      {source && (
        <section ref={sourcePanel} className="card section">
          <div className="spread">
            <h2>Source page {source.page}</h2>
            <button onClick={() => setSource(null)}>Close source</button>
          </div>
          <img
            className="pipeline-source"
            src={'/api/v1/jobs/' + id + '/files/' + source.file + '/pages/' + source.page}
            alt={'Statement source page ' + source.page}
          />
          <div className="actions">
            <button
              disabled={source.page <= 1}
              onClick={() => setSource({ ...source, page: source.page - 1 })}
            >
              Previous source page
            </button>
            <button
              disabled={
                source.page >= (files.data?.items.find((f) => f.id === source.file)?.pages ?? 0)
              }
              onClick={() => setSource({ ...source, page: source.page + 1 })}
            >
              Next source page
            </button>
          </div>
        </section>
      )}
    </>
  );
}
