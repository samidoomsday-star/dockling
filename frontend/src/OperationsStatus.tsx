import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { FoundationApi, FoundationError, type ServerSession } from './lib/foundation';
const count = z.number().int().nonnegative();
const schema = z
  .object({
    status: z.enum(['healthy', 'attention']),
    checked_at: z.string(),
    queued: count,
    running: count,
    oldest_queue_seconds: count,
    recent_failures: count,
    pending_removals: count,
    failed_removals: count,
    uncertain_ai_attempts: count,
    pending_ai_cleanup: count,
    backup_created_at: z.string().nullable(),
    backup_expires_at: z.string().nullable(),
    restore_verified_at: z.string().nullable(),
    alerts: z.array(
      z
        .object({ code: z.string(), level: z.enum(['warning', 'critical']), message: z.string() })
        .strict(),
    ),
  })
  .strict();
const api = new FoundationApi();
const date = (value: string | null) => (value ? new Date(value).toLocaleString() : 'Not verified');

export default function OperationsStatus({ session }: { session: ServerSession }) {
  const q = useQuery({
    queryKey: ['foundation', 'admin', 'operations'],
    queryFn: () => api.request('/admin/operations', schema),
    enabled: session.platform_admin,
    retry: false,
    refetchInterval: 15000,
  });
  if (!session.platform_admin) return null;
  return (
    <section className="card section lavender">
      <span className="eyebrow">Keep the service dependable</span>
      <h2>Operations and recovery</h2>
      <p>
        These signals contain counts and fixed alerts. They give no access to customer documents.
      </p>
      {q.isError && (
        <p role="alert">
          {q.error instanceof FoundationError
            ? q.error.message
            : 'Operating status is unavailable.'}
        </p>
      )}
      {!q.isError && q.data && (
        <>
          <p role="status">
            {q.data.status === 'healthy' ? 'No current alerts' : 'Attention needed'}
          </p>
          <div className="account-grid">
            <article>
              <h3>Conversion queue</h3>
              <p>
                {q.data.queued} waiting · {q.data.running} running
              </p>
              <p>Oldest wait: {q.data.oldest_queue_seconds} seconds</p>
              <p>{q.data.recent_failures} recent failures</p>
            </article>
            <article>
              <h3>Live removal</h3>
              <p>
                {q.data.pending_removals} pending · {q.data.failed_removals} incomplete
              </p>
              <p>{q.data.pending_ai_cleanup} AI cleanup receipts pending</p>
            </article>
            <article>
              <h3>Encrypted backup</h3>
              <p>Created: {date(q.data.backup_created_at)}</p>
              <p>Expires: {date(q.data.backup_expires_at)}</p>
              <p>Restore drill: {date(q.data.restore_verified_at)}</p>
            </article>
          </div>
          {q.data.alerts.map((a) => (
            <div className="notice" key={a.code}>
              <strong>{a.level === 'critical' ? 'Action required' : 'Review'}:</strong> {a.message}
            </div>
          ))}
          <p className="fine">
            A successful local restore is engineering evidence. Hosted recovery promises require a
            drill on the chosen server. Never automatically retry an uncertain paid AI request.
          </p>
        </>
      )}
      {q.isPending && <p>Checking operating status…</p>}
      <button className="button secondary" onClick={() => void q.refetch()}>
        Refresh operating status
      </button>
    </section>
  );
}
