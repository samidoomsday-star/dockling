import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  FoundationApi,
  FoundationError,
  type CurrentJob,
  type ServerFile,
  type ServerSession,
} from './lib/foundation';
const api = new FoundationApi();
const explain = (e: unknown) =>
  e instanceof FoundationError ? e.message : 'Check the fields and try again.';
const formats = [
  ['excel', 'Excel'],
  ['csv', 'CSV'],
  ['qb_csv3', 'QuickBooks 3 columns'],
  ['qb_csv4', 'QuickBooks 4 columns'],
  ['xero_csv', 'Xero'],
  ['ofx', 'OFX'],
];

export function Preferences({ session }: { session: ServerSession }) {
  const client = useQueryClient();
  const q = useQuery({
    queryKey: ['foundation', session.workspace_id, 'settings'],
    queryFn: () => api.settings(),
    retry: false,
  });
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  return (
    <section className="card section">
      <span className="eyebrow">Make it yours</span>
      <h1>Workspace preferences</h1>
      <p>These defaults apply when you create a new job. Existing jobs keep their choices.</p>
      {q.isError && <p role="alert">{explain(q.error)}</p>}
      {message && <p role="status">{message}</p>}
      {q.data ? (
        <form
          key={q.data.version}
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            setBusy(true);
            setMessage('');
            void api
              .saveSettings(session, {
                expected_version: q.data!.version,
                currency: f.get('currency'),
                date_order: f.get('date_order'),
                output_date_format: f.get('output_date_format'),
                outputs: f.getAll('outputs'),
              })
              .then(async () => {
                setMessage('Preferences saved for future jobs.');
                await client.invalidateQueries({
                  queryKey: ['foundation', session.workspace_id, 'settings'],
                });
              })
              .catch((e) => setMessage(explain(e)))
              .finally(() => setBusy(false));
          }}
        >
          <fieldset disabled={session.role !== 'owner' || busy}>
            <legend>New job defaults</legend>
            <label>
              Currency
              <input
                required
                name="currency"
                pattern="[A-Z]{3}"
                maxLength={3}
                defaultValue={q.data.currency}
              />
            </label>
            <label>
              Date order
              <select name="date_order" defaultValue={q.data.date_order}>
                <option value="auto">Automatic</option>
                <option value="MDY">Month / day / year</option>
                <option value="DMY">Day / month / year</option>
                <option value="YMD">Year / month / day</option>
              </select>
            </label>
            <label>
              Output date format
              <select name="output_date_format" defaultValue={q.data.output_date_format}>
                <option value="ISO">Year-month-day</option>
                <option value="MM/DD/YYYY">Month/day/year</option>
                <option value="DD/MM/YYYY">Day/month/year</option>
              </select>
            </label>
            <fieldset>
              <legend>Output formats</legend>
              {formats.map(([id, name]) => (
                <label className="check" key={id}>
                  <input
                    type="checkbox"
                    name="outputs"
                    value={id}
                    defaultChecked={q.data!.outputs.includes(id)}
                  />
                  {name}
                </label>
              ))}
            </fieldset>
            {session.role === 'owner' && (
              <button className="button primary">Save preferences</button>
            )}
          </fieldset>
          {session.role !== 'owner' && <p>Your owner can change these defaults.</p>}
        </form>
      ) : (
        !q.isError && <p>Loading preferences…</p>
      )}
    </section>
  );
}

export function JobOwnerTools({
  session,
  job,
  files,
  running,
}: {
  session: ServerSession;
  job: CurrentJob;
  files: ServerFile[];
  running: boolean;
}) {
  const client = useQueryClient();
  const prefix = ['foundation', session.workspace_id, 'job', job.id];
  const utilities = useQuery({
    queryKey: [...prefix, 'utilities', job.revision, running],
    queryFn: () => api.utilities(job.id),
    retry: false,
  });
  const operators = useQuery({
    queryKey: ['foundation', session.workspace_id, 'support-operators'],
    queryFn: () => api.operators(),
    enabled: session.role === 'owner',
    retry: false,
  });
  const grants = useQuery({
    queryKey: [...prefix, 'support-grants', job.revision],
    queryFn: () => api.grants(job.id),
    enabled: session.role === 'owner',
    retry: false,
  });
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    setMessage('');
    try {
      await action();
      await client.invalidateQueries({ queryKey: prefix });
      setMessage('Saved. Queued tools will appear below when finished.');
    } catch (e) {
      setMessage(explain(e));
    } finally {
      setBusy(false);
    }
  }
  if (session.role !== 'owner') return null;
  return (
    <section className="card section">
      <span className="eyebrow">Owner controls</span>
      <h2>Layout tools &amp; support</h2>
      <p>
        Keep private source information in this job. Share only the specific access needed, for up
        to one hour.
      </p>
      {message && <p role="status">{message}</p>}
      <details>
        <summary>Build a private layout scaffold</summary>
        <p>
          Downloads page-one words and layout clues for technical review. It contains private source
          text and is never added to the shared profile catalog automatically.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            void act(() => api.scaffold(session, job.id, job.revision, String(f.get('file'))));
          }}
        >
          <label>
            Source file
            <select name="file" required>
              {files.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.display_name}
                </option>
              ))}
            </select>
          </label>
          <button disabled={busy || running || !files.length} className="button secondary">
            Create private scaffold
          </button>
        </form>
        {utilities.isError && <p role="alert">{explain(utilities.error)}</p>}
        {utilities.data?.items.map((a) => (
          <p key={a.id}>
            <a
              className="text-link"
              href={'/api/v1/jobs/' + job.id + '/utilities/' + a.id + '/download'}
            >
              Download {a.name}
            </a>
          </p>
        ))}
      </details>
      <details>
        <summary>Allow temporary support access</summary>
        <p>
          The named operator must sign in with a fresh second factor. Changing this job’s revision
          ends the access. You can revoke it immediately.
        </p>
        {operators.isError && <p role="alert">{explain(operators.error)}</p>}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            void act(() =>
              api.grant(session, job.id, {
                expected_revision: job.revision,
                actor_id: f.get('operator'),
                scopes: f.getAll('scope'),
                minutes: Number(f.get('minutes')),
                reason: f.get('reason'),
              }),
            );
          }}
        >
          <label>
            Support operator
            <select name="operator" required>
              {operators.data?.items.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.display_name}
                </option>
              ))}
            </select>
          </label>
          <fieldset>
            <legend>Approved access</legend>
            <label className="check">
              <input name="scope" value="results" type="checkbox" defaultChecked />
              Extracted transaction rows
            </label>
            <label className="check">
              <input name="scope" value="source" type="checkbox" />
              Source files / pages
            </label>
            <label className="check">
              <input name="scope" value="profile_scaffold" type="checkbox" />
              Private layout scaffold
            </label>
          </fieldset>
          <label>
            Duration in minutes
            <input name="minutes" type="number" min={1} max={60} defaultValue={30} required />
          </label>
          <label>
            Why support is needed
            <input name="reason" maxLength={250} required />
          </label>
          <button className="button secondary" disabled={busy || !operators.data?.items.length}>
            Grant temporary access
          </button>
        </form>
        {!operators.data?.items.length && <p>No support operator has signed in yet.</p>}
        {grants.isError && <p role="alert">{explain(grants.error)}</p>}
        {grants.data?.items.map((g) => (
          <div className="connection-row" key={g.id}>
            <p>
              {g.scopes.join(', ')} ·{' '}
              {g.revoked ? 'Revoked' : 'Expires ' + new Date(g.expires_at).toLocaleString()} ·
              Revision {g.revision}
            </p>
            {!g.revoked && (
              <button
                disabled={busy}
                onClick={() =>
                  void act(() => api.revokeGrant(session, job.id, g.id, job.revision, g.version))
                }
              >
                Revoke support access
              </button>
            )}
          </div>
        ))}
      </details>
    </section>
  );
}

export default function ServiceOperations({ session }: { session: ServerSession }) {
  const health = useQuery({
    queryKey: ['foundation', 'health'],
    queryFn: () => api.health(),
    retry: false,
    refetchInterval: 15000,
  });
  const metrics = useQuery({
    queryKey: ['foundation', 'metrics'],
    queryFn: () => api.metrics(),
    retry: false,
  });
  const grants = useQuery({
    queryKey: ['foundation', 'assigned-support'],
    queryFn: () => api.grants(),
    retry: false,
  });
  const [section, setSection] = useState('processing');
  const [profileId, setProfileId] = useState('generic');
  const [draft, setDraft] = useState('');
  const [reason, setReason] = useState('');
  const [evidenceId, setEvidenceId] = useState('');
  const [synthetic, setSynthetic] = useState(false);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [diagnosticId, setDiagnosticId] = useState('');
  const [supportId, setSupportId] = useState('');
  const [offset, setOffset] = useState(0);
  const config = useQuery({
    queryKey: ['foundation', 'configuration', section],
    queryFn: () => api.configuration(section),
    retry: false,
  });
  const diagnostic = useQuery({
    queryKey: ['foundation', 'diagnostic', diagnosticId],
    queryFn: () => api.diagnostic(diagnosticId),
    enabled: !!diagnosticId,
    retry: false,
    refetchInterval: (q) =>
      q.state.data?.operation && ['queued', 'running'].includes(q.state.data.operation.state)
        ? 2000
        : false,
  });
  const support = useQuery({
    queryKey: ['foundation', 'support-rows', supportId, offset],
    queryFn: () => api.supportRows(supportId, offset),
    refetchInterval: 5000,
    enabled: !!supportId,
    retry: false,
  });
  async function act(action: () => Promise<unknown>) {
    setMessage('');
    setBusy(true);
    try {
      await action();
    } catch (e) {
      setMessage(explain(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Service operations</span>
          <h1>Service health</h1>
          <p>
            Fresh administrator second-factor sign-in required. Customer documents require a named,
            owner-approved support grant.
          </p>
        </div>
      </div>
      <section className="card section">
        <h2>Live services</h2>
        {health.isError ? (
          <p role="alert">{explain(health.error)}</p>
        ) : health.data ? (
          <dl>
            {Object.entries(health.data).map(([k, v]) => (
              <div key={k}>
                <dt>{k.replaceAll('_', ' ')}</dt>
                <dd className="wrap-anywhere">{v ?? 'Not reported'}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p>Checking services…</p>
        )}
        <p>
          Model hashes are verified at worker startup. The heartbeat reports availability, not a new
          hash check.
        </p>
        <button
          disabled={busy}
          onClick={() =>
            void act(async () => {
              const op = await api.selftest(session);
              setDiagnosticId(op.job_id);
              setMessage('Synthetic selftest queued.');
            })
          }
        >
          Run synthetic selftest
        </button>
      </section>
      {message && <p role="status">{message}</p>}
      {diagnosticId && (
        <section className="card section">
          <h2>Synthetic diagnostic</h2>
          {diagnostic.isError ? (
            <p role="alert">{explain(diagnostic.error)}</p>
          ) : diagnostic.data ? (
            <>
              <p>Status: {diagnostic.data.operation?.state ?? 'No operation'}</p>
              {diagnostic.data.reports.map((a) => (
                <p key={a.id}>
                  <a
                    className="text-link"
                    href={'/api/v1/admin/diagnostics/' + diagnosticId + '/' + a.id + '/download'}
                  >
                    Download {a.name}
                  </a>
                </p>
              ))}
              {diagnostic.data.evidence.map((e) => (
                <p key={e.artifact_id}>
                  Profile test: {e.passed ? 'Passed synthetic fixture' : 'Did not pass'}{' '}
                  {e.passed && (
                    <button onClick={() => setEvidenceId(e.artifact_id)}>
                      Use this test evidence
                    </button>
                  )}
                </p>
              ))}
            </>
          ) : (
            <p>Loading diagnostic…</p>
          )}
        </section>
      )}
      <section className="card section">
        <h2>Configuration versions</h2>
        <p>
          Save a draft first. Activation applies to future jobs. Existing jobs keep their processing
          and export configuration. Pricing stays internal; this does not publish an offer.
        </p>
        <label>
          Configuration section
          <select
            value={section.startsWith('profile_') ? 'profile' : section}
            onChange={(e) => {
              setSection(e.target.value === 'profile' ? 'profile_' + profileId : e.target.value);
              setDraft('');
              setEvidenceId('');
            }}
          >
            {['processing', 'exports', 'templates', 'pricing', 'profile'].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        {section.startsWith('profile_') && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setSection('profile_' + profileId);
              setDraft('');
              setEvidenceId('');
            }}
          >
            <label>
              Profile identifier
              <input
                pattern="[a-z0-9_-]+"
                maxLength={80}
                value={profileId}
                onChange={(e) => setProfileId(e.target.value)}
                required
              />
            </label>
            <button>Open profile</button>
          </form>
        )}
        {config.isError && <p role="alert">{explain(config.error)}</p>}
        {config.data && (
          <>
            <p>
              Latest version {config.data.version} · Active version{' '}
              {config.data.active_version ?? 'Baseline'}
            </p>
            <details>
              <summary>Edit supported configuration (advanced)</summary>
              <p>
                Use exact decimal text for money, for example “0.01”. Processing limits cannot
                weaken the financial checks.
              </p>
              <label>
                Configuration JSON
                <textarea
                  className="config-editor"
                  rows={14}
                  value={draft || JSON.stringify(config.data.data, null, 2)}
                  onChange={(e) => {
                    setDraft(e.target.value);
                    setEvidenceId('');
                  }}
                />
              </label>
              <label>
                Reason for change
                <input
                  maxLength={250}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  required
                />
              </label>
              {section.startsWith('profile_') && (
                <>
                  <p>
                    Shared profiles must contain permitted synthetic patterns. Private customer
                    scaffolds must be reviewed and redacted separately; never paste their words
                    directly here.
                  </p>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void act(async () => {
                        const p = JSON.parse(draft || JSON.stringify(config.data!.data)) as Record<
                          string,
                          unknown
                        >;
                        const op = await api.profileTest(session, String(p.id), p);
                        setDiagnosticId(op.job_id);
                        setMessage('Synthetic profile test queued.');
                      })
                    }
                  >
                    Test profile on synthetic fixture
                  </button>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={synthetic}
                      onChange={(e) => setSynthetic(e.target.checked)}
                    />
                    I reviewed this profile and it contains no private customer fingerprints.
                  </label>
                  <p>
                    Accepted test evidence:{' '}
                    {evidenceId ? 'Selected' : 'Run the exact profile test before activation'}
                  </p>
                </>
              )}
              <div className="action-row">
                <button
                  disabled={busy || !reason.trim()}
                  onClick={() =>
                    void act(async () => {
                      await api.saveConfiguration(session, section, {
                        expected_version: config.data!.version,
                        data: JSON.parse(draft || JSON.stringify(config.data!.data)),
                        reason,
                      });
                      await config.refetch();
                      setMessage('Draft saved. Active configuration is unchanged.');
                    })
                  }
                >
                  Save configuration draft
                </button>
                <button
                  className="button primary"
                  disabled={
                    busy ||
                    !reason.trim() ||
                    (section.startsWith('profile_') && (!synthetic || !evidenceId))
                  }
                  onClick={() =>
                    void act(async () => {
                      await api.saveConfiguration(session, section, {
                        expected_version: config.data!.version,
                        data: JSON.parse(draft || JSON.stringify(config.data!.data)),
                        reason,
                        activate: true,
                        synthetic_review_confirmed: synthetic,
                        evidence_id: evidenceId || null,
                      });
                      await config.refetch();
                      setMessage('Version activated for future jobs.');
                    })
                  }
                >
                  Activate for future jobs
                </button>
              </div>
              <h3>Version history</h3>
              {config.data.history.map((v) => (
                <p key={v.version}>
                  Version {v.version} · {v.reason}{' '}
                  <button
                    onClick={() => {
                      setDraft(JSON.stringify(v.data, null, 2));
                      setEvidenceId('');
                    }}
                  >
                    Copy version {v.version} into editor
                  </button>
                </p>
              ))}
            </details>
          </>
        )}
      </section>
      <section className="card section">
        <h2>Approved support access</h2>
        {grants.isError && <p role="alert">{explain(grants.error)}</p>}
        {grants.data?.items.length ? (
          grants.data.items.map((g) => (
            <div key={g.id}>
              <p>
                Job {g.job_id} · {g.scopes.join(', ')} · until{' '}
                {new Date(g.expires_at).toLocaleString()}
              </p>
              {g.scopes.includes('results') && (
                <button
                  onClick={() => {
                    setSupportId(g.id);
                    setOffset(0);
                  }}
                >
                  Open approved transaction rows
                </button>
              )}
              {(g.scopes.includes('source') || g.scopes.includes('profile_scaffold')) && (
                <SupportArtifacts grant={g.id} />
              )}
            </div>
          ))
        ) : (
          <p>No active grants. Administrator status does not give access to customer jobs.</p>
        )}
        {support.isError && <p role="alert">{explain(support.error)}</p>}
        {!support.isError && support.data && (
          <>
            <div className="table-scroll">
              <table>
                <caption>Owner-approved transaction rows</caption>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Description</th>
                    <th>Debit</th>
                    <th>Credit</th>
                    <th>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {support.data.items.map((r) => (
                    <tr key={r.statement_id + r.id}>
                      <td>{r.date}</td>
                      <td>{r.description}</td>
                      <td>{r.debit}</td>
                      <td>{r.credit}</td>
                      <td>{r.balance}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {offset > 0 && <button onClick={() => setOffset(0)}>First approved rows</button>}
            {support.data.next_offset !== null && (
              <button onClick={() => setOffset(support.data!.next_offset!)}>
                Next approved rows
              </button>
            )}
          </>
        )}
      </section>
      <section className="card section">
        <h2>Anonymous operation outcomes</h2>
        {metrics.isError ? (
          <p role="alert">{explain(metrics.error)}</p>
        ) : metrics.data ? (
          <>
            <p>
              {metrics.data.scope}. Groups need at least {metrics.data.minimum_workspaces}{' '}
              workspaces; {metrics.data.suppressed_groups} small groups are hidden.
            </p>
            {metrics.data.buckets.map((b) => (
              <p key={b.action + b.state}>
                {b.action} · {b.state} · {b.count}
              </p>
            ))}
          </>
        ) : (
          <p>Loading aggregate counts…</p>
        )}
      </section>
    </>
  );
}

function SupportArtifacts({ grant }: { grant: string }) {
  const [opened, setOpened] = useState(false);
  const q = useQuery({
    queryKey: ['foundation', 'support-artifacts', grant],
    queryFn: () => api.supportArtifacts(grant),
    refetchInterval: 5000,
    enabled: opened,
    retry: false,
  });
  return (
    <div>
      <button onClick={() => setOpened(!opened)}>
        {opened ? 'Hide approved files' : 'Show approved files'}
      </button>
      {opened &&
        (q.isError ? (
          <p role="alert">{explain(q.error)}</p>
        ) : q.data ? (
          q.data.items.map((a, i) => (
            <p key={a.id}>
              <a
                className="text-link"
                href={'/api/v1/admin/support-grants/' + grant + '/artifacts/' + a.id}
              >
                Download {a.kind.replaceAll('_', ' ')} {i + 1} ({a.bytes.toLocaleString()} bytes)
              </a>
            </p>
          ))
        ) : (
          <p>Loading approved files…</p>
        ))}
    </div>
  );
}
