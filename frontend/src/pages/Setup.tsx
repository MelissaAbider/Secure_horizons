import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { LiveDemo } from '../components/LiveDemo'
import { getOperator } from '../DataContext'
import {
  PROTOCOLS, defaultSetup, fingerprint, isAddress, loadSetup, policyJson, ruleHints, saveSetup, shortAddr, stepsDone,
  type SetupState,
} from '../lib/setup'

const STEPS = ['Connect your Safe', 'Choose your protocols', 'Set your agent', 'Start monitoring']
const NEXT = ['connect your Safe.', 'choose your protocols.', 'set your agent.', 'start monitoring.']

function greeting(d = new Date()): string {
  const h = d.getHours()
  return h < 5 ? 'Good night' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : h < 22 ? 'Good evening' : 'Good night'
}

function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="font-mono text-[12px] font-medium uppercase tracking-[0.24em] text-fog-400">{children}</div>
}

const BTN = 'inline-flex items-center justify-center gap-2 rounded-2xl bg-fog-100 px-6 py-3.5 text-[15px] font-semibold text-ink-950 shadow-[0_8px_24px_-10px_rgba(14,20,36,.6)] transition hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-40'
const BTN_LIGHT = 'inline-flex items-center justify-center gap-2 rounded-2xl border border-ink-700 bg-white px-6 py-3.5 text-[15px] font-semibold text-fog-100 transition hover:border-fog-500'
const INPUT = 'w-full rounded-xl border border-ink-700 bg-white px-4 py-3 text-[15px] outline-none transition focus:border-signal-violet focus:ring-4 focus:ring-blue-100'
const Arrow = () => <span aria-hidden>→</span>

function Ring({ pct }: { pct: number }) {
  const r = 34, c = 2 * Math.PI * r
  return (
    <div className="relative grid h-20 w-20 place-items-center">
      <svg viewBox="0 0 80 80" className="absolute inset-0 -rotate-90" aria-hidden>
        <circle cx="40" cy="40" r={r} fill="none" stroke="#E3E6F1" strokeWidth="6" />
        <circle cx="40" cy="40" r={r} fill="none" stroke="#2747E0" strokeWidth="6" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)} style={{ transition: 'stroke-dashoffset .6s ease' }} />
      </svg>
      <span data-testid="setup-pct" className="font-display text-[17px] font-semibold tabular-nums">{pct}%</span>
    </div>
  )
}

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}
      className={`relative h-7 w-12 shrink-0 rounded-full transition ${on ? 'bg-signal-violet' : 'bg-ink-600'}`}>
      <span className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-all ${on ? 'left-6' : 'left-1'}`} />
    </button>
  )
}

export function Setup() {
  const [s, setS] = useState<SetupState>(loadSetup)
  const done = stepsDone(s)
  const count = done.filter(Boolean).length
  const firstOpen = done.findIndex((d) => !d)
  const [open, setOpen] = useState<number>(firstOpen === -1 ? -1 : firstOpen)
  const [addrError, setAddrError] = useState('')
  const [fp, setFp] = useState('')
  const name = getOperator()
  const policy = useMemo(() => policyJson(s), [s])
  const hints = ruleHints(s.instructions, s.protocols).filter((h) => s.rules.protocolCaps[h.protocolId] !== h.pct)

  useEffect(() => { saveSetup(s) }, [s])
  useEffect(() => { let on = true; fingerprint(policy).then((h) => { if (on) setFp(h) }); return () => { on = false } }, [policy])

  const update = (p: Partial<SetupState>) => setS((x) => ({ ...x, ...p }))
  const goNext = (i: number) => setOpen(i + 1 < 4 ? i + 1 : -1)

  function connect() {
    if (!isAddress(s.safe)) { setAddrError('A Safe address is 0x followed by 40 letters or digits.'); return }
    setAddrError('')
    update({ connected: true, safe: s.safe.trim() })
    goNext(0)
  }
  function nextAction() {
    const i = done.findIndex((d) => !d)
    if (i === -1) return
    setOpen(i)
    document.getElementById(`step-${i}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
  function download() {
    const blob = new Blob([JSON.stringify({ ...policy, fingerprint: fp }, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob); a.download = 'treasury-guard-policy.json'; a.click()
    setTimeout(() => URL.revokeObjectURL(a.href), 1000)
  }

  const nextLabel = firstOpen === -1 ? 'Open the dashboard' : STEPS[firstOpen]

  return (
    <div className="setup-bg relative -mx-4 -mt-4 min-h-[calc(100vh-80px)] px-4 pb-16 pt-12 sm:-mx-6 sm:px-6">
      <div className="mx-auto max-w-[1240px]">
        {/* header */}
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <Eyebrow>Setup</Eyebrow>
            <h1 className="mt-3 font-display text-[clamp(2.2rem,4vw,3.2rem)] font-semibold leading-none tracking-[-0.035em]">
              {greeting()}{name && name !== 'dashboard-operator' ? ` ${name}` : ''}
            </h1>
            <p className="mt-3 text-lg text-fog-400">{firstOpen === -1 ? 'Your treasury is under watch.' : `Next step: ${NEXT[firstOpen]}`}</p>
          </div>
          {firstOpen === -1
            ? <Link to="/" className={BTN}>Open the dashboard <Arrow /></Link>
            : <button onClick={nextAction} className={BTN}>{nextLabel} <Arrow /></button>}
        </div>

        <div className="mt-10 grid gap-6 lg:grid-cols-[1.45fr_1fr]">
          {/* ── Getting started ── */}
          <section className="min-w-0 rounded-[28px] border border-white bg-white/75 p-7 shadow-[0_20px_60px_-30px_rgba(21,27,46,.25)] backdrop-blur sm:p-9">
            <div className="flex items-start justify-between">
              <div>
                <Eyebrow>Getting started</Eyebrow>
                <h2 data-testid="setup-count" className="mt-3 font-display text-[26px] font-semibold tracking-[-0.02em]">{count} of 4 steps done</h2>
              </div>
              <div className="flex flex-col items-center gap-2">
                <Ring pct={count * 25} />
                {count > 0 && (
                  <button data-testid="restart-setup" onClick={() => { setS(defaultSetup()); setAddrError(''); setOpen(0) }}
                    className="rounded-full border border-ink-700 bg-white px-3 py-1 text-[13px] font-medium text-fog-300 transition hover:border-fog-500 hover:text-fog-100">↺ Restart</button>
                )}
              </div>
            </div>

            <ol className="mt-7 space-y-2">
              {STEPS.map((label, i) => {
                const isOpen = open === i
                const ok = done[i]
                const locked = i > 0 && !done[i - 1] && !ok
                return (
                  <li key={label} id={`step-${i}`} className={`rounded-2xl transition ${isOpen ? 'border border-ink-700 bg-white shadow-soft' : 'border border-transparent'}`}>
                    <button type="button" disabled={locked} onClick={() => setOpen(isOpen ? -1 : i)} data-testid={`step-${i}`}
                      className="flex w-full items-center gap-4 px-5 py-4 text-left disabled:cursor-not-allowed disabled:opacity-50">
                      <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-full font-mono text-[13px] font-semibold transition ${ok ? 'bg-green-600 text-white' : isOpen ? 'bg-signal-violet text-white' : 'border border-ink-600 bg-white text-fog-300'}`}>
                        {ok ? '✓' : i + 1}
                      </span>
                      <span className={`flex-1 text-[17px] ${ok && !isOpen ? 'text-fog-400' : 'text-fog-100'}`}>{label}</span>
                      {ok && !isOpen && <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-green-700">done · <span className="text-signal-violet underline-offset-2 hover:underline">edit</span></span>}
                      <span aria-hidden className={`text-fog-400 transition ${isOpen ? 'rotate-90' : ''}`}>→</span>
                    </button>

                    {isOpen && (
                      <div className="px-5 pb-6 pt-1 sm:pl-[4.25rem]">
                        {i === 0 && (
                          <div className="space-y-4">
                            <p className="text-fog-400">Paste the address of your company's Safe. We only read it: the money stays in the vault and we never hold a key.</p>
                            <label className="block">
                              <span className="mb-1.5 block font-mono text-[11px] uppercase tracking-[0.18em] text-fog-400">Safe address</span>
                              <input data-testid="safe-input" value={s.safe} onChange={(e) => update({ safe: e.target.value, connected: false })}
                                placeholder="0x…" spellCheck={false} className={`${INPUT} font-mono`} />
                            </label>
                            {addrError && <p role="alert" className="text-[14px] text-rose-glow">{addrError}</p>}
                            <div className="grid gap-3 sm:grid-cols-2">
                              <label className="block">
                                <span className="mb-1.5 block font-mono text-[11px] uppercase tracking-[0.18em] text-fog-400">Network</span>
                                <select value={s.network} onChange={(e) => update({ network: e.target.value as SetupState['network'] })} className={INPUT}>
                                  <option value="fuji">Avalanche Fuji (test network)</option>
                                  <option value="local">Local (anvil)</option>
                                </select>
                              </label>
                              <label className="block">
                                <span className="mb-1.5 block font-mono text-[11px] uppercase tracking-[0.18em] text-fog-400">Signatures needed</span>
                                <select value={`${s.threshold}/${s.signers}`} onChange={(e) => { const [a, b] = e.target.value.split('/').map(Number); update({ threshold: a, signers: b }) }} className={INPUT}>
                                  {['2/3', '3/5', '4/7'].map((v) => <option key={v} value={v}>{v.replace('/', ' of ')}</option>)}
                                </select>
                              </label>
                            </div>
                            <button data-testid="connect-safe" onClick={connect} className={BTN}>Connect the Safe <Arrow /></button>
                          </div>
                        )}

                        {i === 1 && (
                          <div className="space-y-4">
                            <p className="text-fog-400">Tick what the agent may use. This becomes the sealed list your signers approve.</p>
                            <div className="grid gap-3 sm:grid-cols-2">
                              {PROTOCOLS.map((p) => {
                                const on = s.protocols.includes(p.id)
                                return (
                                  <button key={p.id} type="button" disabled={!p.available} data-testid={`proto-${p.id}`}
                                    onClick={() => update({ protocols: on ? s.protocols.filter((x) => x !== p.id) : [...s.protocols, p.id] })}
                                    className={`flex items-center justify-between rounded-xl border px-4 py-3.5 text-left transition disabled:cursor-not-allowed disabled:opacity-45 ${on ? 'border-signal-violet bg-blue-50/70' : 'border-ink-700 bg-white hover:border-fog-500'}`}>
                                    <span className="font-medium">{p.label}</span>
                                    <span className={`grid h-5 w-5 place-items-center rounded-md text-[12px] ${on ? 'bg-signal-violet text-white' : 'border border-ink-600'}`}>{on ? '✓' : ''}</span>
                                  </button>
                                )
                              })}
                            </div>
                            <button onClick={() => goNext(1)} disabled={s.protocols.length === 0} className={BTN}>Save the list <Arrow /></button>
                          </div>
                        )}

                        {i === 2 && (
                          <div className="space-y-6">
                            <div className="space-y-5">
                              <div className="grid gap-x-8 gap-y-4 rounded-2xl bg-ink-950 p-5 sm:grid-cols-2">
                                <div className="flex items-center justify-between sm:col-span-2">
                                  <span className="font-semibold">Guaranteed rules</span>
                                  <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-fog-400">signed by the Safe</span>
                                </div>
                                <label className="block">
                                  <div className="flex justify-between text-[14px]"><span className="text-fog-300">Max per protocol</span><span className="font-mono font-semibold">{s.rules.maxPerProtocolPct}%</span></div>
                                  <input type="range" min={10} max={100} step={5} value={s.rules.maxPerProtocolPct} aria-label="Max per protocol"
                                    onChange={(e) => update({ rules: { ...s.rules, maxPerProtocolPct: Number(e.target.value) }, agentSaved: false })} className="mt-2 w-full accent-[#2747E0]" />
                                </label>
                                <label className="block">
                                  <div className="flex justify-between text-[14px]"><span className="text-fog-300">Max loss per move</span><span className="font-mono font-semibold">{s.rules.maxLossPct}%</span></div>
                                  <input type="range" min={0.1} max={2} step={0.1} value={s.rules.maxLossPct} aria-label="Max loss per move"
                                    onChange={(e) => update({ rules: { ...s.rules, maxLossPct: Number(e.target.value) }, agentSaved: false })} className="mt-2 w-full accent-[#2747E0]" />
                                </label>
                                <label className="flex items-center justify-between gap-3 text-[14px]">
                                  <span className="text-fog-300">Human signature above</span>
                                  <select value={s.rules.humanAboveUsd} onChange={(e) => update({ rules: { ...s.rules, humanAboveUsd: Number(e.target.value) }, agentSaved: false })}
                                    className="rounded-lg border border-ink-700 bg-white px-2 py-1.5 font-mono">
                                    {[25000, 50000, 100000, 250000].map((v) => <option key={v} value={v}>${v.toLocaleString('en-US')}</option>)}
                                  </select>
                                </label>
                                <div className="flex items-center justify-between text-[14px]">
                                  <span className="text-fog-300">Circuit breaker</span>
                                  <Toggle on={s.rules.circuitBreaker} label="Circuit breaker" onChange={(v) => update({ rules: { ...s.rules, circuitBreaker: v }, agentSaved: false })} />
                                </div>
                                {Object.entries(s.rules.protocolCaps).map(([pid, pct]) => (
                                  <div key={pid} className="flex items-center justify-between rounded-lg bg-white px-3 py-2 text-[14px]">
                                    <span className="text-fog-300">Max on {PROTOCOLS.find((p) => p.id === pid)?.label ?? pid}</span>
                                    <span className="flex items-center gap-2 font-mono font-semibold">{pct}%
                                      <button aria-label="Remove rule" className="text-fog-500 hover:text-rose-glow" onClick={() => { const c = { ...s.rules.protocolCaps }; delete c[pid]; update({ rules: { ...s.rules, protocolCaps: c }, agentSaved: false }) }}>✕</button>
                                    </span>
                                  </div>
                                ))}
                              </div>
                              <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                  <span className="font-semibold">What you want</span>
                                  <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-fog-400">free text</span>
                                </div>
                                <textarea data-testid="instructions" rows={5} value={s.instructions}
                                  onChange={(e) => update({ instructions: e.target.value, agentSaved: false })} className={`${INPUT} resize-none leading-relaxed`} />
                                {hints.map((h) => (
                                  <div key={h.line} data-testid="rule-hint" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[14px]">
                                    <p className="text-amber-800"><b>“{h.line}”</b> looks like a rule. As an instruction the agent may ignore it; only the {s.rules.maxPerProtocolPct}% cap is guaranteed.</p>
                                    <button data-testid="make-rule" onClick={() => update({ rules: { ...s.rules, protocolCaps: { ...s.rules.protocolCaps, [h.protocolId]: h.pct } }, agentSaved: false })}
                                      className="mt-2 rounded-lg bg-amber-600 px-3 py-1.5 font-semibold text-white hover:bg-amber-700">Make it a rule</button>
                                  </div>
                                ))}
                                <p className="text-[13px] text-fog-400">Instructions guide the agent's choices. They give it no rights.</p>
                              </div>
                            </div>
                            <button data-testid="save-agent" onClick={() => { update({ agentSaved: true }); goNext(2) }} className={BTN}>Save the agent <Arrow /></button>
                          </div>
                        )}

                        {i === 3 && (
                          <div className="space-y-4">
                            <p className="text-fog-400">Your signers seal the policy. From then on, every block, the guard checks the five detection rules, alerts your team on Discord and drafts the DORA notification. Pulling funds back on its own is phase 2.</p>
                            <ul className="grid gap-2 sm:grid-cols-2">
                              {['Forged bridge release', 'rsETH collateral surge', 'Market liquidity drain', 'Our withdrawable share', 'Bridge or market contained'].map((r, k) => (
                                <li key={r} className="flex items-center gap-3 rounded-xl border border-ink-700 bg-white px-4 py-3 text-[14px]">
                                  <span className="font-mono text-[11px] text-signal-violet">R{k + 1}</span>{r}
                                </li>
                              ))}
                            </ul>
                            <button data-testid="go-live" onClick={() => { update({ live: true, liveSince: new Date().toISOString() }); setOpen(-1) }} className={BTN}>
                              Sign with the Safe and start <Arrow />
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </li>
                )
              })}
            </ol>

            {firstOpen !== -1 && open === -1 && (
              <button onClick={nextAction} className={`${BTN} mt-7 w-full py-4`}>{nextLabel} <Arrow /></button>
            )}
          </section>

          {/* ── Your guard ── */}
          <aside className="flex min-w-0 flex-col rounded-[28px] border border-white bg-white/75 p-7 shadow-[0_20px_60px_-30px_rgba(21,27,46,.25)] backdrop-blur sm:p-9">
            <Eyebrow>Your guard</Eyebrow>
            <div className="mt-5 flex items-center gap-4">
              <span className="relative grid h-16 w-16 place-items-center rounded-2xl bg-[#0E1424]">
                <svg viewBox="0 0 24 24" className="h-8 w-8" aria-hidden><path d="M12 2 4 5v6c0 5 3.4 9.3 8 11 4.6-1.7 8-6 8-11V5l-8-3Z" fill="#4F7BFF" /><path d="m8.5 12 2.5 2.5 4.5-5" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" /></svg>
                {s.live && <span className="pulse-dot absolute -right-1 -top-1 h-3.5 w-3.5 rounded-full border-2 border-white bg-green-500" />}
              </span>
              <div>
                <div className="font-display text-[22px] font-semibold tracking-[-0.02em]">Treasury Guard</div>
                <div data-testid="guard-status" className={`text-[15px] ${s.live ? 'text-green-700' : 'text-fog-400'}`}>
                  {s.live ? `Watching ${s.network === 'fuji' ? 'Avalanche Fuji' : 'local chain'} · every block` : s.connected ? 'Connected, not watching yet' : 'Not connected'}
                </div>
              </div>
            </div>

            <dl className="mt-7 divide-y divide-ink-700 text-[15px]">
              {[
                ['Safe', s.connected ? <span className="font-mono">{shortAddr(s.safe)} · {s.threshold} of {s.signers}</span> : '—'],
                ['Allowed', s.protocols.length ? s.protocols.map((p) => PROTOCOLS.find((x) => x.id === p)?.label).join(', ') : '—'],
                ['Max per protocol', `${s.rules.maxPerProtocolPct}%`],
                ...Object.entries(s.rules.protocolCaps).map(([pid, pct]) => [`Max on ${PROTOCOLS.find((p) => p.id === pid)?.label ?? pid}`, `${pct}%`]),
                ['Human signature', `above $${s.rules.humanAboveUsd.toLocaleString('en-US')}`],
                ['Circuit breaker', s.rules.circuitBreaker ? 'ON' : 'off'],
              ].map(([k, v]) => (
                <div key={String(k)} className="flex items-start justify-between gap-4 py-3">
                  <dt className="text-fog-400">{k}</dt><dd className="text-right font-medium">{v}</dd>
                </div>
              ))}
            </dl>

            <div className="mt-6">
              <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-fog-400">Alerts go to</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(['discord', 'telegram', 'slack', 'email'] as const).map((c) => (
                  <button key={c} onClick={() => update({ channels: { ...s.channels, [c]: !s.channels[c] } })}
                    className={`rounded-full border px-4 py-2 text-[14px] capitalize transition ${s.channels[c] ? 'border-fog-100 bg-fog-100 text-ink-950' : 'border-ink-700 bg-white text-fog-300'}`}>{c}</button>
                ))}
              </div>
              <p className="mt-2 text-[13px] text-fog-400">For alerts, questions and pause. Never to widen the agent's rights.</p>
            </div>

            <div className="mt-6 rounded-2xl bg-ink-950 px-4 py-3">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-fog-400">Policy fingerprint</div>
              <div data-testid="policy-fp" className="mt-1 truncate font-mono text-[13px]">{fp || '—'}</div>
            </div>

            <div className="mt-auto grid gap-3 pt-7">
              {s.live
                ? <Link to="/" className={`${BTN} w-full py-4`}>Open the dashboard <Arrow /></Link>
                : <button onClick={nextAction} className={`${BTN_LIGHT} w-full py-4`}>{nextLabel} <Arrow /></button>}
              <button onClick={download} className="text-[14px] font-medium text-signal-violet hover:underline">Download the policy file</button>
              {(s.connected || s.live) && (
                <button onClick={() => { setS(defaultSetup()); setOpen(0) }}
                  className="text-[13px] text-fog-400 hover:text-fog-100">Start over</button>
              )}
            </div>
          </aside>
        </div>

        {s.live && <LiveDemo />}

        <p className="mt-8 text-center font-mono text-[11px] uppercase tracking-[0.16em] text-fog-500">Preview · setup is saved in this browser · the agent itself is phase 2</p>
      </div>
    </div>
  )
}
