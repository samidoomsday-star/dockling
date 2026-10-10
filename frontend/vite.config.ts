import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'dockling-mode',
      generateBundle() {
        this.emitFile({
          type: 'asset',
          fileName: 'dockling-mode.json',
          source: JSON.stringify({ mode: loadEnv(mode, process.cwd()).VITE_APP_MODE ?? 'demo' }),
        });
      },
    },
  ],
  server: { host: '127.0.0.1' },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
}));
