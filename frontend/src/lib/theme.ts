// Light by default; the visitor can switch to dark. Stored per browser (a viewer convenience only).
import { useSyncExternalStore } from 'react'

export type Theme = 'light' | 'dark'
const KEY = 'sh.theme'
const listeners = new Set<() => void>()

function read(): Theme {
  try { return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light' } catch { return 'light' }
}
let current: Theme = typeof window === 'undefined' ? 'light' : read()

function apply(t: Theme) {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', t === 'dark')
  document.documentElement.style.colorScheme = t
}

export function initTheme() { current = read(); apply(current) }

export function setTheme(t: Theme) {
  current = t
  try { localStorage.setItem(KEY, t) } catch { /* storage unavailable */ }
  apply(t)
  listeners.forEach((l) => l())
}

export function useTheme(): [Theme, () => void] {
  const t = useSyncExternalStore(
    (l) => { listeners.add(l); return () => { listeners.delete(l) } },
    () => current, () => 'light' as Theme,
  )
  return [t, () => setTheme(t === 'dark' ? 'light' : 'dark')]
}
