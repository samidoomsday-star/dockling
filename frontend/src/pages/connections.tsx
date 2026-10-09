import { useState, type FormEvent } from 'react';
import { Plug, Plus, Trash2 } from 'lucide-react';
import { useAction, useSnapshot, useWorkspace } from '../lib/workspace';
import { Badge, Button, Card, Check, Empty, Field, Heading, Modal, Notice } from '../components/ui';
import { highestEffort, errorMessage, validateConnection } from '../lib/validation';
import type { Connection, Effort } from '../lib/types';
const effortLabels: Record<Effort, string> = {
  provider_default: 'Provider default',
  minimal: 'Minimal',
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  xhigh: 'Extra high',
  max: 'Max',
};
function fresh(): Connection {
  return {
    id: crypto.randomUUID(),
    name: 'My compatible provider',
    url: 'https://provider.example/v1',
    style: 'chat',
    model: '',
    effort: 'provider_default',
    models: [],
    terms: false,
    schema: 'prompt_json',
    effortStyle: 'reasoning_effort',
    tokenField: 'max_tokens',
    modelsRoute: '/models',
    completionRoute: '/chat/completions',
    temperature: false,
  };
}
export function Connections() {
  const { api } = useWorkspace();
  const { data } = useSnapshot();
  const { run, busy } = useAction();
  const [draft, setDraft] = useState<Connection | null>(null);
  const [manual, setManual] = useState('');
  const [reference, setReference] = useState('');
  const [documentMax, setDocumentMax] = useState(false);
  const [error, setError] = useState('');
  const [removing, setRemoving] = useState<Connection | null>(null);
  if (!data) return null;
  function change<K extends keyof Connection>(key: K, value: Connection[K]) {
    setDraft((prev) => (prev ? { ...prev, [key]: value } : null));
  }
  function selectModel(id: string) {
    if (!draft) return;
    const model = draft.models.find((m) => m.id === id);
    setDraft({
      ...draft,
      model: id,
      effort:
        draft.effortStyle === 'none' ? 'provider_default' : highestEffort(model?.efforts ?? []),
    });
  }
  function addModel() {
    if (!draft || !manual.trim()) return;
    if (documentMax && !/^https:\/\//.test(reference)) {
      setError('Add an HTTPS provider documentation reference for Max support.');
      return;
    }
    const id = manual.trim();
    const model = {
      id,
      efforts: documentMax
        ? (['provider_default', 'max'] as Effort[])
        : (['provider_default'] as Effort[]),
      source: documentMax ? ('operator_documentation' as const) : ('unknown' as const),
      reference: documentMax ? reference : '',
    };
    setDraft({
      ...draft,
      models: [...draft.models.filter((m) => m.id !== id), model],
      model: id,
      effort: draft.effortStyle === 'none' ? 'provider_default' : highestEffort(model.efforts),
    });
    setManual('');
    setError('');
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!draft) return;
    setError('');
    try {
      validateConnection(draft);
      if (
        await run(
          () => api.saveConnection(draft),
          'Connection configuration saved in memory. No key stored or provider contacted.',
        )
      )
        setDraft(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  return (
    <>
      <Heading
        eyebrow="Optional AI"
        title="Your models, connected your way"
        actions={
          <Button
            onClick={() => {
              setDraft(fresh());
              setError('');
            }}
          >
            <Plus size={17} />
            Add connection
          </Button>
        }
      >
        Bring your own OpenAI-compatible provider. Keep model choice and effort visible.
      </Heading>
      <Notice>
        Preview configuration only. API keys are not accepted or stored here, and discovery/test
        buttons do not contact a provider.
      </Notice>
      <div className="grid two section">
        {data.connections.map((c) => (
          <Card key={c.id} className="connection-card">
            <div className="spread">
              <span className="feature-icon lavender">
                <Plug />
              </span>
              <Badge tone="lavender">
                {c.style === 'chat' ? 'Chat Completions' : 'Responses API'}
              </Badge>
            </div>
            <h2>{c.name}</h2>
            <p className="url">{c.url}</p>
            <dl className="facts">
              <dt>Model</dt>
              <dd>{c.model}</dd>
              <dt>Effort</dt>
              <dd>{effortLabels[c.effort]}</dd>
              <dt>Provider terms</dt>
              <dd>{c.terms ? 'Acknowledged in preview' : 'Acknowledgement needed'}</dd>
              <dt>Key</dt>
              <dd>Not stored · secure backend required</dd>
            </dl>
            <div className="actions">
              <Button
                variant="secondary"
                onClick={() => {
                  setDraft(structuredClone(c));
                  setError('');
                }}
              >
                Edit connection
              </Button>
              <Button
                variant="secondary"
                onClick={() => setRemoving(c)}
                aria-label={'Remove ' + c.name}
              >
                <Trash2 size={16} />
              </Button>
            </div>
          </Card>
        ))}
      </div>
      {!data.connections.length && (
        <Empty title="No AI connection">
          <p>
            You can still process locally using text/OCR in the Python application without an LLM
            key.
          </p>
        </Empty>
      )}
      <Modal
        open={!!draft}
        onOpenChange={(open) => {
          if (!open) setDraft(null);
        }}
        title="OpenAI-compatible connection"
        description="Set a provider, select a model and choose an explicitly supported effort."
      >
        {draft && (
          <form onSubmit={(e) => void save(e)}>
            <div className="grid two">
              <Field label="Connection nickname">
                <input value={draft.name} onChange={(e) => change('name', e.target.value)} />
              </Field>
              <Field label="API base URL">
                <input
                  type="url"
                  value={draft.url}
                  onChange={(e) => change('url', e.target.value)}
                  placeholder="https://provider.example/v1"
                />
              </Field>
              <Field label="API style">
                <select
                  value={draft.style}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      style: e.target.value as Connection['style'],
                      completionRoute:
                        e.target.value === 'responses' ? '/responses' : '/chat/completions',
                      tokenField:
                        e.target.value === 'responses' ? 'max_output_tokens' : 'max_tokens',
                      effortStyle:
                        e.target.value === 'responses' ? 'reasoning' : 'reasoning_effort',
                    })
                  }
                >
                  <option value="chat">Chat Completions</option>
                  <option value="responses">Responses API</option>
                </select>
              </Field>
              <Field label="API key (secure backend required)">
                <input
                  type="password"
                  disabled
                  autoComplete="off"
                  placeholder="Do not enter real keys in preview"
                />
              </Field>
            </div>
            <div className="inset">
              <div className="spread">
                <h3>Model catalog</h3>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() =>
                    setDraft({
                      ...draft,
                      models: [
                        {
                          id: 'documented-sample-model',
                          efforts: ['provider_default', 'low', 'high', 'max'],
                          source: 'operator_documentation',
                          reference: 'Synthetic fixture, not provider evidence',
                        },
                      ],
                      model: 'documented-sample-model',
                      effort: draft.effortStyle === 'none' ? 'provider_default' : 'max',
                    })
                  }
                >
                  Load sample catalog
                </Button>
              </div>
              <p>
                Real discovery uses provider metadata. A model ID alone does not prove effort
                support.
              </p>
              <div className="grid two">
                <Field label="Model picker">
                  <select value={draft.model} onChange={(e) => selectModel(e.target.value)}>
                    <option value="">Choose a model</option>
                    {draft.models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.id}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Reasoning effort">
                  <select
                    value={draft.effort}
                    onChange={(e) => change('effort', e.target.value as Effort)}
                  >
                    {(
                      draft.models.find((m) => m.id === draft.model)?.efforts ?? [
                        'provider_default',
                      ]
                    )
                      .filter((e) => draft.effortStyle !== 'none' || e === 'provider_default')
                      .map((e) => (
                        <option key={e} value={e}>
                          {effortLabels[e]}
                        </option>
                      ))}
                  </select>
                </Field>
              </div>
              <p className="fine">
                Highest documented effort is selected automatically. Max is offered only when
                capability evidence is recorded. Unknown models use provider default.
              </p>
              <details>
                <summary>Add a model manually</summary>
                <Field label="Manual model ID">
                  <input value={manual} onChange={(e) => setManual(e.target.value)} />
                </Field>
                <Check checked={documentMax} onChange={() => setDocumentMax(!documentMax)}>
                  Provider documentation explicitly supports Max for this model.
                </Check>
                {documentMax && (
                  <Field label="Provider documentation URL">
                    <input
                      type="url"
                      value={reference}
                      onChange={(e) => setReference(e.target.value)}
                    />
                  </Field>
                )}
                <Button type="button" variant="secondary" onClick={addModel}>
                  Add model to picker
                </Button>
              </details>
            </div>
            <Check checked={draft.terms} onChange={() => change('terms', !draft.terms)}>
              I reviewed the provider’s data handling terms and confirmed they are suitable for the
              intended use.
            </Check>
            <details>
              <summary>Advanced adapter settings</summary>
              <div className="grid two">
                <Field label="Structured output">
                  <select
                    value={draft.schema}
                    onChange={(e) => change('schema', e.target.value as Connection['schema'])}
                  >
                    <option value="prompt_json">Prompt JSON</option>
                    <option value="json_object">JSON object</option>
                    <option value="json_schema">JSON schema</option>
                  </select>
                </Field>
                <Field label="Effort parameter">
                  <select
                    value={draft.effortStyle}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        effortStyle: e.target.value as Connection['effortStyle'],
                        effort: e.target.value === 'none' ? 'provider_default' : draft.effort,
                      })
                    }
                  >
                    <option value="reasoning_effort">reasoning_effort</option>
                    <option value="reasoning">reasoning object</option>
                    <option value="none">No effort parameter</option>
                  </select>
                </Field>
                <Field label="Output token field">
                  <select
                    value={draft.tokenField}
                    onChange={(e) =>
                      change('tokenField', e.target.value as Connection['tokenField'])
                    }
                  >
                    {['max_tokens', 'max_completion_tokens', 'max_output_tokens'].map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Models route">
                  <input
                    value={draft.modelsRoute}
                    onChange={(e) => change('modelsRoute', e.target.value)}
                  />
                </Field>
                <Field label="Completion route">
                  <input
                    value={draft.completionRoute}
                    onChange={(e) => change('completionRoute', e.target.value)}
                  />
                </Field>
              </div>
              <Check
                checked={draft.temperature}
                onChange={() => change('temperature', !draft.temperature)}
              >
                Include temperature parameter
              </Check>
            </details>
            {error && (
              <p role="alert" className="error">
                {error}
              </p>
            )}
            <div className="actions section">
              <Button type="submit" disabled={busy}>
                Save preview connection
              </Button>
              <Button type="button" variant="secondary" disabled>
                Test provider · backend required
              </Button>
            </div>
          </form>
        )}
      </Modal>
      <Modal
        open={!!removing}
        onOpenChange={(open) => {
          if (!open) setRemoving(null);
        }}
        title="Remove connection?"
        description="This removes the sample configuration. Real key revocation requires the backend."
      >
        <Button
          variant="danger"
          disabled={busy}
          onClick={() => {
            if (removing)
              void run(() => api.removeConnection(removing.id), 'Preview connection removed.').then(
                (ok) => {
                  if (ok) setRemoving(null);
                },
              );
          }}
        >
          Confirm connection removal
        </Button>
      </Modal>
    </>
  );
}
