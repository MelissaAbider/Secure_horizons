/// <reference types="vitest/config" />
import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// Fixture mode (VITE_USE_FIXTURES=true) and tests read the shared API fixtures generated from backend/models.py.
const fixturesDir = path.resolve(__dirname, '../fixtures')

export default defineConfig(({ mode }) => {
  // Only EXPLORER_URL is read from the root .env: that file holds private keys.
  const rootEnv = loadEnv(mode, path.resolve(__dirname, '..'), '')
  return {
    plugins: [react()],
    base: process.env.VITE_BASE ?? '/',
    resolve: { alias: { '@fixtures': fixturesDir } },
    define: {
      __EXPLORER_URL__: JSON.stringify(rootEnv.EXPLORER_URL || 'https://testnet.snowtrace.io'),
    },
    server: {
      port: 5173,
      fs: { allow: ['..'] },
      // Lets you run the front with VITE_API_URL= (empty) and relative /api calls, like production.
      proxy: { '/api': 'http://localhost:8000' },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      globals: true,
    },
  }
})
