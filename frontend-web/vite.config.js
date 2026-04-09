import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: true, // Fix for Gitpod/Cloud environments
    host: true,
    port: 5173,
    watch: {
      usePolling: true,
    },
  },
})
