import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/tests/setup.js',
    include: ['src/tests/test_*.{jsx,js}'],
  },
  server: {
    port: 5173,
    // API_TARGET is set to http://backend:8000 in Docker, localhost:8000 locally
    proxy: {
      '/auth': { target: process.env.API_TARGET || 'http://localhost:8000' },
      '/workspaces': {
        target: process.env.API_TARGET || 'http://localhost:8000',
        bypass: (req) => {
          if (req.headers.accept?.includes('text/html')) return '/index.html'
        },
      },
      '/signal-types': { target: process.env.API_TARGET || 'http://localhost:8000' },
      '/schemas': {
        target: process.env.API_TARGET || 'http://localhost:8000',
        bypass: (req) => {
          if (req.headers.accept?.includes('text/html')) return '/index.html'
        },
      },
      '/observability': { target: process.env.API_TARGET || 'http://localhost:8000' },
    },
  },
})
