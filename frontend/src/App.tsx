import { lazy, Suspense } from 'react';
import FoundationApp from './FoundationApp';
import { Routes, Route, Link } from 'react-router-dom';
import { AppLayout, PublicLayout } from './components/layout';
import { Home, Demo, Pricing, Help, Access } from './pages/public';
import { Dashboard, Jobs, Upload } from './pages/workspace';
const JobPage = lazy(() => import('./pages/job').then((m) => ({ default: m.JobPage })));
const Connections = lazy(() =>
  import('./pages/connections').then((m) => ({ default: m.Connections })),
);
import { Categories, Settings } from './pages/settings';
const Admin = lazy(() => import('./pages/admin').then((m) => ({ default: m.Admin })));
export default function App() {
  if (import.meta.env.VITE_APP_MODE === 'api') return <FoundationApp />;
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Suspense
        fallback={
          <main id="main" className="app-main">
            Loading screen…
          </main>
        }
      >
        <Routes>
          <Route element={<PublicLayout />}>
            <Route index element={<Home />} />
            <Route path="demo" element={<Demo />} />
            <Route path="pricing" element={<Pricing />} />
            <Route path="help" element={<Help />} />
            <Route path="sign-in" element={<Access />} />
            <Route path="invite" element={<Access />} />
            <Route
              path="*"
              element={
                <div>
                  <h1>Page not found</h1>
                  <Link to="/">Go home</Link>
                </div>
              }
            />
          </Route>
          <Route element={<AppLayout />}>
            <Route path="app" element={<Dashboard />} />
            <Route path="app/jobs" element={<Jobs />} />
            <Route path="app/new" element={<Upload />} />
            <Route path="app/jobs/:id" element={<JobPage />} />
            <Route path="app/connections" element={<Connections />} />
            <Route path="app/categories" element={<Categories />} />
            <Route path="app/settings" element={<Settings />} />
            <Route path="admin" element={<Admin />} />
          </Route>
        </Routes>
      </Suspense>
    </>
  );
}
