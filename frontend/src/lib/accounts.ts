import { z } from 'zod';
import { FoundationApi, type ServerSession } from './foundation';

const uuid = z.uuid();
const integer = z.number().int().nonnegative();
const allowance = z
  .object({
    status: z.string(),
    processing_allowed: z.boolean(),
    page_limit: integer,
    seat_limit: integer,
    valid_until: z.string().nullable(),
  })
  .strict();
const invoice = z
  .object({
    id: uuid,
    version: integer,
    status: z.enum(['draft', 'issued', 'paid', 'failed', 'refunded', 'cancelled']),
    plan_name: z.string(),
    amount: z.string().regex(/^(0|[1-9][0-9]*)\.[0-9]{2}$/),
    currency: z.string().regex(/^[A-Z]{3}$/),
    valid_until: z.string(),
    created_at: z.string(),
    payment_method: z.literal('manual_invoice'),
  })
  .strict();
const plan = z
  .object({
    id: uuid,
    name: z.string(),
    pages_per_month: integer,
    seats: integer,
    monthly_amount: z.string().regex(/^(0|[1-9][0-9]*)\.[0-9]{2}$/),
    currency: z.string(),
    approved_for_customers: z.boolean(),
  })
  .strict();
const serviceRequest = z
  .object({
    id: uuid,
    kind: z.enum(['support', 'plan', 'privacy_export', 'privacy_remove']),
    message: z.string(),
    status: z.enum(['open', 'answered', 'closed']),
    version: integer,
    response: z.string().nullable(),
    created_at: z.string(),
  })
  .strict();
export const usageSchema = allowance
  .extend({
    period: z.string(),
    pages_used: integer,
    pages_reserved: integer,
    pages_remaining: integer,
    active_seats: integer,
    pending_invitations: integer,
    ai_charges_included: z.literal(false),
    inspection_reservation_max: integer,
  })
  .strict();
export type AccountInvoice = z.infer<typeof invoice>;
export type AccountRequest = z.infer<typeof serviceRequest>;
export class AccountsApi extends FoundationApi {
  usage() {
    return this.request('/usage', usageSchema);
  }
  createWorkspace(s: ServerSession, name: string) {
    return this.request(
      '/workspaces',
      z
        .object({ id: uuid, name: z.string(), role: z.enum(['owner', 'editor', 'viewer']) })
        .strict(),
      s,
      { name },
      'POST',
    );
  }
  billing() {
    return this.request(
      '/billing',
      z
        .object({
          entitlement: allowance,
          invoices: z.array(invoice),
          checkout_available: z.literal(false),
          portal_available: z.literal(false),
          mode: z.literal('manual_invoice'),
        })
        .strict(),
    );
  }
  plans() {
    return this.request(
      '/plans',
      z.object({ items: z.array(plan), offers_enabled: z.boolean() }).strict(),
    );
  }
  invitations() {
    return this.request(
      '/invitations',
      z
        .object({
          items: z.array(
            z
              .object({
                id: uuid,
                email: z.string(),
                role: z.enum(['editor', 'viewer']),
                status: z.enum(['pending', 'accepted', 'revoked', 'expired']),
                expires_at: z.string(),
              })
              .strict(),
          ),
        })
        .strict(),
    );
  }
  requests() {
    return this.request('/requests', z.object({ items: z.array(serviceRequest) }).strict());
  }
  requestHelp(s: ServerSession, kind: AccountRequest['kind'], message: string) {
    return this.request('/requests', serviceRequest, s, { kind, message }, 'POST');
  }
  notices() {
    return this.request(
      '/notices',
      z
        .object({
          items: z.array(
            z
              .object({ id: uuid, action: z.string(), created_at: z.string(), read: z.boolean() })
              .strict(),
          ),
        })
        .strict(),
    );
  }
  markRead(s: ServerSession, id: string) {
    return this.request(
      '/notices/' + id + '/read',
      z.object({ read: z.literal(true) }).strict(),
      s,
      {},
      'POST',
    );
  }
  adminPlans() {
    return this.request('/admin/plans', z.object({ items: z.array(plan) }).strict());
  }
  createPlan(s: ServerSession, body: unknown) {
    return this.request('/admin/plans', plan, s, body, 'POST');
  }
  billingWorkspaces() {
    return this.request(
      '/admin/billing-workspaces',
      z.object({ items: z.array(z.object({ id: uuid, name: z.string() }).strict()) }).strict(),
    );
  }
  adminBilling(ws: string) {
    return this.request(
      '/admin/workspaces/' + ws + '/billing',
      z.object({ workspace_id: uuid, entitlement: allowance, invoices: z.array(invoice) }).strict(),
    );
  }
  createInvoice(s: ServerSession, ws: string, planId: string, days: number) {
    return this.request(
      '/admin/workspaces/' + ws + '/invoices',
      invoice,
      s,
      { plan_id: planId, days },
      'POST',
    );
  }
  evidence(s: ServerSession, ws: string, i: AccountInvoice, status: string, reference: string) {
    return this.request(
      '/admin/workspaces/' + ws + '/invoices/' + i.id + '/evidence',
      invoice,
      s,
      { expected_version: i.version, status, reference, verified_evidence: true },
      'POST',
    );
  }
  adminRequests() {
    return this.request(
      '/admin/requests',
      z.object({ items: z.array(serviceRequest.extend({ workspace_id: uuid }).strict()) }).strict(),
    );
  }
  respond(s: ServerSession, r: AccountRequest, response: string, status = 'answered') {
    return this.request(
      '/admin/requests/' + r.id + '/response',
      serviceRequest,
      s,
      { expected_version: r.version, status, response },
      'POST',
    );
  }
}
