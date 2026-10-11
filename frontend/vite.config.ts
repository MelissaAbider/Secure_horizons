/// <reference types="vitest/config" />
import fs from 'node:fs'
import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// Real fixtures belong to T0 (../fixtures). When they are not there yet,
// fall back to the stand-in copies in ./dev-fixtures (dev and tests only).
const realFixtures = path.resolve(__dirname, '../fixtures')
const fixturesDir = fs.existsSync(path.join(realFixtures, 'state.json'))
  ? realFixtures
  : path.resolve(__dirname, 'dev-fixtures')

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
