import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(() => {
  // VITE_API_TARGET lets docker-compose dev override the proxy target.
  // Local dev (outside Docker) leaves this unset and hits localhost.
  const target = process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8000'
  return {
    plugins: [react()],
    server: {
      watch: {
        // Polling is required inside Docker bind-mounts where inotify events
        // are not reliably delivered to the container.
        usePolling: true,
      },
      proxy: {
        // ws: true so the optimization WebSocket (/api/optimization/ws) upgrade
        // is proxied through to the API in dev.
        '/api': { target, ws: true },
        // /health is a root-level route on the API (not under /api). Without
        // this, the dev server serves index.html for /health and the health
        // poll's res.json() fails, hiding the "slots free" indicator.
        '/health': { target },
      },
    },
  }
})
