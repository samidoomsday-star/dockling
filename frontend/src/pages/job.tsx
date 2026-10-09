import { useEffect, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import * as Tabs from '@radix-ui/react-tabs';
import { Pencil, Download, CheckCircle2, Trash2, FileText } from 'lucide-react';
import { Badge, Button, Card, Check, Empty, Field, Heading, Modal, Notice } from '../components/ui';
import { useAction, useSnapshot, useWorkspace } from '../lib/workspace';
import { outputs, statusLabels, verdictLabels, type Edit, type Job, type Row } from '../lib/types';
import { errorMessage, exportBlock, validateEdit } from '../lib/validation';
import { sourceRows } from '../lib/fixtures';
export function JobPage() {
  const { id } = useParams();
  const { data } = useSnapshot();
  const job = data?.jobs.find((j) => j.id === id);
  if (!job)
    return (
      <Empty title="Conversion not found">
        <Link to="/app/jobs">Back to conversions</Link>
      </Empty>
    );
  return <JobWorkspace key={job.id} job={job} />;
}
function JobWorkspace({ job }: { job: Job }) {
  const { api } = useWorkspace();
  const { run, busy } = useAction();
  const [tab, setTab] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('tab');
    return ['overview', 'review', 'checks', 'exports', 'files', 'ai', 'activity', 'data'].includes(
      requested ?? '',
    )
      ? requested!
      : 'review';
  });
  const [dirty, setDirty] = useState(false);
  const [nextTab, setNextTab] = useState<string | null>(null);
  function changeTab(value: string) {
    if (dirty) {
      setNextTab(value);
      return;
    }
    setTab(value);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', value);
    window.history.replaceState(null, '', url);
  }
  const closed = job.status === 'closed';
  return (
    <>
      <Link className="back-link" to="/app/jobs">
        ← All conversions
      </Link>
      <Heading
        eyebrow={closed ? 'Data removed' : 'Synthetic statement workspace'}
        title={job.name}
        actions={
          <Badge tone={job.status === 'needs_review' ? 'peach' : 'mint'}>
            {statusLabels[job.status]}
          </Badge>
        }
      >
        {closed
          ? 'The preview data has been scrubbed.'
          : `${job.currency} · ${job.files.length} file(s) · revision ${job.revision}`}
      </Heading>
      {closed ? (
        <Card>
          <h2>Removal record</h2>
          <Notice tone="success">{job.certificate}</Notice>
          <p>No source content, row descriptions or consent notes remain in this preview job.</p>
        </Card>
      ) : (
        <>
          {['intake_done', 'created', 'failed'].includes(job.status) ? (
            <Card>
              <h2>
                {job.status === 'failed'
                  ? 'Recover this conversion'
                  : 'Your practice conversion is ready'}
              </h2>
              <p>
                Start the synthetic workflow to explore review. The selected file is not uploaded or
                converted.
              </p>
              <Button
                disabled={busy}
                onClick={() =>
                  void run(() => api.process(job.id), 'Synthetic rows are ready for review.')
                }
              >
                {job.status === 'failed'
                  ? 'Retry practice processing'
                  : 'Start practice processing'}
              </Button>
            </Card>
          ) : null}
          <Notice tone={job.verdict === 'NEEDS_REVIEW' ? 'warning' : 'success'}>
            <strong>{verdictLabels[job.verdict]}.</strong>{' '}
            {job.verdict === 'NEEDS_REVIEW'
              ? 'Resolve differences and confirm source-derived information.'
              : 'This fixture check concerns amounts. Check dates and descriptions against the source separately.'}
          </Notice>
          <Tabs.Root value={tab} onValueChange={changeTab}>
            <Tabs.List className="tabs" aria-label="Conversion sections">
              {[
                ['overview', 'Overview'],
                ['review', 'Review'],
                ['checks', 'Checks'],
                ['exports', 'Exports'],
                ['files', 'Files & intake'],
                ['ai', 'Optional AI'],
                ['activity', 'Activity'],
                ['data', 'Data & privacy'],
              ].map(([value, label]) => (
                <Tabs.Trigger key={value} value={value}>
                  {label}
                </Tabs.Trigger>
              ))}
            </Tabs.List>
            <Tabs.Content value="overview">
              <Card>
                <h2>Conversion overview</h2>
                <p>
                  One synthetic January statement, two transactions and a page-level source
                  reference. Real processing status, per-page diagnostics and quotes require the
                  API/worker.
                </p>
                <dl className="facts">
                  <dt>Status</dt>
                  <dd>{statusLabels[job.status]}</dd>
                  <dt>Financial evidence</dt>
                  <dd>{verdictLabels[job.verdict]}</dd>
                  <dt>Source check</dt>
                  <dd>{job.sourceChecked ? 'Current' : 'Pending'}</dd>
                  <dt>Retention</dt>
                  <dd>Preview resets on reload; production reminders need server timestamps</dd>
                </dl>
                <Button variant="secondary" onClick={() => changeTab('review')}>
                  Open transaction review
                </Button>
              </Card>
            </Tabs.Content>
            <Tabs.Content value="review">
              <Review job={job} onDirty={setDirty} onChecks={() => changeTab('checks')} />
            </Tabs.Content>
            <Tabs.Content value="checks">
              <Checks key={job.revision} job={job} />
            </Tabs.Content>
            <Tabs.Content value="exports">
              <Exports job={job} />
            </Tabs.Content>
            <Tabs.Content value="files">
              <Files job={job} />
            </Tabs.Content>
            <Tabs.Content value="ai">
              <Ai job={job} />
            </Tabs.Content>
            <Tabs.Content value="activity">
              <Card>
                <h2>Revision history</h2>
                <p className="muted">
                  Preview history is session-only; the backend will record authenticated actors and
                  timestamps.
                </p>
                <ol className="timeline">
                  {job.history.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ol>
                <p>
                  Current revision: {job.revision}. Export revision:{' '}
                  {job.exportRevision ?? 'not generated'}.
                </p>
              </Card>
            </Tabs.Content>
            <Tabs.Content value="data">
              <DataPrivacy job={job} />
            </Tabs.Content>
          </Tabs.Root>
          <Modal
            open={nextTab !== null}
            onOpenChange={(open) => {
              if (!open) setNextTab(null);
            }}
            title="Discard staged changes?"
            description="Your unsaved corrections will be lost when you leave Review."
          >
            <Button
              variant="danger"
              onClick={() => {
                setDirty(false);
                if (nextTab) {
                  setTab(nextTab);
                  setNextTab(null);
                }
              }}
            >
              Discard and continue
            </Button>
          </Modal>
        </>
      )}
    </>
  );
}
function Source() {
  return (
    <Card className="source-panel">
      <div className="spread">
        <h2>Statement source</h2>
        <Badge tone="blue">Page 1 · fictional</Badge>
      </div>
      <div className="paper">
        <span className="eyebrow">SAMPLE BANK · NOT A REAL STATEMENT</span>
        <h3>January 2026</h3>
        <p>
          Account ending 1234 · USD
          <br />
          Opening balance: 1,000.00
        </p>
        <p className="mobile-hint">Swipe the table to see every column.</p>
        <div
          className="table-scroll"
          tabIndex={0}
          role="region"
          aria-label="Source statement table"
        >
          <table>
            <caption className="sr-only">True values in the synthetic source</caption>
            <thead>
              <tr>
                <th>Date</th>
                <th>Transaction</th>
                <th>Debit</th>
                <th>Credit</th>
                <th>Balance</th>
              </tr>
            </thead>
            <tbody>
              {sourceRows.map((r) => (
                <tr key={r.id}>
                  <td>{r.date}</td>
                  <td>{r.description}</td>
                  <td>{r.debit || '—'}</td>
                  <td>{r.credit || '—'}</td>
                  <td>{r.balance}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>Closing balance: 2,987.50</p>
        <small>Rendered source fixture. No OCR bounding boxes are available.</small>
      </div>
      <a
        className="text-link"
        href="/samples/synthetic-january.pdf"
        target="_blank"
        rel="noreferrer"
      >
        Open the matching sample PDF ↗
      </a>
    </Card>
  );
}
function Review({
  job,
  onChecks,
  onDirty,
}: {
  job: Job;
  onChecks: () => void;
  onDirty: (dirty: boolean) => void;
}) {
  const { api } = useWorkspace();
  const { run, busy } = useAction();
  const [edits, setEdits] = useState<Edit[]>([]);
  const [editing, setEditing] = useState<Edit | null>(null);
  const [editError, setEditError] = useState('');
  const [openedRevision, setOpenedRevision] = useState(job.revision);
  const canEdit = ['needs_review', 'reviewed'].includes(job.status);
  useEffect(() => {
    onDirty(edits.length > 0);
  }, [edits.length, onDirty]);
  useEffect(() => {
    if (!edits.length) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    const navigate = (event: MouseEvent) => {
      if (
        event.target instanceof Element &&
        event.target.closest('a[href]') &&
        !window.confirm('Discard unsaved staged changes and leave this review?')
      ) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener('beforeunload', warn);
    document.addEventListener('click', navigate, true);
    return () => {
      window.removeEventListener('beforeunload', warn);
      document.removeEventListener('click', navigate, true);
    };
  }, [edits.length]);
  function open(row: Row) {
    if (!edits.length) setOpenedRevision(job.revision);
    setEditing({
      id: row.id,
      action: 'fix',
      date: row.date,
      description: row.description,
      debit: row.debit,
      credit: row.credit,
      balance: row.balance,
      note: '',
    });
    setEditError('');
  }
  function stage(e: FormEvent) {
    e.preventDefault();
    if (!editing) return;
    try {
      validateEdit(editing);
      setEdits((prev) => [...prev.filter((p) => p.id !== editing.id), editing]);
      setEditing(null);
    } catch (e) {
      setEditError(errorMessage(e));
    }
  }
  return (
    <>
      <div className="review-top">
        <div>
          <h2>Compare the source. Keep the detail.</h2>
          <p>Fix the café debit from 12.59 to 12.50, then save and continue to source checks.</p>
        </div>
        <Button variant="secondary" onClick={onChecks}>
          Continue to checks →
        </Button>
      </div>
      <div className="review-grid">
        <Source />
        <Card className="rows-panel">
          <div className="spread">
            <h2>Transaction rows</h2>
            <Badge>{job.rows.length} rows</Badge>
          </div>
          <p className="fine">
            Amounts stay exact text in this UI. The real financial checks belong to the Python
            backend.
          </p>
          <p className="mobile-hint">Swipe for all amounts; choose the pencil to edit.</p>
          <div
            className="table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Transaction review table"
          >
            <table>
              <caption className="sr-only">Extracted sample transaction rows</caption>
              <thead>
                <tr>
                  <th>Date / details</th>
                  <th>Debit</th>
                  <th>Credit</th>
                  <th>Balance</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {job.rows.map((r) => (
                  <tr key={r.id} className={r.flags.length ? 'flagged' : ''}>
                    <td>
                      <strong>{r.date}</strong>
                      <span>{r.description}</span>
                      <small>
                        Page {r.page} · {r.engine}
                        {r.fixed ? ' · corrected' : ''}
                      </small>
                      {r.flags.map((f) => (
                        <Badge tone="peach" key={f}>
                          {f.replaceAll('_', ' ').toLowerCase()}
                        </Badge>
                      ))}
                    </td>
                    <td>{r.debit || '—'}</td>
                    <td>{r.credit || '—'}</td>
                    <td>{r.balance || '—'}</td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={'Edit ' + r.description}
                        disabled={!canEdit}
                        onClick={() => open(r)}
                      >
                        <Pencil size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!canEdit && <p className="fine">Editing is available during the review stage.</p>}
          <div className="review-summary">
            <span>
              <CheckCircle2 size={17} /> Source check: {job.sourceChecked ? 'current' : 'pending'}
            </span>
            <span>Revision {job.revision}</span>
          </div>
        </Card>
      </div>
      {edits.length > 0 && (
        <Card className="staged">
          <h2>{edits.length} staged change(s)</h2>
          <p>
            No rows change until you save this batch. Saving invalidates previous source checks and
            exports.
          </p>
          <ul>
            {edits.map((e) => (
              <li key={e.id}>
                {e.action} · {e.description} · debit {e.debit || 'blank'} / credit{' '}
                {e.credit || 'blank'}
              </li>
            ))}
          </ul>
          <div className="actions">
            <Button
              disabled={busy}
              onClick={() =>
                void run(
                  () => api.saveEdits(job.id, openedRevision, edits),
                  'Changes saved; compare the current revision with the source.',
                ).then((ok) => {
                  if (ok) setEdits([]);
                })
              }
            >
              Save staged changes
            </Button>
            <Button variant="secondary" onClick={() => setEdits([])}>
              Discard staged changes
            </Button>
          </div>
        </Card>
      )}
      <details>
        <summary>Prefer Excel review?</summary>
        <p>
          The existing CLI generates a review workbook and applies fix/delete/insert_after actions
          with revision checks. Hosted workbook import requires the backend; this preview cannot
          apply a file.
        </p>
        <code>stmtconv review --help</code>
        <p>Blank money fields clear their value; a movement still needs a debit or credit.</p>
      </details>
      <Modal
        open={!!editing}
        onOpenChange={(open) => {
          if (!open) setEditing(null);
        }}
        title="Edit transaction"
        description="Stage a precise correction, insertion or deletion. Save the batch afterwards."
      >
        {editing && (
          <form onSubmit={stage}>
            <Field label="Action">
              <select
                value={editing.action}
                onChange={(e) =>
                  setEditing({ ...editing, action: e.target.value as Edit['action'] })
                }
              >
                <option value="fix">Correct this row</option>
                <option value="insert_after">Insert a new row after this one</option>
                <option value="delete">Delete this row</option>
              </select>
            </Field>
            <div className="grid two">
              <Field label="Date (YYYY-MM-DD)">
                <input
                  value={editing.date}
                  onChange={(e) => setEditing({ ...editing, date: e.target.value })}
                />
              </Field>
              <Field label="Description">
                <input
                  value={editing.description}
                  onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                />
              </Field>
              {(['debit', 'credit', 'balance'] as const).map((k) => (
                <Field
                  key={k}
                  label={k[0].toUpperCase() + k.slice(1)}
                  hint="Blank clears this value."
                >
                  <input
                    inputMode="decimal"
                    value={editing[k]}
                    onChange={(e) => setEditing({ ...editing, [k]: e.target.value })}
                  />
                </Field>
              ))}
              <Field label="Correction note">
                <input
                  value={editing.note}
                  onChange={(e) => setEditing({ ...editing, note: e.target.value })}
                />
              </Field>
            </div>
            {editing.action === 'delete' && (
              <Notice tone="warning">
                This stages deletion of the entire row. Review the batch before saving.
              </Notice>
            )}
            {editError && (
              <p className="error" role="alert">
                {editError}
              </p>
            )}
            <Button type="submit">Stage change</Button>
          </form>
        )}
      </Modal>
    </>
  );
}
function Checks({ job }: { job: Job }) {
  const { api } = useWorkspace();
  const { run, busy } = useAction();
  const [compared, setCompared] = useState<string[]>([]);
  const [note, setNote] = useState('');
  const [aiChecked, setAiChecked] = useState(false);
  const aiPending = job.rows.some((r) => r.engine === 'ai' && !r.sourceReviewed);
  return (
    <div className="grid two">
      <Card>
        <Badge tone={job.verdict === 'NEEDS_REVIEW' ? 'peach' : 'mint'}>Financial evidence</Badge>
        <h2>{verdictLabels[job.verdict]}</h2>
        <dl className="facts">
          <dt>Opening / closing</dt>
          <dd>1,000.00 / 2,987.50 USD (fixture)</dd>
          <dt>Sequence</dt>
          <dd>
            {job.verdict === 'NEEDS_REVIEW'
              ? 'Difference or source trust gate pending'
              : 'Matches the fixed sample amounts'}
          </dd>
          <dt>Source review</dt>
          <dd>{job.sourceChecked ? 'Completed at current revision' : 'Pending'}</dd>
          <dt>Period / continuity</dt>
          <dd>One January sample; cross-file checks require backend</dd>
        </dl>
        <Notice>
          Do not treat these fixture checks as real reconciliation. The server must validate
          balances, totals, dates, gaps and duplicates.
        </Notice>
        {aiPending && (
          <div className="inset">
            <h3>AI-derived rows need full source comparison</h3>
            <Check checked={aiChecked} onChange={() => setAiChecked(!aiChecked)}>
              I compared every AI sample row, including dates and descriptions, with the displayed
              source.
            </Check>
            <Button
              disabled={!aiChecked || busy}
              onClick={() =>
                void run(
                  () => api.confirmAiSource(job.id),
                  'AI source confirmation recorded. Now complete the source check.',
                )
              }
            >
              Confirm AI sample source
            </Button>
          </div>
        )}
      </Card>
      <Card>
        <Badge tone="blue">Separate source check</Badge>
        <h2>Check the current rows</h2>
        <p>
          Compare both sample rows, including every corrected row. This acknowledgement applies to
          revision {job.revision}.
        </p>
        {job.rows.map((r) => (
          <Check
            key={r.id}
            checked={compared.includes(r.id)}
            onChange={() =>
              setCompared((prev) =>
                prev.includes(r.id) ? prev.filter((x) => x !== r.id) : [...prev, r.id],
              )
            }
          >
            Compared {r.date} · {r.description}
            {r.fixed ? ' · corrected row' : ''}
          </Check>
        ))}
        <Field label="Source-check note">
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="What did you compare?"
          />
        </Field>
        <Button
          disabled={
            busy ||
            aiPending ||
            compared.length !== job.rows.length ||
            !note.trim() ||
            !job.rows.length
          }
          onClick={() =>
            void run(
              () => api.spotcheck(job.id, job.revision, note),
              'Source check recorded at the current revision.',
            )
          }
        >
          Record source check
        </Button>
        {job.sourceChecked && <Notice tone="success">Current check: {job.spotNote}</Notice>}
        <Link to={'/app/jobs/' + job.id}>Return to source and rows ↑</Link>
      </Card>
    </div>
  );
}
function Exports({ job }: { job: Job }) {
  const { api } = useWorkspace();
  const { run, busy } = useAction();
  const block = exportBlock(job);
  const ready = job.exportRevision === job.revision;
  return (
    <>
      <Card>
        <Heading level={2} title="Your result, your format">
          Review gates protect the package. Downloads here are fixed reference samples.
        </Heading>
        {block ? (
          <Notice tone="warning">{block}</Notice>
        ) : (
          <Notice tone="success">The sample meets the preview export gates.</Notice>
        )}
        <Button
          disabled={!!block || busy || ready}
          onClick={() =>
            void run(
              () => api.export(job.id),
              'Preview package prepared; downloads are fixed synthetic reference files.',
            )
          }
        >
          {ready ? 'Preview package prepared' : 'Prepare preview package'}
        </Button>
        <p className="fine">
          Current revision {job.revision} · package revision {job.exportRevision ?? 'none'}. Backend
          exports must verify these revisions and file hashes.
        </p>
      </Card>
      <div className="output-grid section">
        {outputs.map((o) => (
          <Card key={o.id}>
            <Download size={21} />
            <h2>{o.name}</h2>
            <p>{o.detail}</p>
            <p className="fine">
              {job.outputs.includes(o.id) ? 'Selected for this job' : 'Available reference format'}
            </p>
            {ready ? (
              <a className="button secondary" download href={'/samples/' + o.sample}>
                Download fixed {o.name} sample
              </a>
            ) : (
              <span className="muted">Prepare package to enable reference download</span>
            )}
          </Card>
        ))}
      </div>
      {ready && (
        <Card>
          <h2>Delivery package</h2>
          <p>
            A sample ZIP contains the six exports and a sample README. Real packaging must include
            the current job’s verified files and source-check evidence.
          </p>
          <a className="button primary" download href="/samples/sample-package.zip">
            Download fixed sample package
          </a>
          <p>No email or external delivery is sent by this preview.</p>
        </Card>
      )}
      <details>
        <summary>Merge, accounting imports and exceptions</summary>
        <p>
          Merge: {job.merge ? 'requested' : 'off'} · private account:{' '}
          {job.accountConfirmed ? 'confirmed' : 'not confirmed'}. Monthly workbook tabs,
          currency/direction checks and period continuity are backend operations.
        </p>
        <p>
          QuickBooks imports split into chunks of at most 1,000 rows. Xero and OFX are file imports,
          not live integrations. OFX requires institution and account details at integration time.
        </p>
        <p>
          Exceptional UNVERIFIABLE exports require owner authorization and recorded reasons; normal
          customers cannot bypass those gates here.
        </p>
      </details>
    </>
  );
}
function Files({ job }: { job: Job }) {
  return (
    <div className="grid two">
      <Card>
        <h2>Selected files</h2>
        {job.files.map((f, i) => (
          <div className="file-item" key={i}>
            <FileText />
            <div>
              <strong>{f.name}</strong>
              <p>
                Preview metadata: {f.pages} sample page · {f.kind}
              </p>
            </div>
          </div>
        ))}
        <Notice>
          The actual file contents were not uploaded. These page counts and classifications describe
          the fixture, not your selected files.
        </Notice>
        <a href="/samples/synthetic-january.pdf" download className="button secondary">
          Download synthetic source PDF
        </a>
      </Card>
      <Card>
        <h2>Intake & account grouping</h2>
        <dl className="facts">
          <dt>Currency / date order</dt>
          <dd>
            {job.currency} / {job.dateOrder}
          </dd>
          <dt>Merge</dt>
          <dd>
            {job.merge ? 'Requested; backend continuity checks pending' : 'Separate statement'}
          </dd>
          <dt>Private account label</dt>
          <dd>{job.accountGroup || 'Not set'}</dd>
          <dt>Identity</dt>
          <dd>{job.accountConfirmed ? 'Sample confirmation recorded' : 'Not confirmed'}</dd>
          <dt>Extraction choices</dt>
          <dd>
            {job.intake
              ? `${job.intake.engine} / ${job.intake.profile} / pages ${job.intake.pages || 'all'} / combine ${job.intake.combine ? 'yes' : 'no'}`
              : 'Seeded fixture'}
          </dd>
          <dt>Categories</dt>
          <dd>{job.categorize ? 'Requested; backend application pending' : 'Off'}</dd>
        </dl>
        <p>
          Real intake performs signature checks, encrypted-PDF handling, image rotation, blank-page
          detection and limit enforcement before extraction.
        </p>
        <p>
          Unsupported or failed extraction needs manual review, a tested profile or an explicitly
          selected fallback. Do not silently treat failures as successful conversion.
        </p>
      </Card>
    </div>
  );
}
function Ai({ job }: { job: Job }) {
  const { api } = useWorkspace();
  const { data } = useSnapshot();
  const { run, busy } = useAction();
  const [consent, setConsent] = useState(job.aiConsent);
  const [note, setNote] = useState(job.consentNote);
  const connection = data?.connections[0];
  return (
    <div className="grid two">
      <Card>
        <Badge tone="lavender">Optional, off by default</Badge>
        <h2>Your provider. Your choice.</h2>
        <p>
          AI fallback is reserved for isolated, masked transaction rows. Full PDFs and images are
          not automatically sent.
        </p>
        <dl className="facts">
          <dt>Connection</dt>
          <dd>{connection?.name ?? 'None'}</dd>
          <dt>Model / effort</dt>
          <dd>
            {connection?.model ?? 'Not selected'} / {connection?.effort ?? 'provider default'}
          </dd>
          <dt>Provider terms</dt>
          <dd>{connection?.terms ? 'Preview acknowledgement recorded' : 'Not acknowledged'}</dd>
          <dt>Job page budget</dt>
          <dd>
            {job.aiPagesUsed} / {job.aiPageCap} fixture pages
          </dd>
        </dl>
        <Link className="button secondary" to="/app/connections">
          Manage AI connections
        </Link>
        <Notice>
          Real inference requires secure BYOK storage, approved terms, a model, consent, masked
          payloads and a server-enforced budget. No model requests run here.
        </Notice>
      </Card>
      <Card>
        <h2>Consent for this conversion</h2>
        <Check checked={consent} onChange={() => setConsent(!consent)}>
          Permission to use the selected provider for minimized statement data has been obtained.
        </Check>
        <Field
          label="Consent record"
          hint="Describe who approved, when, and for which provider/model."
        >
          <textarea value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        <Button
          disabled={busy || (consent && !note.trim())}
          onClick={() =>
            void run(
              () => api.consent(job.id, consent, note),
              'Preview consent updated; no model was contacted.',
            )
          }
        >
          Save preview consent
        </Button>
        <p>
          Changing provider, model or effort needs renewed consent in the integrated app. Retrying
          invalid model output still consumes budget; counters must not reset silently.
        </p>
        <Button variant="secondary" disabled title="Requires the server-side AI adapter">
          Run AI fallback · backend required
        </Button>
      </Card>
    </div>
  );
}
function DataPrivacy({ job }: { job: Job }) {
  const { api } = useWorkspace();
  const { run, busy } = useAction();
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [abandon, setAbandon] = useState(false);
  const [partial, setPartial] = useState(false);
  return (
    <Card>
      <Badge tone="peach">You stay in control</Badge>
      <h2>Manage this conversion’s data</h2>
      <p>
        Removing a finished conversion clears its session data. An unfinished conversion requires
        explicit abandonment.
      </p>
      {job.deletionPending && (
        <Notice tone="warning">
          Simulated removal was incomplete. No certificate was issued. Retry without the simulated
          locked file.
        </Notice>
      )}
      <Button variant="danger" onClick={() => setOpen(true)}>
        <Trash2 size={17} />
        {job.deletionPending ? 'Retry removal' : 'Remove preview data'}
      </Button>
      <p className="fine">
        The production worker must inventory artifacts, constrain paths and report partial failures.
        A preview removal is not physical disk or backup deletion.
      </p>
      <Modal
        open={open}
        onOpenChange={setOpen}
        title="Remove preview conversion?"
        description="This clears sample rows, filenames and private notes from the current session."
      >
        <Check checked={confirm} onChange={() => setConfirm(!confirm)}>
          I understand this removes this sample conversion’s data.
        </Check>
        {job.status !== 'delivered' && (
          <Check checked={abandon} onChange={() => setAbandon(!abandon)}>
            Abandon this unfinished conversion.
          </Check>
        )}
        {api.mode === 'demo' && (
          <Check checked={partial} onChange={() => setPartial(!partial)}>
            Demonstrate a partial failure (locked artifact)
          </Check>
        )}
        <div className="actions section">
          <Button
            variant="danger"
            disabled={busy || !confirm || (job.status !== 'delivered' && !abandon)}
            onClick={() =>
              void run(
                () => api.close(job.id, abandon, partial),
                'Preview removal attempted.',
              ).then((ok) => {
                if (ok) setOpen(false);
              })
            }
          >
            Confirm removal
          </Button>
          <Button variant="secondary" onClick={() => setOpen(false)}>
            Keep conversion
          </Button>
        </div>
      </Modal>
    </Card>
  );
}
