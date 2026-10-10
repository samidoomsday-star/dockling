import { useState } from 'react';
import { Link, Routes, Route, useNavigate, useParams } from 'react-router-dom';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { FoundationApi, FoundationError, type ServerSession } from './lib/foundation';
const api = new FoundationApi();
const explain = (e: unknown) =>
  e instanceof FoundationError ? e.message : 'The service is unavailable. Please try again.';

export default function FoundationApp() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const session = useQuery({
    queryKey: ['foundation', 'session'],
    queryFn: () => api.session(),
    retry: false,
    refetchOnWindowFocus: true,
  });
  const workspaces = useInfiniteQuery({
    queryKey: ['foundation', 'workspaces', session.data?.user_id],
    queryFn: ({ pageParam }) => api.workspaces(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: !!session.data,
    retry: false,
  });
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  async function act(action: () => Promise<unknown>, next?: string) {
    setBusy(true);
    setMessage('');
    try {
      await action();
      // Remove all private cached results before a changed identity/workspace renders.
      await client.cancelQueries({ queryKey: ['foundation'] });
      client.removeQueries({ queryKey: ['foundation'] });
      await session.refetch();
      if (next) navigate(next);
    } catch (e) {
      setMessage(explain(e));
    } finally {
      setBusy(false);
    }
  }
  if (session.isPending)
    return (
      <main id="main" className="public-main">
        <h1>Opening your workspace…</h1>
      </main>
    );
  if (!session.data)
    return (
      <main id="main" className="public-main">
        <Link className="brand" to="/">
          Dockling<span className="brand-dot">•</span>
        </Link>
        <section className="hero">
          <span className="eyebrow">Your statement workspace</span>
          <h1>A clearer place to prepare your financial documents.</h1>
          <p>Sign in to your private workspace and create a saved job.</p>
          <p>
            Foundation preview: upload, conversion, review, exports and billing are being connected
            in upcoming phases.
          </p>
          <a className="button primary" href="/auth/login">
            Sign in securely
          </a>
        </section>
        {session.error &&
          !(session.error instanceof FoundationError && session.error.status === 401) && (
            <p role="alert">{explain(session.error)}</p>
          )}
      </main>
    );
  const s = session.data;
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="preview-banner" role="status">
        SaaS foundation · Real sign-in and saved job records · Synthetic testing only
      </div>
      <div className="workspace foundation-shell">
        <aside className="sidebar">
          <Link className="brand" to="/app">
            Dockling<span className="brand-dot">•</span>
          </Link>
          <nav aria-label="Workspace">
            <Link to="/app">Overview</Link>
            <Link to="/app/jobs">Your jobs</Link>
            <Link to="/app/settings">Preferences</Link>
            {s.role === 'owner' && <Link to="/app/team">Team</Link>}
            {s.platform_admin && <Link to="/admin">Service health</Link>}
          </nav>
          <div className="sidebar-note">
            Uploads and conversion arrive in Phase 2. Your existing command-line app remains
            available.
          </div>
        </aside>
        <div className="workspace-body">
          <header className="app-header">
            <label>
              Workspace{' '}
              <select
                aria-label="Workspace"
                disabled={busy}
                value={s.workspace_id ?? ''}
                onChange={(e) => void act(() => api.switch(s, e.target.value), '/app')}
              >
                <option value="" disabled>
                  Select workspace
                </option>
                {workspaces.data?.pages
                  .flatMap((p) => p.items)
                  .map((w) => (
                    <option value={w.id} key={w.id}>
                      {w.name}
                    </option>
                  ))}
              </select>
            </label>
            {workspaces.hasNextPage && (
              <button
                disabled={workspaces.isFetchingNextPage}
                onClick={() => void workspaces.fetchNextPage()}
              >
                Load more workspaces
              </button>
            )}
            <span>{s.role ?? 'No workspace membership'}</span>
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => void act(() => api.logout(s), '/')}
            >
              Sign out
            </button>
          </header>
          <main id="main" className="app-main">
            {message && <p role="alert">{message}</p>}
            {workspaces.isError && <p role="alert">{explain(workspaces.error)}</p>}
            <Routes>
              <Route path="/invite" element={<Invitation session={s} act={act} busy={busy} />} />
              <Route path="/admin" element={<Health />} />
              {s.workspace_id ? (
                <>
                  <Route path="/app" element={<Jobs key={s.workspace_id} session={s} />} />
                  <Route path="/app/jobs" element={<Jobs key={s.workspace_id} session={s} />} />
                  <Route path="/app/new" element={<NewJob session={s} act={act} busy={busy} />} />
                  <Route path="/app/jobs/:id" element={<Job session={s} />} />
                  <Route path="/app/settings" element={<Settings session={s} />} />
                  <Route
                    path="/app/team"
                    element={<Team key={s.workspace_id} session={s} act={act} busy={busy} />}
                  />
                </>
              ) : (
                <Route
                  path="/app"
                  element={
                    <>
                      <h1>Welcome</h1>
                      <p>
                        Ask a workspace owner for an invitation. Administrator sign-in grants
                        service health access only.
                      </p>
                    </>
                  }
                />
              )}
              <Route
                path="*"
                element={
                  <>
                    <h1>Your workspace</h1>
                    <Link to="/app">Open overview</Link>
                  </>
                }
              />
            </Routes>
          </main>
        </div>
      </div>
    </>
  );
}
type Actions = {
  session: ServerSession;
  act: (action: () => Promise<unknown>, next?: string) => Promise<void>;
  busy: boolean;
};
function Jobs({ session }: { session: ServerSession }) {
  const [cursor, setCursor] = useState<string | null>(null);
  const [draftSearch, setDraftSearch] = useState('');
  const [search, setSearch] = useState('');
  const q = useQuery({
    queryKey: ['foundation', session.workspace_id, 'jobs', cursor, search],
    queryFn: () => api.jobs(cursor, search),
    retry: false,
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Organized from the start</span>
          <h1>Your jobs</h1>
          <p>Saved in your workspace. Add a name now; document processing comes next.</p>
        </div>
        {session.role !== 'viewer' && (
          <Link className="button primary" to="/app/new">
            Create job
          </Link>
        )}
      </div>
      <section className="card">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setCursor(null);
            setSearch(draftSearch);
          }}
        >
          <label>
            Find a job
            <input
              maxLength={100}
              value={draftSearch}
              onChange={(e) => setDraftSearch(e.target.value)}
            />
          </label>
          <button className="button secondary">Search jobs</button>
        </form>
        {q.isPending ? (
          <p>Loading jobs…</p>
        ) : q.isError ? (
          <p role="alert">{explain(q.error)}</p>
        ) : q.data.items.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Status</th>
                  <th>Currency</th>
                  <th>Revision</th>
                </tr>
              </thead>
              <tbody>
                {q.data.items.map((j) => (
                  <tr key={j.id}>
                    <td>
                      <Link to={'/app/jobs/' + j.id}>{j.name}</Link>
                    </td>
                    <td>{j.status}</td>
                    <td>{j.currency}</td>
                    <td>{j.revision}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No jobs yet. Your first job will appear here.</p>
        )}
        {cursor && <button onClick={() => setCursor(null)}>First page</button>}
        {q.data?.next_cursor && (
          <button onClick={() => setCursor(q.data.next_cursor)}>Next page</button>
        )}
      </section>
    </>
  );
}
function NewJob({ session, act, busy }: Actions) {
  const [name, setName] = useState('');
  const [currency, setCurrency] = useState('USD');
  if (session.role === 'viewer')
    return <p>Your viewer membership can read jobs. Ask an owner or editor to create one.</p>;
  return (
    <section className="card">
      <h1>Create a job</h1>
      <p>This saves a job record. Files, extraction and export will be enabled in later phases.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void act(async () => {
            const j = await api.create(session, name, currency);
            return j;
          }, '/app/jobs');
        }}
      >
        <label>
          Job name
          <input required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          Currency
          <input
            required
            pattern="[A-Z]{3}"
            maxLength={3}
            value={currency}
            onChange={(e) => setCurrency(e.target.value.toUpperCase())}
          />
        </label>
        <p>Defaults: automatic date order, Excel and CSV formats.</p>
        <button className="button primary" disabled={busy}>
          Save job
        </button>
      </form>
    </section>
  );
}
function Job({ session }: { session: ServerSession }) {
  const { id = '' } = useParams();
  const q = useQuery({
    queryKey: ['foundation', session.workspace_id, 'job', id],
    queryFn: () => api.job(id),
    retry: false,
  });
  if (q.isPending) return <p>Loading job…</p>;
  if (q.isError) return <p role="alert">{explain(q.error)}</p>;
  return (
    <section className="card">
      <span className="eyebrow">Saved job</span>
      <h1>{q.data.name}</h1>
      <dl>
        <dt>Status</dt>
        <dd>{q.data.status}</dd>
        <dt>Currency</dt>
        <dd>{q.data.currency}</dd>
        <dt>Revision</dt>
        <dd>{q.data.revision}</dd>
        <dt>Source review</dt>
        <dd>Not started — no documents uploaded</dd>
      </dl>
      <p>Upload and conversion are next. No financial checks or exports have run on this job.</p>
      <Link to="/app/jobs">Back to jobs</Link>
    </section>
  );
}
function Settings({ session }: { session: ServerSession }) {
  const q = useQuery({
    queryKey: ['foundation', session.workspace_id, 'settings'],
    queryFn: () => api.settings(),
    retry: false,
  });
  return (
    <section className="card">
      <h1>Workspace preferences</h1>
      {q.isError ? (
        <p role="alert">{explain(q.error)}</p>
      ) : q.data ? (
        <>
          <p>
            Currency: {q.data.currency} · Date order: {q.data.date_order}
          </p>
          <p>
            Output date format: {q.data.output_date_format} · Formats: {q.data.outputs.join(', ')}
          </p>
          <p>Editing preferences and BYOK model connections will arrive in Phase 4.</p>
        </>
      ) : (
        <p>Loading preferences…</p>
      )}
    </section>
  );
}
function Team({ session, act, busy }: Actions) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'editor' | 'viewer'>('viewer');
  const [link, setLink] = useState('');
  const [inviteId, setInviteId] = useState('');
  const [cursor, setCursor] = useState<string | null>(null);
  const q = useQuery({
    queryKey: ['foundation', session.workspace_id, 'members', cursor],
    queryFn: () => api.members(cursor),
    enabled: session.role === 'owner',
    retry: false,
  });
  if (session.role !== 'owner') return <p>Team management requires a workspace owner.</p>;
  return (
    <section className="card">
      <h1>Your team</h1>
      {q.isError && <p role="alert">{explain(q.error)}</p>}
      {q.data?.items.map((m) => (
        <div className="team-row" key={m.id}>
          <span>
            {m.display_name} · {m.active ? 'Active' : 'Inactive'}
          </span>
          <label>
            Role
            <select
              aria-label={'Role for ' + m.display_name}
              value={m.role}
              disabled={busy}
              onChange={(e) =>
                void act(() =>
                  api.changeMember(
                    session,
                    m.id,
                    m.version,
                    e.target.value as typeof m.role,
                    m.active,
                  ),
                )
              }
            >
              <option value="owner">Owner</option>
              <option value="editor">Editor</option>
              <option value="viewer">Viewer</option>
            </select>
          </label>
          <button
            disabled={busy}
            onClick={() =>
              void act(() => api.changeMember(session, m.id, m.version, m.role, !m.active))
            }
          >
            {m.active ? 'Revoke access' : 'Restore access'}
          </button>
        </div>
      ))}
      <h2>Invite a teammate</h2>
      <p>
        A link is valid for two days and only for the verified email address entered here. No email
        is sent in this local preview.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void act(async () => {
            const i = await api.invite(session, email, role);
            setLink(i.accept_url);
            setInviteId(i.id);
          });
        }}
      >
        <label>
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Invitation role
          <select value={role} onChange={(e) => setRole(e.target.value as 'editor' | 'viewer')}>
            <option value="viewer">Viewer</option>
            <option value="editor">Editor</option>
          </select>
        </label>
        <button className="button primary" disabled={busy}>
          Create invitation link
        </button>
      </form>
      {link && (
        <label>
          Copy invitation link
          <input readOnly value={link} onFocus={(e) => e.target.select()} />
        </label>
      )}
      {inviteId && (
        <button
          disabled={busy}
          onClick={() =>
            void act(async () => {
              await api.revoke(session, inviteId);
              setInviteId('');
              setLink('');
            })
          }
        >
          Revoke this invitation
        </button>
      )}
      {cursor && <button onClick={() => setCursor(null)}>First team page</button>}
      {q.data?.next_cursor && (
        <button onClick={() => setCursor(q.data.next_cursor)}>Next team page</button>
      )}
    </section>
  );
}
function Invitation({ session, act, busy }: Actions) {
  const [token, setToken] = useState(() => window.location.hash.slice(1));
  return (
    <section className="card">
      <h1>Join a workspace</h1>
      <p>
        Sign in using the verified email address the owner invited. If sign-in removed your link,
        reopen it now.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void act(async () => {
            await api.accept(session, token);
            window.history.replaceState(null, '', '/invite');
            setToken('');
          }, '/app');
        }}
      >
        <label>
          Invitation token
          <input
            type="password"
            autoComplete="off"
            required
            maxLength={512}
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        </label>
        <button className="button primary" disabled={busy}>
          Accept invitation
        </button>
      </form>
    </section>
  );
}
function Health() {
  const q = useQuery({
    queryKey: ['foundation', 'health'],
    queryFn: () => api.health(),
    retry: false,
  });
  return (
    <section className="card">
      <h1>Service health</h1>
      <p>
        Fresh administrator second-factor sign-in required. This view grants no customer document
        access.
      </p>
      {q.isError ? (
        <p role="alert">{explain(q.error)}</p>
      ) : q.data ? (
        <dl>
          {Object.entries(q.data).map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p>Checking services…</p>
      )}
    </section>
  );
}
