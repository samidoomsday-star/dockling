"""Scoped manual billing and durable quota metadata; no online checkout is simulated."""

from alembic import op

revision = "0011_accounts_billing"
down_revision = "0010_owner_tools"
branch_labels = None
depends_on = None

DDL = """
CREATE TABLE web_account_commands(id uuid PRIMARY KEY,actor_id uuid NOT NULL REFERENCES web_users(id),key varchar(128) NOT NULL,name varchar(80) NOT NULL,workspace_id uuid NOT NULL REFERENCES web_workspaces(id),UNIQUE(actor_id,key));
GRANT SELECT,INSERT ON web_account_commands TO dockling_app;
CREATE TABLE web_commercial_plans(id uuid PRIMARY KEY,actor_id uuid NOT NULL REFERENCES web_users(id),data jsonb NOT NULL,at timestamptz NOT NULL DEFAULT now());
CREATE TABLE web_billing_invoices(id uuid PRIMARY KEY,workspace_id uuid NOT NULL REFERENCES web_workspaces(id),plan_id uuid NOT NULL REFERENCES web_commercial_plans(id),version bigint NOT NULL DEFAULT 1 CHECK(version>0),status varchar(16) NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','issued','paid','failed','refunded','cancelled')),valid_until timestamptz NOT NULL,at timestamptz NOT NULL DEFAULT now(),UNIQUE(workspace_id,id));
CREATE TABLE web_billing_evidence(id uuid PRIMARY KEY,workspace_id uuid NOT NULL,invoice_id uuid NOT NULL,actor_id uuid NOT NULL REFERENCES web_users(id),version bigint NOT NULL,status varchar(16) NOT NULL,reference varchar(120) NOT NULL UNIQUE,at timestamptz NOT NULL DEFAULT now(),FOREIGN KEY(workspace_id,invoice_id) REFERENCES web_billing_invoices(workspace_id,id),UNIQUE(invoice_id,version));
CREATE TABLE web_entitlements(workspace_id uuid PRIMARY KEY REFERENCES web_workspaces(id),invoice_id uuid NOT NULL,status varchar(16) NOT NULL CHECK(status IN ('active','refunded','cancelled')),limits jsonb NOT NULL,valid_until timestamptz NOT NULL,FOREIGN KEY(workspace_id,invoice_id) REFERENCES web_billing_invoices(workspace_id,id));
CREATE TABLE web_page_reservations(id uuid PRIMARY KEY,workspace_id uuid NOT NULL,job_id uuid NOT NULL,period varchar(7) NOT NULL,source_digest varchar(64) NOT NULL,pages bigint NOT NULL CHECK(pages>0 AND pages<=100),settled boolean NOT NULL DEFAULT false,FOREIGN KEY(workspace_id,job_id) REFERENCES web_jobs(workspace_id,id),UNIQUE(workspace_id,job_id,period,source_digest));
CREATE TABLE web_service_requests(id uuid PRIMARY KEY,workspace_id uuid NOT NULL REFERENCES web_workspaces(id),actor_id uuid NOT NULL REFERENCES web_users(id),kind varchar(20) NOT NULL CHECK(kind IN ('support','plan','privacy_export','privacy_remove')),message varchar(500) NOT NULL,status varchar(20) NOT NULL DEFAULT 'open' CHECK(status IN ('open','answered','closed')),version bigint NOT NULL DEFAULT 1,response varchar(500),at timestamptz NOT NULL DEFAULT now());
CREATE TABLE web_notice_receipts(id uuid PRIMARY KEY,event_id uuid NOT NULL REFERENCES web_events(id),actor_id uuid NOT NULL REFERENCES web_users(id),UNIQUE(event_id,actor_id));
GRANT SELECT,INSERT ON web_commercial_plans,web_billing_evidence TO dockling_app;
GRANT SELECT,INSERT,UPDATE ON web_billing_invoices,web_entitlements,web_page_reservations,web_service_requests TO dockling_app;
GRANT SELECT,INSERT ON web_notice_receipts TO dockling_app;
CREATE INDEX web_page_workspace ON web_page_reservations(workspace_id,period);
CREATE INDEX web_invoice_workspace ON web_billing_invoices(workspace_id);
CREATE INDEX web_request_workspace ON web_service_requests(workspace_id);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("Restore a matching backup; billing evidence and usage must never reset.")
