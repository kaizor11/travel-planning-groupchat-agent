// Vite config: React plugin + dev proxy so /trips and /api requests hit the FastAPI backend on port 8000.
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Only /api is forwarded to FastAPI.
      // /trips/:tripId is a React Router client-side route — Vite serves index.html for it.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
