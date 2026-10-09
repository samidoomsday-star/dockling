import { useState } from 'react';
import { Link } from 'react-router-dom';
import * as Tabs from '@radix-ui/react-tabs';
import { ShieldCheck, Activity, SlidersHorizontal } from 'lucide-react';
import { useSnapshot, useWorkspace } from '../lib/workspace';
import { Badge, Button, Card, Empty, Field, Heading, Notice } from '../components/ui';
export function Admin() {
  const { role } = useWorkspace();
  const { data } = useSnapshot();
  const [section, setSection] = useState('operations');
  const [profile, setProfile] = useState('generic');
  const [price, setPrice] = useState('');
  const [priceMessage, setPriceMessage] = useState('');
  const [tool, setTool] = useState('');
  if (role !== 'admin')
    return (
      <Empty title="Owner tools">
        <ShieldCheck size={24} />
        <p>
          Choose Owner / admin in the preview role selector to inspect this design. Real access must
          be enforced by the server.
        </p>
        <Link to="/app">Back to customer workspace</Link>
      </Empty>
    );
  if (!data) return null;
  return (
    <>
      <Heading eyebrow="Owner workspace" title="Keep the service running smoothly">
        Operations, configuration and diagnostics in one place.
      </Heading>
      <Notice>
        This role selector is a preview control. It provides no security. Real admin routes require
        server authentication and authorization.
      </Notice>
      <Tabs.Root value={section} onValueChange={setSection}>
        <Tabs.List className="tabs" aria-label="Owner tools">
          <Tabs.Trigger value="operations">Operations</Tabs.Trigger>
          <Tabs.Trigger value="profiles">Bank profiles</Tabs.Trigger>
          <Tabs.Trigger value="pricing">Pricing & configuration</Tabs.Trigger>
          <Tabs.Trigger value="health">Health & models</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="operations">
          <div className="grid three metrics">
            <Card className="blue">
              <Activity />
              <span>Preview conversions</span>
              <strong>{data.jobs.length}</strong>
            </Card>
            <Card className="peach">
              <SlidersHorizontal />
              <span>Need review</span>
              <strong>{data.jobs.filter((j) => j.status === 'needs_review').length}</strong>
            </Card>
            <Card className="mint">
              <ShieldCheck />
              <span>Source checks current</span>
              <strong>{data.jobs.filter((j) => j.sourceChecked).length}</strong>
            </Card>
          </div>
          <Card className="section">
            <h2>Service metrics & exception handling</h2>
            <p>
              Counts reflect this session. Production timing medians, job outcomes and anonymous
              ledgers require server events; no revenue or time savings are invented here.
            </p>
            <p>
              Failed jobs need an explicit recovery path. UNVERIFIABLE exports need an authorized
              exception reason and server audit. Partial deletion never issues a certificate.
            </p>
            <Field label="Exceptional export reason (backend required)">
              <textarea
                disabled
                placeholder="Available only with server-authorized operator review"
              />
            </Field>
            <Button disabled>Authorize exception · backend required</Button>
          </Card>
        </Tabs.Content>
        <Tabs.Content value="profiles">
          <div className="grid two">
            <Card>
              <h2>Known bank layouts</h2>
              <Field label="Profile picker">
                <select value={profile} onChange={(e) => setProfile(e.target.value)}>
                  <option value="generic">Generic fallback</option>
                  <option value="synthetic-text">Synthetic text sample</option>
                  <option value="synthetic-scan">Synthetic scanned sample</option>
                  <option value="synthetic-card">Synthetic card sample</option>
                </select>
              </Field>
              <Badge tone="blue">
                {profile === 'generic' ? 'No universal layout guarantee' : 'Synthetic test profile'}
              </Badge>
              <p>
                Profiles are validated YAML configuration. No real bank layout coverage is implied
                by these samples.
              </p>
              <Button variant="secondary" onClick={() => setTool('profiles')}>
                View test / scaffold instructions
              </Button>
            </Card>
            <Card>
              <h2>Test and scaffold</h2>
              <p>
                Backend profile testing compares known expected rows. Scaffolding can include client
                text and belongs in a private operator workspace.
              </p>
              <Field label="Profile YAML (backend required)">
                <input type="file" disabled accept=".yaml,.yml" />
              </Field>
              {tool === 'profiles' && (
                <Notice>
                  Use the existing CLI locally: <code>stmtconv profiles --help</code>. Test a
                  synthetic layout before registering it. Hosted test and scaffold endpoints are
                  pending.
                </Notice>
              )}
            </Card>
          </div>
        </Tabs.Content>
        <Tabs.Content value="pricing">
          <div className="grid two">
            <Card>
              <h2>Service pricing</h2>
              <p>
                Original service tiers are operator configuration, not approved hosted subscription
                plans.
              </p>
              <Field
                label="Practice basic-tier amount"
                hint="Local form only; does not change config/pricing.yaml."
              >
                <input
                  inputMode="decimal"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                />
              </Field>
              <Button
                variant="secondary"
                onClick={() =>
                  setPriceMessage(
                    /^\d+(\.\d{1,2})?$/.test(price)
                      ? 'Preview value accepted. Backend pricing persistence and quotes are not connected.'
                      : 'Enter an exact nonnegative amount with at most two decimals.',
                  )
                }
              >
                Validate preview value
              </Button>
              {priceMessage && <p role="status">{priceMessage}</p>}
              <p>
                Existing quote configuration supports page tiers, scan/rush surcharges and monthly
                service options.
              </p>
              <code>stmtconv orders --help</code>
            </Card>
            <Card>
              <h2>Configuration & delivery templates</h2>
              <p>
                Limits, category rules, extraction thresholds and delivery wording remain validated
                configuration files. Server editing needs permissions and an audit trail.
              </p>
              <Field label="Configuration YAML (backend required)">
                <input type="file" disabled accept=".yaml,.yml" />
              </Field>
              <p>
                Reserved full-account output and invoicing remain unsupported. Payments, billing and
                live accounting connections need separate integration work.
              </p>
            </Card>
          </div>
        </Tabs.Content>
        <Tabs.Content value="health">
          <div className="grid two">
            <Card>
              <Badge tone="blue">Server state unknown</Badge>
              <h2>Health & diagnostics</h2>
              <p>
                Frontend: rendered in your browser. Processing worker, database, private storage and
                model files have not been connected to this interface.
              </p>
              <Button variant="secondary" onClick={() => setTool('doctor')}>
                Show local diagnostic commands
              </Button>
              {tool === 'doctor' && (
                <div className="inset">
                  <code>stmtconv doctor</code>
                  <p>
                    Run on the device that hosts Python. Check actual output; this UI cannot
                    diagnose that device.
                  </p>
                  <code>stmtconv selftest</code>
                </div>
              )}
              <p>
                Existing selftests use synthetic statements. Production health probes and metrics
                require the backend.
              </p>
            </Card>
            <Card>
              <h2>OCR models & setup</h2>
              <p>
                Docling’s local OCR/layout models do not need an LLM API key. Downloading models is
                a separate setup operation with checksum verification.
              </p>
              <Button variant="secondary" onClick={() => setTool('models')}>
                Show model setup guidance
              </Button>
              {tool === 'models' && (
                <Notice>
                  Follow <strong>docs/DEVICE_SETUP.md</strong> and{' '}
                  <strong>docs/ENVIRONMENT.md</strong> in the repository. Use{' '}
                  <code>stmtconv models --help</code> for the supported setup/check commands. This
                  preview does not download or verify models.
                </Notice>
              )}
              <Link to="/help">Read workflow limitations →</Link>
            </Card>
          </div>
        </Tabs.Content>
      </Tabs.Root>
    </>
  );
}
