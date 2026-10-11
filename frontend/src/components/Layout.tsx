import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { isFixtureMode, isNoSnapshotYet } from '../api'
import { getOperator, setOperator, useDashboardData } from '../DataContext'
import { APP_NAME, APP_VERSION } from '../lib/labels'
import { canAnimate, scrollToId, startSmoothScroll, ScrollTrigger } from '../lib/motion'
import { useTheme } from '../lib/theme'
import { Banner } from './ui'

// The home page is one long scroll story: these jump to its chapters.
const SECTIONS = [
  { id: 'agent', label: 'Agent' },
  { id: 'attack', label: 'Attack' },
  { id: 'proof', label: 'Proof' },
]
// Secondary pages, kept for the jury but out of the way.
const MORE = [
  { to: '/setup', label: 'Set up your vault' },
  { to: '/alerts', label: 'Alerts & decisions' },
  { to: '/charts', label: 'Charts' },
  { to: '/incident', label: 'Incident & DORA' },
  { to: '/evidence', label: 'Evidence' },
  { to: '/dependencies', label: 'Third parties' },
  { to: '/metrics', label: 'Metrics' },
]

export function Layout({ children }: { children: ReactNode }) {
  const { health, state, decisions } = useDashboardData()
  const [operator, setOp] = useState(getOperator)
  const [theme, toggleTheme] = useTheme()
  const nav = useNavigate()
  const loc = useLocation()
  const home = loc.pathname === '/'
  const pending = (Array.isArray(decisions.data) ? decisions.data : []).reduce((n, d) => n + d.actions.filter((a) => a.status === 'pending_approval').length, 0)
  const h = health.data
  const block = state.data?.block_number ?? h?.block_number
  const waiting = isNoSnapshotYet(state.error)
  const unreachable = !!state.error && !waiting
  const stale = !isFixtureMode() && state.data && Date.now() - Date.parse(state.data.updated_at) > 15000

  useEffect(() => startSmoothScroll(), [])
  useEffect(() => { if (!canAnimate()) return; window.scrollTo(0, 0); const t = setTimeout(() => ScrollTrigger.refresh(), 120); return () => clearTimeout(t) }, [loc.pathname])

  function go(id: string) {
    if (!home) { nav('/'); setTimeout(() => scrollToId(id), 300) } else scrollToId(id)
  }

  const banners = (
    <div className="space-y-2">
      {isFixtureMode() && <Banner tone="yellow" testId="fixture-banner">FIXTURE MODE: data from fixtures/, no backend</Banner>}
      {waiting && <Banner tone="gray">Waiting for first block: the monitoring engine has not read the chain yet</Banner>}
      {unreachable && <Banner tone="red">Backend unreachable: showing last data from block {state.data?.block_number ?? '—'}</Banner>}
      {stale && !unreachable && <Banner tone="amber">Data is stale: last snapshot is more than 15 s old</Banner>}
    </div>
  )

  return (
    <div className={`min-h-screen font-sans text-fog-100 ${home ? '' : 'page-wash'}`}>
      {/* Floating glass pill: light on the light theme, night on the dark theme */}
      <header className={`${home ? 'fixed' : 'sticky'} inset-x-0 top-3 z-40 px-3 sm:px-6`}>
        <div className="mx-auto flex max-w-[1240px] items-center gap-3 rounded-full border border-ink-700 bg-ink-900/90 py-2 pl-5 pr-2 text-fog-100 shadow-[0_10px_40px_-14px_rgba(21,27,46,.35)] backdrop-blur-md sm:gap-4">
          <NavLink to="/" className="flex shrink-0 items-center gap-2">
            <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden><path d="M12 2 4 5v6c0 5 3.4 9.3 8 11 4.6-1.7 8-6 8-11V5l-8-3Z" fill="#4F7BFF" /><path d="m8.5 12 2.5 2.5 4.5-5" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" /></svg>
            <span className="font-display text-[17px] font-bold tracking-tight">{APP_NAME}</span>
            <span data-testid="app-version" className="rounded-full bg-ink-800 px-1.5 font-mono text-[10px] text-fog-400">{APP_VERSION}</span>
          </NavLink>
          <nav className="mx-auto hidden items-center gap-1 md:flex">
            {SECTIONS.map((s) => (
              <button key={s.id} onClick={() => go(s.id)} className="rounded-full px-4 py-2 text-[14px] text-fog-300 transition hover:bg-ink-800 hover:text-fog-100">{s.label}</button>
            ))}
            <NavLink to="/setup" className={({ isActive }) => `rounded-full px-4 py-2 text-[14px] transition hover:bg-ink-800 ${isActive ? 'bg-ink-800 text-fog-100' : 'text-fog-300'}`}>Set up</NavLink>
            <NavLink to="/alerts" className={({ isActive }) => `rounded-full px-4 py-2 text-[14px] transition hover:bg-ink-800 ${isActive ? 'bg-ink-800 text-fog-100' : 'text-fog-300'}`}>
              Alerts{pending > 0 && <span data-testid="pending-badge" className="ml-1.5 rounded-full bg-rose-glow px-1.5 font-mono text-[11px] font-bold text-white">{pending}</span>}
            </NavLink>
          </nav>
          <span className="ml-auto hidden items-center gap-2 font-mono text-[11px] uppercase tracking-[0.14em] text-fog-400 lg:flex md:ml-0">
            <span className={`h-1.5 w-1.5 rounded-full ${h?.rpc_ok ? 'bg-green-400' : 'bg-red-500'}`} />
            {(state.data?.network ?? h?.network ?? '—')} · {block ?? '—'}
          </span>
          <button type="button" onClick={toggleTheme} data-testid="theme-toggle"
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'} title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
            className="ml-auto grid h-10 w-10 shrink-0 place-items-center rounded-full border border-ink-700 text-fog-300 transition hover:bg-ink-800 hover:text-fog-100 md:ml-0">
            {theme === 'dark'
              ? <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" aria-hidden fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="4.2" /><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" /></svg>
              : <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" aria-hidden fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a8.5 8.5 0 1 0 10.7 10.7Z" /></svg>}
          </button>
          <NavLink to="/demo" className="shrink-0 rounded-full bg-fog-100 px-5 py-2.5 text-[14px] font-semibold text-ink-950 transition hover:opacity-85">
            Run the attack
          </NavLink>
        </div>
      </header>

      {home ? (
        <main>
          <div className="absolute inset-x-0 top-24 z-30 mx-auto max-w-[1240px] px-4 sm:px-6">{banners}</div>
          {children}
        </main>
      ) : (
        <main className="mx-auto max-w-[1320px] px-4 pb-10 pt-6 sm:px-6">
          {banners}
          <div className="mt-4 space-y-5">{children}</div>
        </main>
      )}

      <footer className="relative z-10 border-t border-ink-700 bg-white">
        <div className="mx-auto flex max-w-[1240px] flex-wrap items-center gap-x-6 gap-y-3 px-4 py-6 text-sm sm:px-6">
          <span className="font-display font-bold tracking-tight">{APP_NAME}</span>
          {MORE.map((m) => <NavLink key={m.to} to={m.to} className="text-fog-400 hover:text-fog-100">{m.label}</NavLink>)}
          <label className="ml-auto flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.14em] text-fog-400">
            Operator
            <input id="operator" value={operator} onChange={(e) => { setOp(e.target.value); setOperator(e.target.value) }}
              className="w-40 rounded-full border border-ink-700 bg-white px-3 py-1.5 font-mono text-[12px] normal-case tracking-normal text-fog-100 outline-none focus:border-signal-violet" />
          </label>
        </div>
      </footer>
    </div>
  )
}
