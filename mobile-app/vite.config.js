import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiUrl = env.VITE_API_URL || process.env.VITE_API_URL;
  const isRelease = mode === 'production' && !process.env.VITEST && !process.env.SKIP_RELEASE_GATE;

  if (isRelease) {
    if (!apiUrl) {
      throw new Error(
        '[SECURITY RELEASE BUILD FAIL] VITE_API_URL environment variable is missing. Set VITE_API_URL=https://api.altsan.com/api for production builds.'
      );
    }
    if (!apiUrl.startsWith('https://')) {
      throw new Error(
        `[SECURITY RELEASE BUILD FAIL] VITE_API_URL must be a secure HTTPS endpoint in production release builds. Got: ${apiUrl}`
      );
    }
  }

  return {
    plugins: [react()],
    server: {
      port: 5174,
      host: true,
    },
    build: {
      target: 'es2020',
      sourcemap: mode !== 'production',
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom'],
            capacitor: ['@capacitor/core', '@capacitor/camera', '@capacitor/geolocation', '@capacitor/filesystem', '@capacitor/app', '@capacitor/network'],
          },
        },
      },
    },
    test: {
      globals: true,
      environment: 'jsdom',
    },
  };
});
