import { useState, type FormEvent } from 'react';
import { useAction, useSnapshot, useWorkspace } from '../lib/workspace';
import { Button, Card, Check, Field, Heading, Notice } from '../components/ui';
import { outputs, type Rule, type Settings as Preferences } from '../lib/types';
export function Categories() {
  const { data } = useSnapshot();
  return data ? <CategoryEditor initial={data.rules} /> : null;
}
function CategoryEditor({ initial }: { initial: Rule[] }) {
  const [rules, setRules] = useState(initial);
  const [preview, setPreview] = useState('Fake café, grocery');
  const match = rules.find(
    (r) => r.match.trim() && preview.toLowerCase().includes(r.match.toLowerCase()),
  );
  const { api } = useWorkspace();
  const { run, busy } = useAction();
  function update(id: string, key: keyof Rule, value: string) {
    setRules((prev) => prev.map((r) => (r.id === id ? { ...r, [key]: value } : r)));
  }
  return (
    <>
      <Heading eyebrow="Organize your transactions" title="Categories">
        Ordered matching rules keep your bookkeeping consistent.
      </Heading>
      <Card>
        <Notice>
          Rule editing is interactive. Applying rules, regex matching and per-job override files
          require the Python integration; preview exports remain fixed.
        </Notice>
        {rules.map((r, i) => (
          <div className="rule-row" key={r.id}>
            <span className="rule-order">{i + 1}</span>
            <Field label="Category">
              <input
                value={r.category}
                onChange={(e) => update(r.id, 'category', e.target.value)}
              />
            </Field>
            <Field label="Keyword or regex">
              <input value={r.match} onChange={(e) => update(r.id, 'match', e.target.value)} />
            </Field>
            <Field label="Direction">
              <select
                value={r.direction}
                onChange={(e) => update(r.id, 'direction', e.target.value)}
              >
                <option value="both">Both</option>
                <option value="debit">Debit</option>
                <option value="credit">Credit</option>
              </select>
            </Field>
            <button
              aria-label={'Move rule ' + (i + 1) + ' up'}
              disabled={i === 0}
              onClick={() => {
                const next = [...rules];
                [next[i - 1], next[i]] = [next[i], next[i - 1]];
                setRules(next);
              }}
            >
              ↑
            </button>
            <button
              aria-label={'Delete rule ' + (i + 1)}
              onClick={() => setRules(rules.filter((x) => x.id !== r.id))}
            >
              Remove
            </button>
          </div>
        ))}
        <div className="actions section">
          <Button
            variant="secondary"
            onClick={() =>
              setRules([
                ...rules,
                { id: crypto.randomUUID(), category: '', match: '', direction: 'both' },
              ])
            }
          >
            Add rule
          </Button>
          <Button
            disabled={busy}
            onClick={() =>
              void run(() => api.saveRules(rules), 'Category rules saved in this preview session.')
            }
          >
            Save category rules
          </Button>
        </div>
        <div className="inset">
          <h3>Quick keyword preview</h3>
          <Field label="Sample description">
            <input value={preview} onChange={(e) => setPreview(e.target.value)} />
          </Field>
          <p>
            First keyword match: <strong>{match?.category ?? 'No match'}</strong>
          </p>
          <p className="fine">
            This checks keywords only. Direction and regular expressions are validated by the Python
            matching service during integration.
          </p>
        </div>
        <details>
          <summary>Job-specific overrides</summary>
          <p>
            The Python workflow accepts per-job category overrides. The hosted upload/validation
            endpoint will preserve the same ordering and direction rules.
          </p>
          <Field label="Category override file (backend required)">
            <input type="file" disabled accept=".yaml,.yml" />
          </Field>
        </details>
      </Card>
    </>
  );
}
export function Settings() {
  const { data } = useSnapshot();
  return data ? <SettingsEditor initial={data.settings} /> : null;
}
function SettingsEditor({ initial }: { initial: Preferences }) {
  const [settings, setSettings] = useState(initial);
  const { api } = useWorkspace();
  const { run, busy } = useAction();
  async function save(e: FormEvent) {
    e.preventDefault();
    await run(() => api.saveSettings(settings), 'Preferences saved for this preview session.');
  }
  return (
    <>
      <Heading eyebrow="Make it your own" title="Workspace settings">
        Simple defaults, with advanced choices available when you need them.
      </Heading>
      <form onSubmit={(e) => void save(e)}>
        <Card>
          <h2>Conversion defaults</h2>
          <div className="grid two">
            <Field label="Default currency">
              <input
                value={settings.currency}
                maxLength={3}
                onChange={(e) =>
                  setSettings({ ...settings, currency: e.target.value.toUpperCase() })
                }
              />
            </Field>
            <Field label="Accounting date format">
              <select
                value={settings.dateFormat}
                onChange={(e) => setSettings({ ...settings, dateFormat: e.target.value })}
              >
                <option value="%m/%d/%Y">Month/day/year</option>
                <option value="%d/%m/%Y">Day/month/year</option>
                <option value="%Y-%m-%d">Year-month-day</option>
              </select>
            </Field>
            <Field label="Source transaction order">
              <select
                value={settings.sourceOrder}
                onChange={(e) => setSettings({ ...settings, sourceOrder: e.target.value })}
              >
                <option value="auto">Automatic</option>
                <option value="ascending">Oldest first</option>
                <option value="descending">Newest first</option>
              </select>
            </Field>
            <Field
              label="Retention preference (days)"
              hint="A preview preference, not an active deletion schedule."
            >
              <input
                type="number"
                min={0}
                max={365}
                value={settings.retentionDays}
                onChange={(e) =>
                  setSettings({ ...settings, retentionDays: Number(e.target.value) })
                }
              />
            </Field>
          </div>
          <h3>Default output formats</h3>
          {outputs.map((o) => (
            <Check
              key={o.id}
              checked={settings.outputs.includes(o.id)}
              onChange={() =>
                setSettings({
                  ...settings,
                  outputs: settings.outputs.includes(o.id)
                    ? settings.outputs.filter((x) => x !== o.id)
                    : [...settings.outputs, o.id],
                })
              }
            >
              {o.name}
            </Check>
          ))}
          <Button type="submit" disabled={busy}>
            Save preferences
          </Button>
        </Card>
      </form>
      <Card className="section">
        <h2>Account and security</h2>
        <p>
          Profile, password reset, invitations and server-enforced permissions will be connected
          with the authentication backend. No account credentials are collected in this preview.
        </p>
        <Notice>
          Reloading resets all demo preferences and jobs. The real application needs encrypted
          private storage and a verified retention worker.
        </Notice>
        <Button
          variant="secondary"
          onClick={() =>
            void run(() => api.reset(), 'Sample workspace reset.').then((ok) => {
              if (ok) window.location.reload();
            })
          }
        >
          Reset sample workspace
        </Button>
      </Card>
    </>
  );
}
