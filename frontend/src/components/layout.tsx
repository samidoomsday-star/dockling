import { useState } from 'react';
import { NavLink, Link, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Files,
  Plus,
  Plug,
  Tags,
  Settings,
  Shield,
  Menu,
  Waves,
  ArrowUpRight,
} from 'lucide-react';
import { useWorkspace, useSnapshot } from '../lib/workspace';
import { Button, Modal, Notice } from './ui';
export function Brand() {
  return (
    <Link className="brand" to="/">
      <span className="brand-icon">
        <Waves size={23} />
      </span>
      Dockling<span className="brand-dot">•</span>
    </Link>
  );
}
export function PreviewBanner() {
  const { api } = useWorkspace();
  return (
    <div className="preview-banner">
      {api.mode === 'demo' ? (
        <>Interactive preview · synthetic data · no real uploads, login or model calls</>
      ) : (
        <>API integration mode · requires a separately implemented backend</>
      )}
    </div>
  );
}
export function Notifications() {
  const { message, notify } = useWorkspace();
  return message ? (
    <div className="toast" role="status">
      <span>{message}</span>
      <button aria-label="Dismiss notification" onClick={() => notify('')}>
        ×
      </button>
    </div>
  ) : null;
}
export function PublicLayout() {
  return (
    <>
      <PreviewBanner />
      <header className="public-header">
        <Brand />
        <nav aria-label="Public">
          <NavLink to="/demo">Sample</NavLink>
          <NavLink to="/pricing">Pricing</NavLink>
          <NavLink to="/help">Help</NavLink>
          <Link className="button secondary" to="/sign-in">
            Open workspace <ArrowUpRight size={16} />
          </Link>
        </nav>
      </header>
      <main id="main" className="public-main">
        <Outlet />
      </main>
      <footer>
        <Brand />
        <span>Clearer statements. More confident decisions.</span>
        <Link to="/help">Privacy & limitations</Link>
      </footer>
      <Notifications />
    </>
  );
}
const items = [
  { to: '/app', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/app/jobs', label: 'Conversions', icon: Files },
  { to: '/app/new', label: 'New conversion', icon: Plus },
  { to: '/app/connections', label: 'AI connections', icon: Plug },
  { to: '/app/categories', label: 'Categories', icon: Tags },
  { to: '/app/settings', label: 'Settings', icon: Settings },
];
export function AppLayout() {
  const { role, setRole, api } = useWorkspace();
  const query = useSnapshot();
  const [menu, setMenu] = useState(false);
  const nav = (
    <nav aria-label="Workspace">
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={() => setMenu(false)}>
          <Icon size={19} />
          {label}
        </NavLink>
      ))}
      {role === 'admin' && (
        <NavLink to="/admin" onClick={() => setMenu(false)}>
          <Shield size={19} />
          Owner tools
        </NavLink>
      )}
    </nav>
  );
  return (
    <>
      <PreviewBanner />
      <div className="workspace">
        <aside className="sidebar">
          <Brand />
          {nav}
          <div className="sidebar-note">
            <span className="eyebrow">Your workspace</span>
            <strong>Sample Studio</strong>
            <p>Practice with fictional statements.</p>
            <Link to="/help">Need a hand? →</Link>
          </div>
        </aside>
        <div className="workspace-body">
          <header className="app-header">
            <button
              aria-label="Open navigation"
              className="icon-button mobile-menu"
              onClick={() => setMenu(true)}
            >
              <Menu size={22} />
            </button>
            <span className="workspace-name">
              Sample Studio <span className="muted">/ Preview</span>
            </span>
            <label className="role-picker">
              Preview role
              <select
                aria-label="Preview role"
                value={role}
                onChange={(e) => setRole(e.target.value as 'customer' | 'admin')}
                disabled={api.mode !== 'demo'}
              >
                <option value="customer">Customer</option>
                <option value="admin">Owner / admin</option>
              </select>
            </label>
          </header>
          <main id="main" className="app-main">
            {query.isPending ? (
              <Notice>Loading workspace…</Notice>
            ) : query.isError ? (
              <Notice tone="warning">
                {query.error.message} <Button onClick={() => void query.refetch()}>Retry</Button>
              </Notice>
            ) : (
              <Outlet />
            )}
          </main>
        </div>
      </div>
      <Modal
        open={menu}
        onOpenChange={setMenu}
        title="Workspace navigation"
        description="Choose where you want to go."
      >
        {nav}
      </Modal>
      <Notifications />
    </>
  );
}
