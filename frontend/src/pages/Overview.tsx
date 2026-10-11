import { useLayoutEffect, useRef, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Area, AreaChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { api, isNoSnapshotYet } from '../api'
import { Counter, Magnetic, Tilt } from '../components/motionBits'
import { ShieldField } from '../components/ShieldField'
import { SeverityBadge, ToneBar, Waiting } from '../components/ui'
import { useDashboardData } from '../DataContext'
import { usePolling } from '../hooks/usePolling'
import { AGENT_MOVES, AGENT_RULES, type Verdict } from '../lib/agentDemo'
import { formatBpsPct, formatUsd, shortHash, withdrawableTone } from '../lib/format'
import { ruleLabel } from '../lib/labels'
import { canAnimate, gsap, scrollToId } from '../lib/motion'
import { useTheme } from '../lib/theme'
import type { Alert, Decision, SeriesPoint, StateResponse } from '../types'

const SHORT_DEP: Record<string, string> = { 'lend-eth': 'Ethereum market', 'lend-avax': 'Avalanche market' }
const usd = (n: number) => formatUsd(Math.round(n))

export function Overview() {
  const { state, alerts, decisions } = useDashboardData()
  const series = usePolling(() => api.series('lend-eth', 'WETH', 300), 2000)
  const s = state.data
  if (!s) {
    if (isNoSnapshotYet(state.error)) return <div className="mx-auto max-w-[1240px] px-4 pt-32"><Waiting /></div>
    if (state.error) return <p className="px-6 pt-32 text-red-600">Could not load state: {state.error.message}</p>
    return <p className="px-6 pt-32 text-fog-400">Loading…</p>
  }
  return (
    <OverviewView s={s}
      alerts={Array.isArray(alerts.data) ? alerts.data : []}
      decisions={Array.isArray(decisions.data) ? decisions.data : []}
      series={Array.isArray(series.data) ? series.data : []} />
  )
}

function Eyebrow({ children, dark = false }: { children: ReactNode; dark?: boolean }) {
  return <div className={`font-mono text-[12px] uppercase tracking-[0.28em] ${dark ? 'text-white/50' : 'text-fog-400'}`}>{children}</div>
}

const VERDICT: Record<Verdict, { label: string; ring: string; text: string }> = {
  executed: { label: 'Executed', ring: 'border-green-500', text: 'text-green-600' },
  signature: { label: 'Signature', ring: 'border-amber-500', text: 'text-amber-600' },
  blocked: { label: 'Blocked', ring: 'border-rose-glow', text: 'text-rose-glow' },
}

const ATTACK_STEPS = [
  { t: 'Fake rsETH is minted', d: 'out of nothing, on the bridge' },
  { t: 'Backing collapses', d: 'the guard reads it in the same block' },
  { t: 'The agent is baited', d: '"Incident solved, deposit at 14%"' },
  { t: 'The guard says no', d: 'not on the sealed list' },
  { t: 'Freeze and pull back', d: 'deposits paused, money back in the vault' },
  { t: 'Proof on-chain', d: 'decision fingerprint anchored' },
]

export function OverviewView({ s, alerts = [], decisions = [], series = [] }: {
  s: StateResponse; alerts?: Alert[]; decisions?: Decision[]; series?: SeriesPoint[]
}) {
  const root = useRef<HTMLDivElement>(null)
  const [theme] = useTheme()
  const backed = s.tokens.find((t) => t.backing_ratio_bps !== null)
  const bps = backed?.backing_ratio_bps ?? null
  const positions = s.positions.filter((p) => p.supplied !== '0')
  const t = s.totals
  const sortedAlerts = [...alerts].sort((a, b) => a.block_number - b.block_number)
  const firstCritical = sortedAlerts.find((a) => a.severity === 'critical')
  const anchored = decisions.find((d) => d.anchor_tx)
  const chart = series.map((p) => ({ b: p.block_number, backing: p.backing_ratio_bps === null ? null : p.backing_ratio_bps / 100 }))
  const blocked = AGENT_MOVES.filter((m) => m.verdict === 'blocked').length
  const manifesto = 'A manipulated agent changes what it wants.'.split(' ')
  const manifesto2 = 'Not what the vault accepts.'.split(' ')

  useLayoutEffect(() => {
    if (!canAnimate() || !root.current) return
    const q = gsap.utils.selector(root)
    const ctx = gsap.context(() => {
      // ── Hero intro
      gsap.from(q('.h-line > span'), { yPercent: 115, duration: 1.2, ease: 'expo.out', stagger: 0.09, delay: 0.1 })
      gsap.from(q('.h-fade'), { opacity: 0, y: 24, duration: 1, ease: 'power3.out', stagger: 0.08, delay: 0.5 })
      const money = q('.h-money')[0] as HTMLElement | undefined
      if (money) {
        const o = { n: 0 }, end = t.value_usd ?? 0
        gsap.to(o, { n: end, duration: 2.2, ease: 'power4.out', delay: 0.2, onUpdate: () => { money.textContent = usd(o.n) }, onComplete: () => { money.textContent = usd(end) } })
      }
      // hero leaves: content sinks, shield drifts
      gsap.to(q('.hero-content'), { yPercent: 18, opacity: 0, ease: 'none', scrollTrigger: { trigger: q('.hero')[0], start: 'top top', end: 'bottom top', scrub: true } })
      gsap.to(q('.hero-canvas'), { yPercent: 25, scale: 1.08, ease: 'none', scrollTrigger: { trigger: q('.hero')[0], start: 'top top', end: 'bottom top', scrub: true } })

      // ── Manifesto: words light up one by one
      const mtl = gsap.timeline({ scrollTrigger: { trigger: q('.manifesto')[0], start: 'top top', end: '+=160%', scrub: 0.6, pin: true } })
      mtl.from(q('.m-word'), { opacity: 0.12, stagger: 0.12, ease: 'none', duration: 0.5 })

      const mm = gsap.matchMedia()
      mm.add('(min-width: 1024px)', () => {
        // ── Agent: horizontal track, stamps slam in as each card reaches the middle
        const track = q('.a-track')[0] as HTMLElement
        const dist = () => track.scrollWidth - window.innerWidth + 48
        const h = gsap.to(track, { x: () => -dist(), ease: 'none', scrollTrigger: { trigger: q('.agent-pin')[0], start: 'top top', end: () => `+=${dist()}`, scrub: 0.8, pin: true, invalidateOnRefresh: true } })
        gsap.to(q('.a-progress'), { scaleX: 1, ease: 'none', scrollTrigger: { trigger: q('.agent-pin')[0], start: 'top top', end: () => `+=${dist()}`, scrub: true } })
        q('.a-card').forEach((card: Element) => {
          const stamp = card.querySelector('.stamp'), checks = card.querySelectorAll('.check')
          const tl = gsap.timeline({ scrollTrigger: { trigger: card, containerAnimation: h, start: 'left 70%', toggleActions: 'play none none reverse' } })
          if (checks.length) tl.from(checks, { opacity: 0, x: -14, stagger: 0.12, duration: 0.35 })
          if (stamp) tl.from(stamp, { scale: 2.6, opacity: 0, rotate: -24, duration: 0.45, ease: 'back.out(2.2)' })
        })

        // ── Attack: one pinned scene, scrubbed by the scroll
        const steps = q('.x-step')
        const read = q('.x-read')[0] as HTMLElement
        const blk = q('.x-block')[0] as HTMLElement
        const startB = 10000, endB = bps ?? 1935
        const b0 = (firstCritical?.block_number ?? s.block_number) - 1
        const o = { b: startB, k: 0 }
        const paint = () => { read.textContent = formatBpsPct(o.b); blk.textContent = String(b0 + Math.round(o.k)) }
        gsap.set(steps, { opacity: 0.25 })
        gsap.set(q('.layer'), { z: (i: number) => i * 130 })
        paint()
        const tl = gsap.timeline({ defaults: { ease: 'power2.inOut' }, scrollTrigger: { trigger: q('.attack')[0], start: 'top top', end: '+=420%', scrub: 0.8, pin: true } })
        tl.from(q('.layer'), { z: (i: number) => i * 16, duration: 1 })
          // 1 mint
          .to(steps[0], { opacity: 1, duration: 0.2 })
          .from(q('.particle'), { z: 340, opacity: 0, stagger: 0.06, duration: 0.8, ease: 'power2.in' }, '<')
          // 2 collapse
          .to(steps[1], { opacity: 1, duration: 0.2 })
          .to(o, { b: endB, k: 1, duration: 1.1, onUpdate: paint }, '<')
          .from(q('.rose-grid'), { opacity: 0, duration: 1.1 }, '<')
          .from(q('.x-readwrap'), { color: '#FFFFFF', duration: 1.1 }, '<')
          // 3 bait
          .to(steps[2], { opacity: 1, duration: 0.2 })
          .from(q('.bait'), { opacity: 0, y: 30, scale: 0.9, duration: 0.6, ease: 'back.out(1.6)' }, '<')
          // 4 guard
          .to(steps[3], { opacity: 1, duration: 0.2 })
          .from(q('.guard-red'), { opacity: 0, duration: 0.4 }, '<')
          .fromTo(q('.scan'), { yPercent: -10 }, { yPercent: 900, duration: 0.8, ease: 'none' }, '<')
          .from(q('.bait-strike'), { scaleX: 0, duration: 0.4 }, '<0.3')
          .from(q('.x-stamp'), { scale: 2.4, opacity: 0, rotate: -20, duration: 0.5, ease: 'back.out(2)' }, '<')
          // 5 freeze + pull back
          .to(steps[4], { opacity: 1, duration: 0.2 })
          .from(q('.coin'), { z: -260, opacity: 0, stagger: 0.08, duration: 0.9 }, '<')
          .from(q('.lid'), { opacity: 0, z: 140, duration: 0.7, ease: 'power3.out' }, '<0.4')
          .from(q('.paused-chip'), { opacity: 0, y: 12, duration: 0.4 }, '<0.3')
          // 6 proof
          .to(steps[5], { opacity: 1, duration: 0.2 })
          .from(q('.proof-chip'), { opacity: 0, y: 12, duration: 0.5 }, '<')
          .to({}, { duration: 0.6 })
        tl.fromTo(q('.x-fill'), { scaleY: 0 }, { scaleY: 1, duration: tl.duration(), ease: 'none' }, 0)
      })

      // ── Proof: cards rise in
      q('.rise').forEach((el: Element) => gsap.from(el, { y: 70, opacity: 0, duration: 1, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 90%' } }))
      // ── Outro: giant words slide with the scroll
      gsap.fromTo(q('.slide-l'), { xPercent: 0 }, { xPercent: -30, ease: 'none', scrollTrigger: { trigger: q('.outro')[0], start: 'top bottom', end: 'bottom top', scrub: true } })
      gsap.fromTo(q('.slide-r'), { xPercent: -30 }, { xPercent: 0, ease: 'none', scrollTrigger: { trigger: q('.outro')[0], start: 'top bottom', end: 'bottom top', scrub: true } })
    }, root)
    return () => ctx.revert()
    // Animations are built once; data changes only update text.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function spot(e: React.MouseEvent<HTMLElement>) {
    const r = e.currentTarget.getBoundingClientRect()
    e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`)
    e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`)
  }

  return (
    <div ref={root} className="relative isolate overflow-x-clip">
      <div aria-hidden className="backdrop fixed inset-0 -z-10 bg-ink-950" />

      {/* ───────── HERO: the money first ───────── */}
      <section onMouseMove={spot} className="hero spot relative min-h-[100svh] overflow-hidden text-fog-100">
        <ShieldField dark={theme === 'dark'} className="hero-canvas absolute inset-0 h-full w-full" />
        <div aria-hidden className="grain pointer-events-none absolute inset-0" />
        <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-ink-950 to-transparent" />
        <div className="hero-content relative mx-auto flex min-h-[100svh] max-w-[1240px] flex-col justify-center px-5 pb-12 pt-32 sm:px-8 lg:pb-32">
          <div className="h-fade flex flex-wrap items-center gap-3 font-mono text-[12px] uppercase tracking-[0.22em] text-fog-400">
            <span className="flex items-center gap-2 rounded-full border border-ink-700 bg-ink-900/70 px-3 py-1.5"><span className="pulse-dot h-1.5 w-1.5 rounded-full bg-rose-glow" />{s.network} · block {s.block_number}</span>
            <span data-testid="risk-badge" className={`rounded-full px-3 py-1.5 font-bold text-white ${{ info: 'bg-slate-500', warning: 'bg-amber-500', high: 'bg-orange-600', critical: 'bg-rose-glow' }[s.risk_level]}`}>{s.risk_level.toUpperCase()}</span>
          </div>
          <div className="h-line mt-8 overflow-hidden pb-2">
            <span className="h-money hero-money block font-display text-[clamp(3.6rem,11vw,10.5rem)] font-bold leading-[0.9] tracking-[-0.055em] tabular-nums">{usd(t.value_usd ?? 0)}</span>
          </div>
          <h1 className="mt-4 font-display text-[clamp(1.9rem,4vw,3.6rem)] font-semibold leading-[1.02] tracking-[-0.04em]">
            <span className="h-line block overflow-hidden"><span className="block">Run by an AI agent.</span></span>
            <span className="h-line block overflow-hidden pb-1"><span className="block font-serif font-normal italic tracking-normal text-signal-violet dark:text-[#9DB6FF]">It never holds the keys.</span></span>
          </h1>
          <div className="h-fade mt-10 flex flex-wrap items-center gap-3">
            <Link to="/demo" className="rounded-full bg-fog-100 px-7 py-3.5 text-[15px] font-semibold text-ink-950 transition hover:opacity-85">Run the attack</Link>
            <button onClick={() => scrollToId('agent')} className="rounded-full border border-ink-600 bg-ink-900/60 px-7 py-3.5 text-[15px] font-medium text-fog-100 transition hover:border-fog-400">Meet the agent ↓</button>
          </div>
          <div className="h-fade mt-12 flex flex-wrap gap-3 lg:absolute lg:bottom-10 lg:left-8 lg:right-8 lg:mt-0">
            {[
              { k: 'Agent asks', v: String(AGENT_MOVES.length) },
              { k: 'Blocked', v: String(blocked), c: 'text-rose-glow dark:text-[#FF8FA8]' },
              { k: `${backed?.symbol ?? 'rsETH'} backing`, v: bps !== null ? formatBpsPct(bps) : '—', c: 'text-rose-glow dark:text-[#FF8FA8]' },
              { k: 'At risk', v: usd(t.at_risk_usd ?? 0) },
            ].map((x) => (
              <div key={x.k} className="rounded-2xl border border-ink-700 bg-ink-900/70 px-4 py-3 backdrop-blur-sm">
                <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-fog-400">{x.k}</div>
                <div className={`mt-1 font-display text-xl font-semibold tabular-nums ${x.c ?? 'text-fog-100'}`}>{x.v}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ───────── MANIFESTO: night turns to day ───────── */}
      <section className="manifesto relative grid h-[100svh] place-items-center px-5 text-fog-100 sm:px-8">
        <p className="mx-auto max-w-[1100px] text-center font-display text-[clamp(2.2rem,5.6vw,5.2rem)] font-semibold leading-[1.02] tracking-[-0.045em]">
          {manifesto.map((w, i) => <span key={i} className="m-word">{w} </span>)}
          <br />
          {manifesto2.map((w, i) => <span key={i} className="m-word font-serif font-normal italic tracking-normal text-signal-violet">{w} </span>)}
        </p>
      </section>

      {/* ───────── 01 AGENT: horizontal track ───────── */}
      <section id="agent" className="relative bg-ink-950">
        <div className="agent-pin relative flex min-h-[100svh] flex-col justify-center overflow-hidden py-24">
          <div className="mx-auto w-full max-w-[1240px] px-5 sm:px-8">
            <Eyebrow>01 — The agent</Eyebrow>
            <h2 className="mt-4 font-display text-[clamp(2.4rem,5.4vw,4.8rem)] font-bold leading-[0.95] tracking-[-0.05em]">
              It proposes. <span className="font-serif font-normal italic tracking-normal text-signal-violet">The vault decides.</span>
            </h2>
          </div>
          <div className="mt-12 overflow-x-auto pb-4 lg:overflow-visible [scrollbar-width:none]">
            <div className="a-track flex w-max gap-6 px-5 sm:px-8 lg:pl-[max(2rem,calc((100vw-1240px)/2+2rem))]">
              {/* sealed rules */}
              <div className="a-card relative flex w-[min(86vw,400px)] shrink-0 flex-col overflow-hidden rounded-[28px] bg-[#0B0F1C] p-8 text-white">
                <div aria-hidden className="spin-slow absolute -right-16 -top-16 h-56 w-56 rounded-full border border-dashed border-white/15" />
                <div className="flex items-center justify-between">
                  <Eyebrow dark>Sealed rules</Eyebrow>
                  <svg viewBox="0 0 24 24" className="h-7 w-7" aria-hidden><rect x="5" y="10" width="14" height="10" rx="2.5" fill="#4F7BFF" /><path d="M8 10V7.5a4 4 0 0 1 8 0V10" stroke="#9DB6FF" strokeWidth="2" fill="none" /></svg>
                </div>
                <dl className="mt-8 flex-1 space-y-4">
                  {AGENT_RULES.map((r) => (
                    <div key={r.k} className="check flex items-baseline justify-between gap-4 border-b border-white/10 pb-3">
                      <dt className="text-white/55">{r.k}</dt>
                      <dd className="font-mono text-[14px] text-white">{r.v}</dd>
                    </div>
                  ))}
                </dl>
                <div className="mt-6 font-mono text-[11px] uppercase tracking-[0.2em] text-[#9DB6FF]">3 of 5 signers · merkle root on-chain</div>
              </div>
              {/* agent asks */}
              {AGENT_MOVES.map((m, i) => (
                <div key={m.ask} className={`a-card relative flex w-[min(86vw,400px)] shrink-0 flex-col rounded-[28px] border bg-white p-8 shadow-soft ${m.verdict === 'blocked' ? 'border-rose-200' : 'border-ink-700'}`}>
                  <div className="flex items-center justify-between font-mono text-[12px] uppercase tracking-[0.2em] text-fog-400">
                    <span>Ask {String(i + 1).padStart(2, '0')}</span><span>{m.time}</span>
                  </div>
                  <div className="mt-6 flex items-start gap-3">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-signal-cyan to-signal-violet font-mono text-[11px] font-bold text-white">AI</span>
                    <div className="rounded-2xl rounded-tl-md bg-ink-950 px-4 py-3 text-[17px] font-medium leading-snug">{m.ask}</div>
                  </div>
                  <div className="check mt-6 flex items-center gap-2 font-mono text-[13px] text-fog-400">
                    <span className={m.verdict === 'executed' ? 'text-green-600' : m.verdict === 'signature' ? 'text-amber-600' : 'text-rose-glow'}>{m.verdict === 'executed' ? '✓' : m.verdict === 'signature' ? '!' : '✕'}</span>{m.check}
                  </div>
                  <div className="mt-auto flex items-end justify-between pt-10">
                    <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-fog-500">sample</span>
                    <span className={`stamp inline-block -rotate-6 rounded-xl border-[3px] px-4 py-1.5 font-display text-2xl font-extrabold uppercase tracking-tight ${VERDICT[m.verdict].ring} ${VERDICT[m.verdict].text}`}>{VERDICT[m.verdict].label}</span>
                  </div>
                </div>
              ))}
              {/* score */}
              <div className="a-card flex w-[min(86vw,400px)] shrink-0 flex-col justify-between rounded-[28px] bg-gradient-to-br from-navy-soft to-navy p-8 text-white">
                <Eyebrow dark>Score</Eyebrow>
                <div>
                  <div className="font-display text-[7rem] font-bold leading-none tracking-[-0.06em]">{blocked}<span className="text-white/40">/{AGENT_MOVES.length}</span></div>
                  <p className="mt-3 text-lg text-white/75">bad asks stopped. Zero keys given.</p>
                </div>
              </div>
            </div>
          </div>
          <div className="mx-auto mt-10 hidden h-[3px] w-full max-w-[1240px] overflow-hidden rounded-full bg-ink-700 px-0 lg:block">
            <div className="a-progress h-full origin-left scale-x-0 bg-signal-violet" />
          </div>
        </div>
      </section>

      {/* ───────── 02 ATTACK: pinned, scrubbed scene ───────── */}
      <section id="attack" className="attack relative min-h-[100svh] overflow-hidden rounded-t-[2.5rem] bg-[#05070B] text-white">
        <div aria-hidden className="grain pointer-events-none absolute inset-0" />
        <div className="relative mx-auto grid min-h-[100svh] max-w-[1240px] items-center gap-10 px-5 py-24 sm:px-8 lg:grid-cols-[0.9fr_1.1fr] lg:py-0">
          <div>
            <Eyebrow dark>02 — The attack</Eyebrow>
            <h2 className="mt-4 font-display text-[clamp(2.4rem,5vw,4.4rem)] font-bold leading-[0.95] tracking-[-0.05em]">
              Caught in <span className="font-serif font-normal italic tracking-normal text-[#FF8FA8]">one block.</span>
            </h2>
            <div className="mt-8 flex items-end gap-6">
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/45">{backed?.symbol ?? 'rsETH'} backing</div>
                <div className="x-readwrap font-display text-[clamp(3.4rem,6vw,5.4rem)] font-bold leading-none tracking-[-0.05em] text-[#FF6F8F] tabular-nums"><span className="x-read">{bps !== null ? formatBpsPct(bps) : '—'}</span></div>
              </div>
              <div className="pb-2 font-mono text-[12px] text-white/45">block <span className="x-block text-white">{firstCritical?.block_number ?? s.block_number}</span></div>
            </div>
            <div className="relative mt-8 pl-6">
              <div aria-hidden className="absolute bottom-2 left-0 top-2 w-px bg-white/10" />
              <div aria-hidden className="x-fill absolute bottom-2 left-0 top-2 w-px origin-top bg-[#FF6F8F]" />
              <ol className="space-y-3.5">
                {ATTACK_STEPS.map((st, i) => (
                  <li key={st.t} className="x-step">
                    <div className="flex items-baseline gap-3">
                      <span className="font-mono text-[11px] text-white/40">{String(i + 1).padStart(2, '0')}</span>
                      <span className="text-[17px] font-semibold">{st.t}</span>
                    </div>
                    <div className="pl-8 text-[14px] text-white/50">{st.d}</div>
                  </li>
                ))}
              </ol>
            </div>
          </div>

          {/* isometric scene */}
          <div className="relative hidden h-[640px] lg:block">
            <div className="absolute inset-0 grid place-items-center [perspective:1800px]">
              <div className="scene relative h-[330px] w-[330px]">
                {/* markets */}
                <div className="layer absolute inset-0 rounded-[30px] border border-white/15 bg-white/[0.04]" style={{ transform: 'translateZ(0px)' }}>
                  <div className="dotgrid absolute inset-5 rounded-2xl opacity-60" />
                  <div className="rose-grid dotgrid-rose absolute inset-5 rounded-2xl" />
                  {Array.from({ length: 10 }, (_, i) => (
                    <span key={i} className="particle absolute h-4 w-4 rounded-[4px] bg-[#FF6F8F] shadow-[0_0_18px_rgba(255,111,143,.8)]"
                      style={{ left: `${18 + (i * 37) % 64}%`, top: `${14 + (i * 23) % 70}%`, transform: 'translateZ(6px)' }} />
                  ))}
                </div>
                {/* guard engine */}
                <div className="layer absolute inset-0 overflow-hidden rounded-[30px] border border-[#4F7BFF]/50 bg-[#4F7BFF]/10" style={{ transform: 'translateZ(130px)' }}>
                  <div className="guard-red absolute inset-0 rounded-[30px] border-2 border-[#FF6F8F] bg-[#FF6F8F]/15" />
                  <div className="scan absolute inset-x-0 top-0 h-8 bg-gradient-to-b from-transparent via-white/40 to-transparent" />
                  <div className="absolute inset-0 grid place-items-center"><span className="x-stamp rounded-xl border-[3px] border-[#FF6F8F] px-4 py-1 font-display text-3xl font-extrabold uppercase text-[#FF6F8F]">Blocked</span></div>
                </div>
                {/* vault */}
                <div className="layer absolute inset-0 rounded-[30px] border border-white/25 bg-gradient-to-br from-navy-soft to-navy" style={{ transform: 'translateZ(260px)' }}>
                  <div className="absolute inset-0 grid place-items-center">
                    <svg viewBox="0 0 24 24" className="h-20 w-20" aria-hidden><path d="M12 2 4 5v6c0 5 3.4 9.3 8 11 4.6-1.7 8-6 8-11V5l-8-3Z" fill="#fff" fillOpacity=".95" /><path d="m8.5 12 2.5 2.5 4.5-5" stroke="#24369F" strokeWidth="2.2" fill="none" strokeLinecap="round" /></svg>
                  </div>
                  {Array.from({ length: 6 }, (_, i) => (
                    <span key={i} className="coin absolute h-5 w-5 rounded-full border-2 border-white bg-[#4F7BFF]"
                      style={{ left: `${14 + i * 13}%`, top: '78%', transform: 'translateZ(8px)' }} />
                  ))}
                  <div className="lid absolute inset-0 rounded-[30px] border-2 border-[#9DB6FF] bg-white/10" style={{ transform: 'translateZ(36px)' }} />
                </div>
              </div>
            </div>
            {/* labels + chips (flat, outside 3D) */}
            <div className="pointer-events-none absolute bottom-16 left-0 font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Markets → Guard engine → Vault</div>
            <div className="bait absolute right-0 top-10 max-w-[260px] rounded-2xl rounded-br-md border border-white/10 keep-white bg-white px-4 py-3 text-[#151B2E] shadow-rose">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-fog-400">message to the agent</div>
              <div className="relative mt-1 inline-block font-medium">“Incident solved, deposit at 14%”
                <span className="bait-strike absolute left-0 right-0 top-1/2 h-[2px] origin-left bg-rose-glow" />
              </div>
            </div>
            <div className="paused-chip absolute bottom-32 right-4 rounded-full keep-white bg-white px-4 py-2 font-mono text-[12px] font-semibold uppercase tracking-[0.14em] text-rose-glow">Deposits {s.vault.deposits_paused ? 'paused' : 'open'}</div>
            <div className="proof-chip absolute bottom-16 right-4 rounded-full border border-white/15 bg-white/5 px-4 py-2 font-mono text-[12px] text-white/80">⛓ {anchored ? `${anchored.id} · ${shortHash(anchored.record_hash ?? anchored.anchor_tx ?? '')}` : 'fingerprint pending'}</div>
          </div>
        </div>
      </section>

      {/* ───────── 03 PROOF: bento ───────── */}
      <section id="proof" className="relative -mt-10 rounded-t-[2.5rem] bg-ink-950 pb-28 pt-28">
        <div className="mx-auto max-w-[1240px] px-5 sm:px-8">
          <Eyebrow>03 — The proof</Eyebrow>
          <h2 className="mt-4 font-display text-[clamp(2.4rem,5.4vw,4.8rem)] font-bold leading-[0.95] tracking-[-0.05em]">
            Every number, <span className="font-serif font-normal italic tracking-normal text-signal-violet">on the record.</span>
          </h2>

          <div className="mt-14 grid gap-5 lg:grid-cols-12">
            <div className="rise lg:col-span-7"><Tilt className="h-full rounded-[28px] border border-ink-700 bg-white p-7 shadow-soft">
              <div data-testid="backing-card">
                <div className="flex items-end justify-between gap-4">
                  <div>
                    <Eyebrow>{backed?.symbol ?? 'rsETH'} backing</Eyebrow>
                    <div className="mt-2 font-display text-7xl font-bold tracking-[-0.05em] text-rose-glow tabular-nums">{bps !== null ? formatBpsPct(bps) : '—'}</div>
                  </div>
                  <span className="rounded-full bg-rose-50 px-3 py-1.5 font-mono text-[12px] text-rose-glow ring-1 ring-rose-200">alert under 99%</span>
                </div>
                <div className="mt-6 h-52">
                  {chart.length > 1 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chart} margin={{ top: 8, right: 4, bottom: 0, left: -18 }}>
                        <defs>
                          <linearGradient id="bkFill6" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#2747E0" stopOpacity={0.28} />
                            <stop offset="100%" stopColor="#2747E0" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="b" type="number" domain={['dataMin', 'dataMax']} tick={{ fill: '#9097B0', fontSize: 11, fontFamily: 'JetBrains Mono' }} tickFormatter={(b: number) => String(b).slice(-4)} axisLine={false} tickLine={false} />
                        <YAxis domain={[0, 100]} tick={{ fill: '#9097B0', fontSize: 11, fontFamily: 'JetBrains Mono' }} tickFormatter={(v: number) => `${v}%`} axisLine={false} tickLine={false} />
                        <ReferenceLine y={99} stroke="#E5486B" strokeDasharray="4 4" />
                        {firstCritical && <ReferenceLine x={firstCritical.block_number} stroke="#E5486B" strokeWidth={2} />}
                        <Area type="linear" dataKey="backing" stroke="#2747E0" strokeWidth={2.5} fill="url(#bkFill6)" isAnimationActive={false} connectNulls={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : <div className="grid h-full place-items-center text-fog-400">The chart fills in with the first blocks.</div>}
                </div>
              </div>
            </Tilt></div>

            <div className="rise lg:col-span-5"><Tilt className="h-full rounded-[28px] border border-ink-700 bg-white p-7 shadow-soft">
              <div className="flex items-center justify-between"><Eyebrow>Alerts</Eyebrow><Link to="/alerts" className="font-mono text-[12px] text-signal-violet">all →</Link></div>
              <ul className="mt-5 space-y-3.5">
                {sortedAlerts.length === 0 && <li className="text-fog-400">Nothing yet. Watching.</li>}
                {sortedAlerts.slice(0, 5).map((a) => (
                  <li key={a.id} className="flex items-center gap-3">
                    <SeverityBadge severity={a.severity} />
                    <span className="min-w-0 flex-1 truncate font-medium">{ruleLabel(a.rule_id)}</span>
                    <span className="font-mono text-[12px] text-fog-400">#{a.block_number}</span>
                  </li>
                ))}
              </ul>
            </Tilt></div>

            <div className="rise lg:col-span-4"><Tilt className="h-full rounded-[28px] bg-[#0B0F1C] p-7 text-white">
              <div data-testid="vault-status">
                <Eyebrow dark>Vault</Eyebrow>
                <div className="mt-6 flex items-center gap-4">
                  <span className={`grid h-14 w-14 place-items-center rounded-2xl ${s.vault.deposits_paused ? 'bg-rose-glow' : 'bg-green-600'}`}>
                    <svg viewBox="0 0 24 24" className="h-7 w-7" aria-hidden><rect x="5" y="10" width="14" height="10" rx="2.5" fill="#fff" /><path d="M8 10V7.5a4 4 0 0 1 8 0V10" stroke="#fff" strokeWidth="2" fill="none" /></svg>
                  </span>
                  <span className="font-display text-3xl font-bold tracking-tight">{s.vault.deposits_paused ? 'Deposits PAUSED' : 'Deposits open'}</span>
                </div>
              </div>
            </Tilt></div>

            <div className="rise lg:col-span-8"><Tilt className="h-full rounded-[28px] border border-ink-700 bg-white p-7 shadow-soft">
              <Eyebrow>Our positions</Eyebrow>
              <div className="mt-5 space-y-3.5">
                {positions.length === 0 && <div className="text-fog-400">Everything is back in the vault.</div>}
                {positions.map((p) => (
                  <div data-testid="position-row" key={`${p.deployment_id}:${p.asset}`} className="flex flex-wrap items-center gap-x-6 gap-y-2">
                    <span className="w-52 font-semibold">{p.asset} <span className="font-normal text-fog-400">· {SHORT_DEP[p.deployment_id] ?? p.deployment_id}</span></span>
                    <span className="w-28 tabular-nums">{formatUsd(p.value_usd)}</span>
                    <ToneBar bps={p.withdrawable_ratio_bps} tone={withdrawableTone(p.withdrawable_ratio_bps)} label={`${p.asset} withdrawable`} />
                  </div>
                ))}
              </div>
            </Tilt></div>

            <div className="rise lg:col-span-12">
              <div className="flex items-center justify-between px-1"><Eyebrow>Markets watched · every block</Eyebrow></div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
                {s.reserves.map((r) => {
                  const bad = r.paused || r.frozen
                  return (
                    <div data-testid="reserve-row" key={`${r.deployment_id}:${r.asset}`} className={`group rounded-2xl border bg-white px-4 py-4 transition hover:-translate-y-1 hover:shadow-soft ${bad ? 'border-rose-200' : 'border-ink-700'}`}>
                      <div className="flex items-center justify-between">
                        <span className="font-display text-lg font-bold">{r.asset}</span>
                        <span className={`h-2 w-2 rounded-full ${r.paused ? 'pulse-dot bg-rose-glow' : r.frozen ? 'bg-amber-500' : 'bg-green-500'}`} />
                      </div>
                      <div className="mt-0.5 font-mono text-[11px] text-fog-400">{SHORT_DEP[r.deployment_id] ?? r.deployment_id}</div>
                      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-ink-800">
                        <div className={`h-full rounded-full ${r.utilization_bps >= 9800 ? 'bg-rose-glow' : r.utilization_bps >= 9000 ? 'bg-amber-500' : 'bg-signal-violet'}`} style={{ width: `${r.borrowable ? Math.min(100, r.utilization_bps / 100) : 0}%` }} />
                      </div>
                      <div className="mt-1.5 font-mono text-[11px] text-fog-500">{r.paused ? 'paused' : r.frozen ? 'frozen' : r.borrowable ? `${(r.utilization_bps / 100).toFixed(0)}% used` : 'collateral'}</div>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="rise grid overflow-hidden rounded-[28px] border border-ink-700 bg-white shadow-soft sm:grid-cols-2 lg:col-span-12 xl:grid-cols-4">
              {[
                { id: 'total-value', k: 'Treasury', v: t.value_usd ?? 0, c: 'text-fog-100' },
                { id: 'total-idle', k: 'Safe in the vault', v: t.idle_usd ?? 0, c: 'text-signal-violet' },
                { id: 'total-withdrawable', k: 'Still in markets', v: t.withdrawable_usd ?? 0, c: 'text-fog-100' },
                { id: 'total-at-risk', k: 'At risk', v: t.at_risk_usd ?? 0, c: (t.at_risk_usd ?? 0) > 0 ? 'text-rose-glow' : 'text-fog-100' },
              ].map((x) => (
                <div key={x.id} className="border-b border-ink-700 px-7 py-6 last:border-b-0 sm:border-r xl:border-b-0">
                  <Eyebrow>{x.k}</Eyebrow>
                  <Counter value={x.v} format={usd} testId={x.id} className={`mt-2 block font-display text-4xl font-bold tracking-[-0.03em] tabular-nums ${x.c}`} />
                </div>
              ))}
            </div>

            <div className="rise lg:col-span-12"><Tilt className="h-full rounded-[28px] bg-gradient-to-br from-navy-soft to-navy p-7 text-white">
              <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
                <Eyebrow dark>Evidence</Eyebrow>
                <span className="caret min-w-0 flex-1 truncate font-mono text-[15px] text-white/90">{anchored ? `${anchored.id}  ·  ${anchored.record_hash ?? anchored.anchor_tx}` : 'No decision anchored yet'}</span>
                <Link to="/evidence" className="rounded-full keep-white bg-white px-5 py-2.5 text-[14px] font-semibold text-navy hover:bg-blue-50">Verify it</Link>
              </div>
            </Tilt></div>
          </div>
        </div>
      </section>

      {/* ───────── OUTRO ───────── */}
      <section className="outro relative overflow-hidden bg-ink-950 pb-24">
        <div className="slide-l whitespace-nowrap font-display text-[clamp(4rem,12vw,11rem)] font-bold leading-none tracking-[-0.05em] outline-text">Agent proposes · Platform checks ·</div>
        <div className="slide-r whitespace-nowrap font-display text-[clamp(4rem,12vw,11rem)] font-bold leading-none tracking-[-0.05em] text-fog-100">Vault executes · Agent proposes ·</div>
        <div className="mx-auto mt-16 max-w-[1240px] px-5 sm:px-8">
          <div className="relative overflow-hidden rounded-[2.5rem] bg-[#05070B] px-8 py-20 text-center text-white" onMouseMove={spot}>
            <div aria-hidden className="spot pointer-events-none absolute inset-0" />
            <div aria-hidden className="grain pointer-events-none absolute inset-0" />
            <h2 className="relative font-display text-[clamp(2.4rem,5.4vw,4.6rem)] font-bold leading-[0.95] tracking-[-0.05em]">
              Replay the attack.<br /><span className="font-serif font-normal italic tracking-normal text-[#9DB6FF]">Watch it stop.</span>
            </h2>
            <Magnetic className="relative mt-10">
              <Link to="/demo" className="block rounded-full keep-white bg-white px-9 py-4 text-[16px] font-semibold text-[#05070B] hover:bg-blue-100">Run the attack →</Link>
            </Magnetic>
          </div>
        </div>
      </section>
    </div>
  )
}
