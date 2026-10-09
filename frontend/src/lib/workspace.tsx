import { createContext, useContext, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createApi } from './mode';
import { errorMessage } from './validation';
import type { Api, Role } from './types';
const api = createApi(import.meta.env.VITE_APP_MODE ?? 'demo');
const Context = createContext<{
  api: Api;
  role: Role;
  setRole: (r: Role) => void;
  message: string;
  notify: (m: string) => void;
} | null>(null);
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<Role>('customer');
  const [message, notify] = useState('');
  return (
    <Context.Provider value={{ api, role, setRole, message, notify }}>{children}</Context.Provider>
  );
}
export function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw new Error('Workspace context missing');
  return value;
}
export function useSnapshot() {
  const { api } = useWorkspace();
  return useQuery({ queryKey: ['workspace'], queryFn: () => api.snapshot(), retry: false });
}
export function useAction() {
  const { notify } = useWorkspace();
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['workspace'] });
    },
    onError: (e) => notify(errorMessage(e)),
  });
  return {
    run: async (action: () => Promise<unknown>, message = 'Saved in this preview session.') => {
      try {
        await mutation.mutateAsync(action);
        notify(message);
        return true;
      } catch {
        return false;
      }
    },
    busy: mutation.isPending,
  };
}
