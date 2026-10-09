import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Files, ScanLine, CheckCircle2, ArrowRight, UploadCloud } from 'lucide-react';
import { useAction, useSnapshot, useWorkspace } from '../lib/workspace';
import {
  Badge,
  Button,
  Card,
  Check,
  Empty,
  Field,
  Heading,
  LinkButton,
  Notice,
} from '../components/ui';
import { outputs, statusLabels, type Job, type NewJob, type Output } from '../lib/types';
import { errorMessage, validateNewJob } from '../lib/validation';
export function JobsTable({ jobs }: { jobs: Job[] }) {
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Conversions table">
      <table>
        <caption className="sr-only">Conversions in this workspace</caption>
        <thead>
          <tr>
            <th>Conversion</th>
            <th>Status</th>
            <th>Source</th>
            <th>Revision</th>
            <th>
              <span className="sr-only">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id}>
              <td>
                <Link to={'/app/jobs/' + j.id}>
                  <strong>{j.name}</strong>
                </Link>
                <small>
                  {j.currency} · {j.rows.length} sample rows
                </small>
              </td>
              <td>
                <Badge
                  tone={
                    j.status === 'needs_review'
                      ? 'peach'
                      : j.status === 'delivered'
                        ? 'mint'
                        : 'blue'
                  }
                >
                  {statusLabels[j.status]}
                </Badge>
              </td>
              <td>{j.files.length ? j.files.map((f) => f.kind).join(', ') : 'Removed'}</td>
              <td>{j.revision}</td>
              <td>
                <Link aria-label={'Open ' + j.name} to={'/app/jobs/' + j.id}>
                  <ArrowRight size={18} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Dashboard() {
  const { data } = useSnapshot();
  if (!data) return null;
  const active = data.jobs.filter((j) => j.status !== 'closed');
  return (
    <>
      <Heading
        eyebrow="A little clarity goes a long way"
        title="Good to see you."
        actions={<LinkButton to="/app/new">New conversion</LinkButton>}
      >
        Here’s what needs your attention in Sample Studio.
      </Heading>
      <div className="grid three metrics">
        {[
          [Files, 'Active conversions', active.length, 'blue'],
          [
            ScanLine,
            'Waiting for review',
            active.filter((j) => j.status === 'needs_review').length,
            'peach',
          ],
          [
            CheckCircle2,
            'Packages ready',
            active.filter((j) => j.status === 'delivered').length,
            'mint',
          ],
        ].map(([Icon, title, value, tone]) => {
          const I = Icon as typeof Files;
          return (
            <Card key={String(title)} className={String(tone)}>
              <I size={22} />
              <span>{String(title)}</span>
              <strong>{String(value)}</strong>
              <small>From this preview session</small>
            </Card>
          );
        })}
      </div>
      <div className="split section">
        <Card>
          <div className="spread">
            <h2>Your conversions</h2>
            <Link to="/app/jobs">View all →</Link>
          </div>
          <JobsTable jobs={data.jobs.slice(0, 5)} />
        </Card>
        <Card className="next-step">
          <Badge tone="peach">Your next step</Badge>
          <h2>
            One small correction.
            <br />A much clearer result.
          </h2>
          <p>
            The January sample has an amount difference. Compare it with the source, save your
            correction and check the rows before export.
          </p>
          <LinkButton to="/app/jobs/sample-review">Continue sample review</LinkButton>
          <p className="fine">Financial checks do not replace source review.</p>
        </Card>
      </div>
    </>
  );
}
export function Jobs() {
  const { data } = useSnapshot();
  const [params, setParams] = useSearchParams();
  const search = params.get('q') ?? '';
  const status = params.get('status') ?? 'all';
  function setSearch(value: string) {
    setParams(
      (prev) => {
        prev.set('q', value);
        return prev;
      },
      { replace: true },
    );
  }
  function setStatus(value: string) {
    setParams(
      (prev) => {
        prev.set('status', value);
        return prev;
      },
      { replace: true },
    );
  }
  if (!data) return null;
  const jobs = data.jobs.filter(
    (j) =>
      j.name.toLowerCase().includes(search.toLowerCase()) &&
      (status === 'all' || j.status === status),
  );
  return (
    <>
      <Heading
        eyebrow="Your workspace"
        title="Conversions"
        actions={<LinkButton to="/app/new">New conversion</LinkButton>}
      >
        Find, review and manage your statement work.
      </Heading>
      <Card>
        <div className="filters">
          <Field label="Search conversions">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name"
            />
          </Field>
          <Field label="Status">
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="all">All statuses</option>
              {Object.entries(statusLabels).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {jobs.length ? (
          <JobsTable jobs={jobs} />
        ) : (
          <Empty title="No conversions match">
            <p>Try a different name or status.</p>
          </Empty>
        )}
      </Card>
    </>
  );
}
const defaults: NewJob = {
  name: 'Practice statement',
  files: [],
  currency: 'USD',
  dateOrder: 'YMD',
  outputs: ['excel', 'csv'],
  merge: false,
  accountGroup: '',
  accountConfirmed: false,
  categorize: false,
  combine: false,
  profile: 'generic',
  engine: 'auto',
  pages: '',
};
export function Upload() {
  const { api } = useWorkspace();
  const { run, busy } = useAction();
  const navigate = useNavigate();
  const { data } = useSnapshot();
  const [form, setForm] = useState<NewJob>(() => ({
    ...defaults,
    currency: data?.settings.currency ?? defaults.currency,
    outputs: data?.settings.outputs ?? defaults.outputs,
  }));
  const [step, setStep] = useState(1);
  const [safe, setSafe] = useState(false);
  const [error, setError] = useState('');
  function set<K extends keyof NewJob>(k: K, value: NewJob[K]) {
    setForm((prev) => ({ ...prev, [k]: value }));
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    try {
      validateNewJob(form);
      if (!safe) throw new Error('Confirm the files are synthetic before continuing.');
      if (api.mode !== 'demo')
        throw new Error(
          'Real intake requires the backend upload endpoint; this frontend does not transmit files.',
        );
      await run(async () => {
        const job = await api.create(form);
        navigate('/app/jobs/' + job.id);
      }, 'Practice conversion created. Selected file content was not uploaded.');
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  return (
    <>
      <Heading eyebrow="Let’s make things clearer" title="New conversion">
        A guided intake with just the options you need.
      </Heading>
      <div className="stepper" aria-label="Intake steps">
        {['Choose files', 'Choose outputs', 'Confirm'].map((s, i) => (
          <span key={s} className={step === i + 1 ? 'current' : ''}>
            {i + 1} · {s}
          </span>
        ))}
      </div>
      <form onSubmit={(e) => void submit(e)}>
        <Card>
          {step === 1 ? (
            <>
              <h2>Bring your sample statements</h2>
              <Notice>
                Preview only: select synthetic files. Content stays on your device and is not
                processed. The review will use the bundled fictional statement.
              </Notice>
              <div className="dropzone">
                <UploadCloud size={35} />
                <Field label="Choose synthetic files">
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff"
                    multiple
                    onChange={(e) => {
                      const names = Array.from(e.target.files ?? []).map((f) => f.name);
                      if (names.some((n) => !/\.(pdf|png|jpe?g|tiff?)$/i.test(n))) {
                        setError('Use PDF, JPG, PNG or TIFF samples.');
                        return;
                      }
                      set('files', names);
                      setError('');
                    }}
                  />
                </Field>
                <p>PDF · JPG · PNG · TIFF</p>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => set('files', ['synthetic-january.pdf'])}
                >
                  Use bundled synthetic statement
                </Button>
              </div>
              <ul className="file-list">
                {form.files.map((name, i) => (
                  <li key={i}>
                    {name}
                    <div className="actions">
                      <button
                        type="button"
                        disabled={i === 0}
                        aria-label={'Move ' + name + ' up'}
                        onClick={() => {
                          const files = [...form.files];
                          [files[i - 1], files[i]] = [files[i], files[i - 1]];
                          set('files', files);
                        }}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        aria-label={'Remove ' + name}
                        onClick={() =>
                          set(
                            'files',
                            form.files.filter((_, j) => j !== i),
                          )
                        }
                      >
                        Remove
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
              <Field label="Conversion name">
                <input
                  maxLength={120}
                  value={form.name}
                  onChange={(e) => set('name', e.target.value)}
                />
              </Field>
              <Check checked={safe} onChange={() => setSafe(!safe)}>
                These are fictional samples; I am not selecting real client documents.
              </Check>
              <details>
                <summary>File handling and password-protected PDFs</summary>
                <p>
                  Real intake will check file signatures, rotate images, inspect page limits and
                  detect blank pages. Filename extensions alone do not establish a valid PDF.
                </p>
                <Field label="PDF password (backend required)">
                  <input
                    type="password"
                    disabled
                    placeholder="Not collected in preview"
                    autoComplete="off"
                  />
                </Field>
                <Check checked={form.combine} onChange={() => set('combine', !form.combine)}>
                  Combine ordered images into one statement
                </Check>
                <p>
                  Otherwise each file represents one statement. Use the arrows above to set order.
                </p>
              </details>
            </>
          ) : step === 2 ? (
            <>
              <h2>Choose how you’ll use the result</h2>
              <div className="output-grid">
                {outputs.map((o) => (
                  <label className="output-option" key={o.id}>
                    <input
                      type="checkbox"
                      checked={form.outputs.includes(o.id)}
                      onChange={() =>
                        set(
                          'outputs',
                          form.outputs.includes(o.id)
                            ? form.outputs.filter((x) => x !== o.id)
                            : ([...form.outputs, o.id] as Output[]),
                        )
                      }
                    />
                    <div>
                      <strong>{o.name}</strong>
                      <small>{o.detail}</small>
                    </div>
                  </label>
                ))}
              </div>
              <div className="grid two section">
                <Field label="Currency">
                  <input
                    value={form.currency}
                    maxLength={3}
                    onChange={(e) => set('currency', e.target.value.toUpperCase())}
                  />
                </Field>
                <Field label="Source date order">
                  <select value={form.dateOrder} onChange={(e) => set('dateOrder', e.target.value)}>
                    <option value="YMD">Year / month / day</option>
                    <option value="DMY">Day / month / year</option>
                    <option value="MDY">Month / day / year</option>
                  </select>
                </Field>
              </div>
              <Check checked={form.categorize} onChange={() => set('categorize', !form.categorize)}>
                Apply category rules to the result
              </Check>
              <Check checked={form.merge} onChange={() => set('merge', !form.merge)}>
                Merge statements belonging to one account
              </Check>
              {(form.merge || form.outputs.includes('ofx')) && (
                <div className="inset">
                  <Field
                    label="Private account group"
                    hint="Use a label, not a full account number."
                  >
                    <input
                      value={form.accountGroup}
                      onChange={(e) => set('accountGroup', e.target.value)}
                    />
                  </Field>
                  <Check
                    checked={form.accountConfirmed}
                    onChange={() => set('accountConfirmed', !form.accountConfirmed)}
                  >
                    I confirmed these statements share the same account and currency.
                  </Check>
                  <p>
                    Merging needs period, overlap and opening/closing balance checks on the server.
                    OFX also needs confirmed institution/account details.
                  </p>
                </div>
              )}
              <details>
                <summary>Advanced extraction options</summary>
                <div className="grid two">
                  <Field label="Bank profile">
                    <select value={form.profile} onChange={(e) => set('profile', e.target.value)}>
                      <option value="generic">Generic layout</option>
                      <option value="synthetic">Synthetic sample profile</option>
                    </select>
                  </Field>
                  <Field label="Extraction engine">
                    <select value={form.engine} onChange={(e) => set('engine', e.target.value)}>
                      <option value="auto">Automatic</option>
                      <option value="text">PDF text</option>
                      <option value="docling">Docling OCR/layout</option>
                    </select>
                  </Field>
                  <Field label="Page groups" hint="Example: 1-4,5-9">
                    <input value={form.pages} onChange={(e) => set('pages', e.target.value)} />
                  </Field>
                </div>
                <p>
                  Options are captured for the API contract. The preview does not run an extraction
                  engine, combine files or infer a bank layout.
                </p>
              </details>
            </>
          ) : (
            <>
              <h2>Ready for a practice run</h2>
              <dl className="facts">
                <dt>Files</dt>
                <dd>{form.files.join(', ') || 'None selected'}</dd>
                <dt>Outputs</dt>
                <dd>
                  {form.outputs.map((id) => outputs.find((o) => o.id === id)?.name).join(', ') ||
                    'None selected'}
                </dd>
                <dt>Statement</dt>
                <dd>
                  {form.currency} · {form.dateOrder} · {form.engine}
                </dd>
                <dt>AI</dt>
                <dd>Off. No external provider will be contacted.</dd>
              </dl>
              <Notice>
                All review rows come from our two-row synthetic fixture, regardless of your chosen
                files. This is a frontend workflow test.
              </Notice>
            </>
          )}
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <div className="actions section">
            {step > 1 && (
              <Button variant="secondary" type="button" onClick={() => setStep(step - 1)}>
                Back
              </Button>
            )}
            {step < 3 ? (
              <Button
                key="next-step"
                type="button"
                disabled={step === 1 && (!safe || !form.files.length)}
                onClick={() => {
                  setError('');
                  setStep(step + 1);
                }}
              >
                Continue
              </Button>
            ) : (
              <Button key="confirm-create" disabled={busy} type="submit">
                Create practice conversion
              </Button>
            )}
          </div>
        </Card>
      </form>
    </>
  );
}
