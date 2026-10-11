import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { resetFixtureDb } from '../fixtureDb'

class RO { observe() {} unobserve() {} disconnect() {} }
;(globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO

afterEach(() => {
  cleanup()
  try { localStorage.clear() } catch { /* ignore */ }
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.useRealTimers()
  vi.restoreAllMocks()
  resetFixtureDb()
})

// jsdom has no matchMedia; GSAP ScrollTrigger needs it at import time. Animations stay off in tests (see lib/motion.ts).
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  window.matchMedia = (query: string) => ({
    matches: false, media: query, onchange: null,
    addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false,
  }) as MediaQueryList
}
