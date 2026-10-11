import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { AccountsApi, type AccountInvoice, type AccountRequest } from './lib/accounts';
import { FoundationError, type ServerSession } from './lib/foundation';

const api = new AccountsApi();
const explain = (e: unknown) =>
  e instanceof FoundationError
    ? e.message
    : 'The service could not complete this action. Please try again.';
function useActions() {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    setMessage('');
    try {
      await action();
      await client.invalidateQueries({ queryKey: ['foundation'] });
    } catch (e) {
      setMessage(explain(e));
    } finally {
      setBusy(false);
    }
  }
  return { busy, message, act };
}

export function Onboarding({
  session,
  act,
  busy,
}: {
  session: ServerSession;
  act: (fn: () => Promise<unknown>, next?: string) => Promise<void>;
  busy: boolean;
}) {
  const [name, setName] = useState('');
  return (
    <section className="card section mint">
      <span className="eyebrow">A private place for your team</span>
      <h1>Set up your workspace</h1>
      <p>
        Create a workspace for your own documents, or reopen the invitation link your team owner
        sent you.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void act(() => api.createWorkspace(session, name), '/app');
        }}
      >
        <label>
          Workspace name
          <input
            required
            maxLength={80}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="For example, Northside Bookkeeping"
          />
        </label>
        <button className="button primary" disabled={busy}>
          Create my workspace
        </button>
      </form>
      <p>
        Your files stay private to invited members. AI is optional. Creating a workspace does not
        take a payment.
      </p>
    </section>
  );
}

export function AccountOverview({ session }: { session: ServerSession }) {
  const q = useQuery({
    queryKey: ['foundation', session.workspace_id, 'usage'],
    queryFn: () => api.usage(),
    retry: false,
    refetchInterval: 10000,
  });
  if (q.isError) return <p role="alert">{explain(q.error)}</p>;
  const u = q.data;
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Stay in control</span>
          <h1>Account and usage</h1>
          <p>
            Your team's current allowance. Existing files remain available if processing access
            ends.
          </p>
        </div>
      </div>
      {q.isPending && <p role="status">Loading your allowance…</p>}
      {u && (
        <>
          <section className="account-grid" aria-label="Current workspace allowance">
            <div className="card section mint">
              <h2>Pages available</h2>
              <p className="account-number">{u.pages_remaining}</p>
              <p>
                {u.pages_used} inspected · {u.pages_reserved} reserved · {u.page_limit} allowed
              </p>
              <p>Calendar month: {u.period} (UTC)</p>
            </div>
            <div className="card section lavender">
              <h2>Your team</h2>
              <p className="account-number">
                {u.active_seats} / {u.seat_limit}
              </p>
              <p>{u.pending_invitations} pending invitations also hold a place.</p>
              {session.role === 'owner' && <Link to="/app/team">Manage your team</Link>}
            </div>
            <div className="card section peach">
              <h2>Processing access</h2>
              <p>
                <strong>{u.processing_allowed ? 'Available' : 'Inactive'}</strong>
              </p>
              <p>
                {u.status === 'development'
                  ? 'Synthetic test allowance; no subscription or payment.'
                  : u.status.replaceAll('_', ' ')}
              </p>
              {u.valid_until && <p>Access ends {new Date(u.valid_until).toLocaleDateString()}.</p>}
              <Link to="/app/help">Ask for help or a plan change</Link>
            </div>
          </section>
          <section className="card section">
            <h2>How page allowance works</h2>
            <p>
              Before inspection, up to {u.inspection_reservation_max} pages are reserved for a job.
              Conversion adjusts that reservation to the inspected page count. Repeating the same
              input in the same job and month does not count it again.
            </p>
            <p>
              A failed or interrupted inspection can keep its reservation. Ask support if you need
              help. Removing a job does not reset usage. Your AI provider's charges are separate.
            </p>
          </section>
        </>
      )}
      <section className="card section">
        <h2>Account security</h2>
        <p>
          Your sign-in provider manages your password, email verification and second factor.
          Workspace owners control team access. Ask support for account recovery or a personal-data
          request.
        </p>
        <Link to="/app/help">Open help and requests</Link>
      </section>
    </>
  );
}

export function InvitationHistory({ session }: { session: ServerSession }) {
  const actions = useActions();
  const q = useQuery({
    queryKey: ['foundation', session.workspace_id, 'invitations'],
    queryFn: () => api.invitations(),
    retry: false,
  });
  return (
    <section className="card section lavender">
      <h2>Recent invitations</h2>
      {actions.message && <p role="alert">{actions.message}</p>}
      {q.isError && <p role="alert">{explain(q.error)}</p>}
      {!q.isError &&
        q.data?.items.map((i) => (
          <div className="team-row" key={i.id}>
            <span>
              {i.email} · {i.role} · {i.status}
            </span>
            <span>Expires {new Date(i.expires_at).toLocaleDateString()}</span>
            {i.status === 'pending' && (
              <button
                disabled={actions.busy}
                onClick={() => void actions.act(() => api.revoke(session, i.id))}
              >
                Revoke invitation for {i.email}
              </button>
            )}
          </div>
        ))}
      {!q.isError && q.data?.items.length === 0 && <p>No invitations yet.</p>}
    </section>
  );
}

function InvoiceCard({ invoice }: { invoice: AccountInvoice }) {
  return (
    <article className="card section mint">
      <h3>{invoice.plan_name}</h3>
      <p>
        <strong>
          {invoice.currency} {invoice.amount}
        </strong>{' '}
        · {invoice.status}
      </p>
      <p>
        Processing access until {new Date(invoice.valid_until).toLocaleDateString()}, after verified
        payment.
      </p>
      <a
        className="button secondary"
        download={'invoice-' + invoice.id + '.json'}
        href={
          'data:application/json;charset=utf-8,' +
          encodeURIComponent(JSON.stringify(invoice, null, 2))
        }
      >
        Download invoice record
      </a>
    </article>
  );
}

export function BillingWorkspace({ session }: { session: ServerSession }) {
  const q = useQuery({
    queryKey: ['foundation', session.workspace_id, 'billing'],
    queryFn: () => api.billing(),
    enabled: session.role === 'owner',
    retry: false,
  });
  const plans = useQuery({
    queryKey: ['foundation', session.workspace_id, 'plans'],
    queryFn: () => api.plans(),
    enabled: session.role === 'owner',
    retry: false,
  });
  if (session.role !== 'owner')
    return (
      <p>
        Billing is managed by your workspace owner. You can view your allowance under Account and
        usage.
      </p>
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Clear plans, no surprise charges</span>
          <h1>Plans and billing</h1>
          <p>The service owner arranges manual invoices. No online payment is taken here.</p>
        </div>
        <Link className="button primary" to="/app/help">
          Request a plan or invoice
        </Link>
      </div>
      {(q.isError || plans.isError) && <p role="alert">{explain(q.error ?? plans.error)}</p>}
      {!plans.isError &&
        plans.data?.items.map((p) => (
          <article className="card section lavender" key={p.id}>
            <h2>{p.name}</h2>
            <p>
              {p.currency} {p.monthly_amount} · {p.pages_per_month} pages per calendar month ·{' '}
              {p.seats} team places
            </p>
          </article>
        ))}
      {!plans.isError && plans.data?.items.length === 0 && (
        <section className="card section peach">
          <h2>Plans are being prepared</h2>
          <p>
            Contact the service owner for an agreed offer. No public subscription price has been
            approved yet.
          </p>
        </section>
      )}
      <section className="card section">
        <h2>Your invoice records</h2>
        <p>
          These records track the agreed plan and payment status. They do not take payments or serve
          as tax invoices.
        </p>
        {!q.isError && q.data?.invoices.map((i) => <InvoiceCard key={i.id} invoice={i} />)}
        {!q.isError && q.data?.invoices.length === 0 && (
          <p>No invoices have been created for this workspace.</p>
        )}
      </section>
    </>
  );
}

export function HelpWorkspace({ session }: { session: ServerSession }) {
  const q = useQuery({
    queryKey: ['foundation', session.workspace_id, 'requests'],
    queryFn: () => api.requests(),
    retry: false,
    refetchInterval: 10000,
  });
  const actions = useActions();
  const [kind, setKind] = useState<AccountRequest['kind']>('support');
  const [message, setMessage] = useState('');
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Help when you need it</span>
          <h1>Help and requests</h1>
          <p>
            Requests stay private. Support does not automatically gain access to your documents.
          </p>
        </div>
      </div>
      <section className="card section mint">
        <h2>A good first conversion</h2>
        <ol>
          <li>Upload a bank or card statement and inspect it.</li>
          <li>Convert it, then compare dates, descriptions and amounts with the source.</li>
          <li>Confirm the source checks and generate your chosen downloads.</li>
          <li>Test the import in your accounting software before relying on it.</li>
        </ol>
        <p>
          Reconciled balances alone cannot prove every row is correct. Unknown layouts can need
          correction. AI is optional and needs your permission.
        </p>
      </section>
      <section className="card section lavender">
        <h2>Send a request</h2>
        <p>
          Describe the issue without including statement text, account numbers, API keys or
          attachments. Workspace privacy requests are reviewed; sending a request does not delete
          your team's data.
        </p>
        {actions.message && <p role="alert">{actions.message}</p>}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void actions.act(async () => {
              await api.requestHelp(session, kind, message);
              setMessage('');
            });
          }}
        >
          <label>
            Request type
            <select
              aria-label="Request type"
              value={kind}
              onChange={(e) => setKind(e.target.value as AccountRequest['kind'])}
            >
              <option value="support">Help with the app</option>
              {session.role === 'owner' && (
                <>
                  <option value="plan">Plan or invoice</option>
                  <option value="privacy_export">Workspace data export request</option>
                  <option value="privacy_remove">Workspace data removal request</option>
                </>
              )}
            </select>
          </label>
          <label>
            Your message
            <textarea
              required
              maxLength={500}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
          </label>
          <button className="button primary" disabled={actions.busy}>
            Send private request
          </button>
        </form>
      </section>
      <section className="card section">
        <h2>Your recent requests</h2>
        {q.isError && <p role="alert">{explain(q.error)}</p>}
        {!q.isError &&
          q.data?.items.map((r) => (
            <article key={r.id} className="notice">
              <h3>
                {r.kind === 'support'
                  ? 'App support'
                  : r.kind === 'plan'
                    ? 'Plan or invoice'
                    : 'Workspace privacy request'}{' '}
                · {r.status}
              </h3>
              <p>{r.message}</p>
              {r.response && (
                <p>
                  <strong>Response:</strong> {r.response}
                </p>
              )}
            </article>
          ))}
        {!q.isError && q.data?.items.length === 0 && <p>No requests yet.</p>}
      </section>
    </>
  );
}

export function NoticesWorkspace({ session }: { session: ServerSession }) {
  const actions = useActions();
  const q = useQuery({
    queryKey: ['foundation', session.workspace_id, 'notices'],
    queryFn: () => api.notices(),
    retry: false,
    refetchInterval: 10000,
  });
  const title = (action: string) =>
    action.startsWith('invoice.')
      ? 'Billing record updated'
      : action.startsWith('request.')
        ? 'Support request updated'
        : action.startsWith('invitation.')
          ? 'Team invitation updated'
          : action.startsWith('member.')
            ? 'Team access updated'
            : action.startsWith('job.')
              ? 'Document job updated'
              : 'Workspace activity';
  return (
    <section className="card section mint">
      <h1>Workspace updates</h1>
      <p>Recent status notices contain no document text or amounts. No email is sent.</p>
      {actions.message && <p role="alert">{actions.message}</p>}
      {q.isError && <p role="alert">{explain(q.error)}</p>}
      {!q.isError &&
        q.data?.items.map((n) => (
          <article className="team-row" key={n.id}>
            <span>
              {title(n.action)} · {new Date(n.created_at).toLocaleString()}
            </span>
            {n.read ? (
              <span>Read</span>
            ) : (
              <button
                disabled={actions.busy}
                onClick={() => void actions.act(() => api.markRead(session, n.id))}
              >
                Mark update read
              </button>
            )}
          </article>
        ))}
    </section>
  );
}

function EvidenceForm({
  session,
  workspace,
  invoice,
  act,
  busy,
}: {
  session: ServerSession;
  workspace: string;
  invoice: AccountInvoice;
  act: (fn: () => Promise<unknown>) => Promise<void>;
  busy: boolean;
}) {
  const next: Record<string, string[]> = {
    draft: ['issued', 'cancelled'],
    issued: ['paid', 'failed', 'cancelled'],
    failed: ['issued', 'cancelled'],
    paid: ['refunded', 'cancelled'],
  };
  const states = next[invoice.status] ?? [];
  const [confirmed, setConfirmed] = useState(false);
  return (
    <article className="card section">
      <h3>
        {invoice.plan_name} · {invoice.status}
      </h3>
      <p>
        {invoice.currency} {invoice.amount} · version {invoice.version}
      </p>
      {states.length > 0 && (
        <form
          key={invoice.version}
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            void act(async () => {
              await api.evidence(
                session,
                workspace,
                invoice,
                String(f.get('status')),
                String(f.get('reference')),
              );
              setConfirmed(false);
            });
          }}
        >
          <label>
            Verified event
            <select aria-label="Verified event" name="status">
              {states.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label>
            Unique evidence reference
            <input
              name="reference"
              required
              minLength={8}
              maxLength={120}
              pattern="[a-zA-Z0-9][a-zA-Z0-9_.:\-]{7,119}"
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            I independently verified this event. This form does not charge or refund money.
          </label>
          <button disabled={busy || !confirmed}>Record verified event</button>
        </form>
      )}
    </article>
  );
}

export function BillingOperations({ session }: { session: ServerSession }) {
  const actions = useActions();
  const [workspace, setWorkspace] = useState('');
  const plans = useQuery({
    queryKey: ['foundation', 'admin', 'plans'],
    queryFn: () => api.adminPlans(),
    enabled: session.platform_admin,
    retry: false,
  });
  const spaces = useQuery({
    queryKey: ['foundation', 'admin', 'billing-workspaces'],
    queryFn: () => api.billingWorkspaces(),
    enabled: session.platform_admin,
    retry: false,
  });
  const bills = useQuery({
    queryKey: ['foundation', 'admin', 'billing', workspace],
    queryFn: () => api.adminBilling(workspace),
    enabled: session.platform_admin && !!workspace,
    retry: false,
  });
  const requests = useQuery({
    queryKey: ['foundation', 'admin', 'requests'],
    queryFn: () => api.adminRequests(),
    enabled: session.platform_admin,
    retry: false,
    refetchInterval: 10000,
  });
  if (!session.platform_admin)
    return <p>Fresh administrator sign-in with a second factor is required.</p>;
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Owner operations</span>
          <h1>Billing and support</h1>
          <p>
            Record verified manual events. Prices remain private drafts while commercial offers are
            disabled.
          </p>
        </div>
      </div>
      {actions.message && <p role="alert">{actions.message}</p>}
      {[plans, spaces, bills, requests].some((q) => q.isError) && (
        <p role="alert">
          Billing or support could not be loaded. Refresh your verified sign-in and try again.
        </p>
      )}
      <section className="card section lavender">
        <h2>Create a private plan draft</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            void actions.act(() =>
              api.createPlan(session, {
                name: String(f.get('name')),
                pages_per_month: Number(f.get('pages')),
                seats: Number(f.get('seats')),
                monthly_amount: String(f.get('amount')),
                currency: String(f.get('currency')),
                approved_for_customers: false,
              }),
            );
          }}
        >
          <label>
            Plan name
            <input name="name" required maxLength={80} />
          </label>
          <label>
            Pages per calendar month
            <input name="pages" type="number" min={1} max={10000} defaultValue={500} />
          </label>
          <label>
            Team places
            <input name="seats" type="number" min={1} max={100} defaultValue={5} />
          </label>
          <label>
            Exact monthly amount
            <input
              name="amount"
              inputMode="decimal"
              required
              placeholder="For example, 25.00"
              pattern="(0|[1-9][0-9]*)\.[0-9]{2}"
            />
          </label>
          <label>
            Currency
            <input name="currency" defaultValue="USD" required pattern="[A-Z]{3}" maxLength={3} />
          </label>
          <button disabled={actions.busy}>Save private plan draft</button>
        </form>
        {!plans.isError &&
          plans.data?.items.map((p) => (
            <p key={p.id}>
              {p.name} · {p.currency} {p.monthly_amount} · {p.pages_per_month} pages · {p.seats}{' '}
              places · {p.approved_for_customers ? 'Approved' : 'Private draft'}
            </p>
          ))}
      </section>
      <section className="card section mint">
        <h2>Workspace invoices</h2>
        <label>
          Billing workspace
          <select
            aria-label="Billing workspace"
            value={workspace}
            onChange={(e) => setWorkspace(e.target.value)}
          >
            <option value="">Choose workspace</option>
            {!spaces.isError &&
              spaces.data?.items.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
          </select>
        </label>
        {workspace && !plans.isError && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void actions.act(() =>
                api.createInvoice(session, workspace, String(f.get('plan')), Number(f.get('days'))),
              );
            }}
          >
            <label>
              Invoice plan
              <select aria-label="Invoice plan" name="plan" required>
                <option value="">Choose a plan</option>
                {plans.data?.items.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Access period in days
              <input name="days" type="number" min={1} max={366} defaultValue={30} />
            </label>
            <button disabled={actions.busy}>Create invoice draft</button>
          </form>
        )}
        {!bills.isError &&
          bills.data?.invoices.map((i) => (
            <EvidenceForm
              key={i.id}
              session={session}
              workspace={workspace}
              invoice={i}
              act={actions.act}
              busy={actions.busy}
            />
          ))}
      </section>
      <section className="card section peach">
        <h2>Private support and plan requests</h2>
        {!requests.isError &&
          requests.data?.items.map((r) => (
            <article className="card section" key={r.id}>
              <h3>
                {r.kind} · {r.status}
              </h3>
              <p>{r.message}</p>
              {r.response && <p>{r.response}</p>}
              {r.status !== 'closed' && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    void actions.act(() =>
                      api.respond(session, r, String(f.get('response')), String(f.get('status'))),
                    );
                  }}
                >
                  <label>
                    Your response
                    <textarea name="response" required maxLength={500} />
                  </label>
                  <label>
                    Request outcome
                    <select aria-label="Request outcome" name="status">
                      <option value="answered">Answered</option>
                      <option value="closed">Closed</option>
                    </select>
                  </label>
                  <button disabled={actions.busy}>Save private response</button>
                </form>
              )}
            </article>
          ))}
      </section>
    </>
  );
}
