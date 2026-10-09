import { DemoApi } from './demo';
import { HttpApi } from './api';
import type { Api } from './types';
export function createApi(mode: string = 'demo'): Api {
  if (mode === 'demo') return new DemoApi();
  if (mode === 'api') return new HttpApi();
  throw new Error('Unsupported VITE_APP_MODE. Choose demo or api explicitly.');
}
