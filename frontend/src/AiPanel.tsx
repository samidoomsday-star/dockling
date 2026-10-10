import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { FoundationApi, FoundationError, type ServerSession } from './lib/foundation';
const api = new FoundationApi();
const human = (value: string) => value.replaceAll('_', ' ');
export default function AiPanel({ session, id }: { session: ServerSession; id: string }) {
  const client = useQueryClient();
  const prefix = useMemo(
    () => ['foundation', session.workspace_id, 'job', id],
    [session.workspace_id, id],
  );
  const q = useQuery({
    queryKey: [...prefix, 'ai'],
    queryFn: () => api.aiStatus(id),
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.runs.some((r) => ['queued', 'running'].includes(r.state) || !r.cleanup_done)
        ? 2000
        : false,
  });
  const connections = useQuery({
    queryKey: ['foundation', session.workspace_id, 'connections'],
    queryFn: () => api.connections(),
    retry: false,
  });
  const [connection, setConnection] = useState('');
  const [note, setNote] = useState('');
  const [names, setNames] = useState('');
  const [cap, setCap] = useState(5);
  const [requestCap, setRequestCap] = useState(5);
  const [consent, setConsent] = useState(false);
  const [pages, setPages] = useState<string[]>([]);
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const state = q.data?.runs[0]?.state;
  useEffect(() => {
    if (state && !['queued', 'running'].includes(state)) {
      void client.invalidateQueries({
        queryKey: prefix,
        predicate: (query) => query.queryKey.at(-1) !== 'ai',
      });
    }
    setPages([]);
    // The revision/run state is authoritative; refreshing sibling data does not reset consent input.
  }, [q.data?.revision, state, client, prefix]);
  async function act(run: () => Promise<unknown>) {
    setBusy(true);
    setError('');
    try {
      await run();
      await client.invalidateQueries({ queryKey: prefix });
    } catch (e) {
      setError(
        e instanceof FoundationError
          ? e.message
          : 'The AI request could not be saved. Refresh and try again.',
      );
    } finally {
      setBusy(false);
    }
  }
  if (q.isPending) return <p>Loading optional AI settings…</p>;
  if (q.isError)
    return (
      <p role="alert">
        Optional AI settings are unavailable. Regular conversion remains available.
      </p>
    );
  const s = q.data;
  const owner = session.role === 'owner';
  const writable = session.role !== 'viewer';
  const running = s.runs.some((r) => ['queued', 'running'].includes(r.state) || !r.cleanup_done);
  const selected = connections.data?.items.find((c) => c.id === connection);
  const uncertain = s.runs.some(
    (r) => r.state === 'uncertain' || r.error_code === 'AI_OUTCOME_UNCERTAIN',
  );
  return (
    <section className="card section blue" aria-labelledby="optional-ai-title">
      <h2 id="optional-ai-title">Optional AI assistance</h2>
      <p>
        Use your model to help with existing transaction cells after regular conversion. It cannot
        recover missing rows or read a whole PDF. You must compare every AI row with the source
        before exporting.
      </p>
      <div className="notice">
        <p>
          Only minimized transaction cells are sent. Known names and detected email/phone/account
          identifiers are masked; this is not a guarantee of full anonymity. Your provider may
          charge you. Regular conversion needs no LLM key.
        </p>
      </div>
      <div className="grid three ai-usage">
        <div>
          <span>Pages reserved</span>
          <strong>
            {s.pages_used} / {s.consent?.page_cap ?? 'No allowance'}
          </strong>
        </div>
        <div>
          <span>Requests reserved</span>
          <strong>
            {s.requests_used} / {s.consent?.request_cap ?? 'No allowance'}
          </strong>
        </div>
        <div>
          <span>Permission</span>
          <strong>{s.consent?.valid ? 'Current' : 'Required'}</strong>
        </div>
      </div>
      <p className="fine">
        Reservations stay counted after failure, cancellation or a model change. These counts limit
        requests; they do not confirm your provider’s invoice or set a dollar spending limit.
      </p>
      {error && <p role="alert">{error}</p>}
      {!s.pages.length && <p>Convert a statement first to make transaction pages available.</p>}
      {owner && (
        <details>
          <summary>Set or renew job permission</summary>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void act(async () => {
                await api.aiConsent(session, id, {
                  expected_revision: s.revision,
                  expected_consent_version: s.consent?.version ?? 0,
                  granted: true,
                  connection_id: connection,
                  consent_note: note,
                  mask_names: names
                    .split('\n')
                    .map((n) => n.trim())
                    .filter(Boolean),
                  page_cap: cap,
                  request_cap: requestCap,
                });
                setConsent(false);
                setNote('');
                setNames('');
              });
            }}
          >
            <label>
              AI provider for this job
              <select
                aria-label="AI provider for this job"
                value={connection}
                onChange={(e) => setConnection(e.target.value)}
                disabled={busy || running}
              >
                <option value="">Choose a configured provider</option>
                {connections.data?.items
                  .filter((c) => c.active && c.selected_model)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} · {c.selected_model} · {human(c.effort)}
                    </option>
                  ))}
              </select>
            </label>
            <p>
              <Link className="text-link" to="/app/connections">
                Manage providers and models
              </Link>
              . The connection must have suitable terms and any required key saved.
            </p>
            {selected && (
              <p>
                Selected: {selected.name}, {selected.selected_model}, {human(selected.effort)}.{' '}
                <strong>
                  {selected.terms_confirmed
                    ? 'Provider terms recorded'
                    : 'Confirm provider terms first'}
                </strong>
                .
              </p>
            )}
            <label>
              Client permission note
              <textarea
                aria-label="Client permission note"
                maxLength={500}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                disabled={busy || running}
              />
            </label>
            <label>
              Names to mask (one per line)
              <textarea
                aria-label="Names to mask"
                maxLength={4000}
                value={names}
                onChange={(e) => setNames(e.target.value)}
                disabled={busy || running}
              />
            </label>
            <p className="fine">
              Include the client’s name and other known sensitive names each time you renew
              permission. These private entries are not returned to the browser.
            </p>
            <div className="grid two">
              <label>
                Job page allowance
                <input
                  aria-label="Job page allowance"
                  type="number"
                  min={1}
                  max={s.platform_page_cap}
                  value={cap}
                  onChange={(e) => setCap(Number(e.target.value))}
                  disabled={busy || running}
                />
              </label>
              <label>
                Job request allowance
                <input
                  aria-label="Job request allowance"
                  type="number"
                  min={1}
                  max={s.platform_request_cap}
                  value={requestCap}
                  onChange={(e) => setRequestCap(Number(e.target.value))}
                  disabled={busy || running}
                />
              </label>
            </div>
            <label className="check">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              I have permission to send these minimized cells to this provider under suitable terms.
            </label>
            <button
              className="button primary"
              disabled={
                busy ||
                running ||
                !consent ||
                !note.trim() ||
                !selected?.terms_confirmed ||
                !s.pages.length
              }
            >
              Save job permission
            </button>
          </form>
        </details>
      )}
      {owner && s.consent?.granted && (
        <button
          className="button secondary"
          disabled={busy}
          onClick={() =>
            void act(() =>
              api.aiConsent(session, id, {
                expected_revision: s.revision,
                expected_consent_version: s.consent!.version,
                granted: false,
              }),
            )
          }
        >
          Revoke job permission
        </button>
      )}
      {writable && s.pages.length > 0 && (
        <>
          <fieldset disabled={busy || running || !s.consent?.valid}>
            <legend>Pages for this AI request (up to {s.pages_per_run})</legend>
            {s.pages.map((p) => (
              <label className="check" key={p.key}>
                <input
                  type="checkbox"
                  checked={pages.includes(p.key)}
                  onChange={(e) =>
                    setPages(
                      e.target.checked ? [...pages, p.key] : pages.filter((k) => k !== p.key),
                    )
                  }
                />
                {p.statement_id} · source page {p.page} · {p.rows} rows
              </label>
            ))}
          </fieldset>
          {uncertain && (
            <div className="notice">
              <p>
                An earlier request has an uncertain outcome. It may have completed or been charged.
                We will not resend it automatically.
              </p>
              <label className="check">
                <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />I
                understand that a new request can cause another provider charge.
              </label>
            </div>
          )}
          <button
            className="button primary"
            disabled={
              busy ||
              running ||
              !s.consent?.valid ||
              !pages.length ||
              pages.length > s.pages_per_run ||
              (uncertain && !ack)
            }
            onClick={() =>
              void act(async () => {
                await api.aiRequest(session, id, {
                  expected_revision: s.revision,
                  consent_version: s.consent!.version,
                  page_keys: pages,
                  acknowledge_prior_uncertainty: ack,
                });
                setAck(false);
              })
            }
          >
            Request AI assistance
          </button>
        </>
      )}
      {s.runs.length > 0 && (
        <div className="table-wrap">
          <table>
            <caption>Recent AI requests</caption>
            <thead>
              <tr>
                <th>Status</th>
                <th>Reserved pages</th>
                <th>Result</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {s.runs.map((r) => (
                <tr key={r.id}>
                  <td>{human(r.state)}</td>
                  <td>{r.pages_reserved}</td>
                  <td>
                    {r.state === 'succeeded'
                      ? 'Saved; full AI source review required'
                      : r.error_code === 'AI_OUTCOME_UNCERTAIN'
                        ? 'May have completed or been charged'
                        : r.error_code
                          ? 'Stopped without applying results'
                          : r.cleanup_done
                            ? 'Waiting'
                            : 'Processing; cleanup pending'}
                  </td>
                  <td>
                    {writable && ['queued', 'running'].includes(r.state) && (
                      <button
                        disabled={busy}
                        onClick={() => void act(() => api.aiCancel(session, id, r.id, s.revision))}
                      >
                        Cancel AI request
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
