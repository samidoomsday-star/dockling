import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { KeyRound, Plug, SlidersHorizontal } from 'lucide-react';
import {
  FoundationApi,
  FoundationError,
  type ServerConnection,
  type ServerSession,
} from './lib/foundation';
const api = new FoundationApi();
const human = (value: string) => value.replaceAll('_', ' ');
const explain = (error: unknown) =>
  error instanceof FoundationError
    ? error.message
    : 'The connection could not be saved. Try again.';

function ConnectionCard({
  connection: c,
  session,
  act,
  busy,
}: {
  connection: ServerConnection;
  session: ServerSession;
  act: (run: () => Promise<unknown>) => Promise<void>;
  busy: boolean;
}) {
  const [key, setKey] = useState('');
  const [manual, setManual] = useState('');
  const [model, setModel] = useState(c.selected_model ?? c.models[0]?.id ?? '');
  const [effort, setEffort] = useState('highest');
  const [terms, setTerms] = useState(c.terms_version ?? '');
  const [confirmed, setConfirmed] = useState(c.terms_confirmed);
  const [revoke, setRevoke] = useState(false);
  const owner = session.role === 'owner';
  const disabled = busy || !owner || !c.active;
  const chosen = c.models.find((m) => m.id === model);
  const levels =
    chosen?.efforts.filter((e) => e === 'provider_default' || c.effort_style !== 'none') ?? [];
  return (
    <section className={'card section ' + (c.active ? 'blue' : '')}>
      <div className="spread">
        <div>
          <h2>{c.name}</h2>
          <p>{c.base_url}</p>
        </div>
        <span className="badge">{c.active ? 'Active' : 'Revoked'}</span>
      </div>
      <div className="grid three">
        <div>
          <KeyRound aria-hidden="true" size={20} />
          <p>
            <strong>
              {c.has_key
                ? 'Key saved securely'
                : c.requires_key
                  ? 'Your key is needed'
                  : 'Key is optional'}
            </strong>
          </p>
        </div>
        <div>
          <Plug aria-hidden="true" size={20} />
          <p>{c.api_style === 'responses' ? 'Responses API' : 'Chat completions API'}</p>
        </div>
        <div>
          <SlidersHorizontal aria-hidden="true" size={20} />
          <p>
            {c.selected_model ?? 'No model selected'} · {human(c.effort)}
          </p>
        </div>
      </div>
      {c.test_code && (
        <p role="status" className="notice">
          {c.test_code === 'MODELS_CONFIRMED'
            ? 'Provider model list confirmed. This does not test paid generation.'
            : c.test_code === 'AI_EFFORT_UNSUPPORTED'
              ? 'The provider no longer advertises your selected effort. Choose a supported setting; your previous choice has been preserved.'
              : 'Your selected model is no longer advertised. Select a current model; your previous choice has been preserved.'}
        </p>
      )}
      {!owner && (
        <p>
          You can see workspace connection settings. A workspace owner manages keys and model
          choices.
        </p>
      )}
      {owner && c.active && (
        <>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const value = key;
              setKey('');
              void act(() =>
                api.connectionAction(session, c.id, c.version, 'key', { api_key: value }),
              );
            }}
          >
            <label>
              Your API key for {c.name}
              <input
                type="password"
                autoComplete="off"
                maxLength={2048}
                value={key}
                onChange={(e) => setKey(e.target.value)}
                disabled={disabled}
              />
            </label>
            <small>
              Encrypted on the server. Saved keys are never shown or stored in your browser.
            </small>
            <button className="button secondary" disabled={disabled || !key.trim()}>
              {c.has_key ? 'Replace saved key' : 'Save API key'}
            </button>
          </form>
          <div className="actions">
            <button
              disabled={disabled || (c.requires_key && !c.has_key)}
              onClick={() =>
                void act(() => api.connectionAction(session, c.id, c.version, 'models'))
              }
            >
              Discover models
            </button>
            <button
              disabled={disabled || (c.requires_key && !c.has_key)}
              onClick={() => void act(() => api.connectionAction(session, c.id, c.version, 'test'))}
            >
              Test connection
            </button>
          </div>
          <p className="fine">
            Discovery/test requests only the provider’s model list. It sends no statement content
            and makes no generation request.
          </p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void act(() =>
                api.connectionAction(session, c.id, c.version, 'models/manual', {
                  model_id: manual,
                }),
              );
            }}
          >
            <label>
              Exact model ID
              <input
                value={manual}
                maxLength={200}
                disabled={disabled}
                onChange={(e) => setManual(e.target.value)}
              />
            </label>
            <button disabled={disabled || !manual.trim()}>Add model manually</button>
          </form>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void act(() =>
                api.connectionAction(session, c.id, c.version, 'selection', {
                  model_id: model,
                  effort,
                }),
              );
            }}
          >
            <div className="grid two">
              <label>
                Model
                <select
                  aria-label={'Model for ' + c.name}
                  value={model}
                  disabled={disabled || !c.models.length}
                  onChange={(e) => {
                    setModel(e.target.value);
                    setEffort('highest');
                  }}
                >
                  <option value="">Choose a model</option>
                  {c.selected_model && !c.models.some((m) => m.id === c.selected_model) && (
                    <option value={c.selected_model}>
                      Previously selected: {c.selected_model}
                    </option>
                  )}
                  {c.models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.id}
                      {m.manual ? ' (manual)' : ''}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Reasoning effort
                <select
                  aria-label={'Reasoning effort for ' + c.name}
                  disabled={disabled || !chosen}
                  value={effort}
                  onChange={(e) => setEffort(e.target.value)}
                >
                  <option value="highest">Highest supported</option>
                  {levels.map((level) => (
                    <option key={level} value={level}>
                      {level === 'provider_default'
                        ? 'Provider default'
                        : level === 'max'
                          ? 'Max'
                          : human(level)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="fine">
              Max appears when the provider reports support. Manual or unknown models use provider
              default. We never silently lower the effort or change your model/provider.
            </p>
            <button className="button primary" disabled={disabled || !chosen}>
              Save model choice
            </button>
          </form>
          <details>
            <summary>Provider terms and sensitive-data permission</summary>
            <p>
              Before any statement processing, confirm that the provider’s terms are suitable for
              the data. Per-job consent and page limits are separate requirements.
            </p>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void act(() =>
                  api.connectionAction(session, c.id, c.version, 'terms', {
                    terms_version: terms,
                    confirmed,
                  }),
                );
              }}
            >
              <label>
                Provider terms URL
                <input
                  type="url"
                  value={terms}
                  disabled={disabled}
                  maxLength={200}
                  onChange={(e) => setTerms(e.target.value)}
                />
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                I reviewed and accept suitable provider terms for this data.
              </label>
              <button disabled={disabled || !terms.trim()}>Save terms confirmation</button>
            </form>
          </details>
          <details>
            <summary>Remove this connection</summary>
            <label className="check">
              <input
                type="checkbox"
                checked={revoke}
                onChange={(e) => setRevoke(e.target.checked)}
              />
              Revoke this connection and erase its saved key.
            </label>
            <button
              disabled={disabled || !revoke}
              onClick={() =>
                void act(() => api.connectionAction(session, c.id, c.version, 'revoke'))
              }
            >
              Revoke connection
            </button>
          </details>
        </>
      )}
    </section>
  );
}
export default function ConnectionsWorkspace({ session }: { session: ServerSession }) {
  const client = useQueryClient();
  const prefix = ['foundation', session.workspace_id, 'connections'];
  const q = useQuery({ queryKey: prefix, queryFn: () => api.connections(), retry: false });
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [style, setStyle] = useState('chat');
  const [requiresKey, setRequiresKey] = useState(true);
  const [effortStyle, setEffortStyle] = useState('reasoning_effort');
  const [schemaStyle, setSchemaStyle] = useState('prompt_json');
  const [tokenField, setTokenField] = useState('max_tokens');
  const [completionRoute, setCompletionRoute] = useState('/chat/completions');
  const [modelsRoute, setModelsRoute] = useState('/models');
  const [temperatureZero, setTemperatureZero] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  async function act(run: () => Promise<unknown>) {
    setBusy(true);
    setMessage('');
    try {
      await run();
      await client.invalidateQueries({ queryKey: prefix });
    } catch (error) {
      setMessage(explain(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Your models, your choice</span>
          <h1>AI connections</h1>
          <p>
            Bring your own provider key and choose an OpenAI-compatible model. Regular text/OCR
            conversion works without an LLM key.
          </p>
        </div>
      </div>
      <div className="notice">
        <p>
          Saving a connection does not send documents or start generation. Optional AI requests are
          controlled from each job, with separate consent and page/request limits. Your provider may
          charge for generation.
        </p>
      </div>
      {(message || q.isError) && <p role="alert">{message || explain(q.error)}</p>}
      {session.role === 'owner' && (
        <section className="card section mint">
          <h2>Add a provider</h2>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void act(() =>
                api.createConnection(session, {
                  name,
                  base_url: url,
                  requires_key: requiresKey,
                  api_style: style,
                  effort_style: effortStyle,
                  schema_style: schemaStyle,
                  token_field: tokenField,
                  completion_route: completionRoute,
                  models_route: modelsRoute,
                  temperature_zero: temperatureZero,
                }),
              );
            }}
          >
            <div className="grid two">
              <label>
                Connection name
                <input
                  value={name}
                  maxLength={80}
                  required
                  disabled={busy}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My provider"
                />
              </label>
              <label>
                OpenAI-compatible base URL
                <input
                  type="url"
                  value={url}
                  maxLength={300}
                  required
                  disabled={busy}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://api.your-provider.com/v1"
                />
              </label>
            </div>
            <details>
              <summary>Advanced compatibility settings</summary>
              <label>
                API style
                <select
                  aria-label="Provider API style"
                  value={style}
                  onChange={(e) => {
                    setStyle(e.target.value);
                    setCompletionRoute(
                      e.target.value === 'responses' ? '/responses' : '/chat/completions',
                    );
                    setTokenField(
                      e.target.value === 'responses' ? 'max_output_tokens' : 'max_tokens',
                    );
                    setEffortStyle(
                      e.target.value === 'responses' ? 'reasoning' : 'reasoning_effort',
                    );
                  }}
                >
                  <option value="chat">Chat completions</option>
                  <option value="responses">Responses</option>
                </select>
              </label>
              <label>
                Model list route
                <input
                  value={modelsRoute}
                  maxLength={100}
                  onChange={(e) => setModelsRoute(e.target.value)}
                />
              </label>
              <label>
                Completion route
                <input
                  value={completionRoute}
                  maxLength={100}
                  onChange={(e) => setCompletionRoute(e.target.value)}
                />
              </label>
              <label>
                Effort field
                <select
                  aria-label="Provider effort field"
                  value={effortStyle}
                  onChange={(e) => setEffortStyle(e.target.value)}
                >
                  <option value="reasoning_effort">reasoning_effort</option>
                  <option value="reasoning">reasoning</option>
                  <option value="none">No effort field</option>
                </select>
              </label>
              <label>
                JSON output support
                <select
                  aria-label="Provider JSON output support"
                  value={schemaStyle}
                  onChange={(e) => setSchemaStyle(e.target.value)}
                >
                  <option value="prompt_json">Plain JSON prompt</option>
                  <option value="json_object">JSON object</option>
                  <option value="json_schema">JSON schema</option>
                </select>
              </label>
              <label>
                Token limit field
                <select
                  aria-label="Provider token limit field"
                  value={tokenField}
                  onChange={(e) => setTokenField(e.target.value)}
                >
                  <option value="max_tokens">max_tokens</option>
                  <option value="max_completion_tokens">max_completion_tokens</option>
                  <option value="max_output_tokens">max_output_tokens</option>
                </select>
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={temperatureZero}
                  onChange={(e) => setTemperatureZero(e.target.checked)}
                />
                This provider supports temperature set to zero.
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={requiresKey}
                  onChange={(e) => setRequiresKey(e.target.checked)}
                />
                This provider requires an API key.
              </label>
            </details>
            <button className="button primary" disabled={busy || !name.trim() || !url.trim()}>
              Add connection
            </button>
          </form>
        </section>
      )}
      {q.isPending && <p>Loading your connections…</p>}
      {q.data?.items.length === 0 && (
        <section className="card section">
          <h2>No providers connected yet</h2>
          <p>Add your provider above. You can keep using regular offline conversion meanwhile.</p>
        </section>
      )}
      {q.data?.items.map((c) => (
        <ConnectionCard
          key={c.id + ':' + c.version}
          connection={c}
          session={session}
          act={act}
          busy={busy}
        />
      ))}
    </>
  );
}
