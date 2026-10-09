import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { WorkspaceProvider } from './lib/workspace';
import './styles.css';
const client = new QueryClient({
  defaultOptions: { queries: { staleTime: 15000, refetchOnWindowFocus: false } },
});
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <WorkspaceProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </WorkspaceProvider>
    </QueryClientProvider>
  </StrictMode>,
);
