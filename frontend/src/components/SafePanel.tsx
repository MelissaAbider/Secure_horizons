import { useState } from 'react'
import { ApiError } from '../api'
import { useDashboardData } from '../DataContext'
import type { Polled } from '../hooks/usePolling'
import { formatUnits, shortHash } from '../lib/format'
import { safeApi, type Decision, type SafeStatus } from '../lib/safeApi'
import { connectWallet, signTypedData, walletError } from '../lib/wallet'
import { Pill } from './ui'

// The connected Safe once monitoring is on: balances, positions (withdrawable share from the monitor), allocations
// through the teller window (only what the sealed list allows), re-sealing after a reset, test-token top-up.

const CARD = 'rounded-2xl border border-ink-700 bg-white p-5'
const BTN = 'inline-flex items-center justify-center gap-2 rounded-xl bg-fog-100 px-4 py-2.5 text-[14px] font-semibold text-ink-950 transition hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-40'
const BTN_LIGHT = 'inline-flex items-center justify-center gap-2 rounded-xl border border-ink-700 bg-white px-4 py-2.5 text-[14px] font-semibold text-fog-100 transition hover:border-fog-500 disabled:cursor-not-allowed disabled:opacity-40'
const INPUT = 'w-full rounded-xl border border-ink-700 bg-white px-3 py-2.5 text-[14px] outline-none focus:border-signal-violet'

function short(a?: string): string { return a ? `${a.slice(0, 6)}…${a.slice(-4)}` : '—' }

export function SafePanel({ safe, ticked, onDisconnect }: { safe: Polled<SafeStatus>; ticked: string[]; onDisconnect?: () => void }) {
  const { state } = useDashboardData()
  const d = safe.data
  const [integration, setIntegration] = useState('')
  const [amount, setAmount] = useState('')
  const [busy, setBusy] = useState<string>()
  const [msg, setMsg] = useState<{ tone: 'ok' | 'bad'; text: string; txs?: string[] }>()

  if (!d?.connected) return null
  const explorer = d.network === 'fuji' ? d.explorer_url : undefined
  const labels = Object.fromEntries(d.integrations_available.map((x) => [x.id, x.label]))
  const sealed = d.sealed_integrations ?? []
  const chosen = integration || sealed[0] || ''
  const asset = chosen.split(':')[1] ?? 'USDC'
  const dec = d.decimals ?? { USDC: 6, WETH: 18 }
  const monitored = new Map((state.data?.positions ?? []).map((p) => [`${p.deployment_id}:${p.asset}`, p]))

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label); setMsg(undefined)
    try { await fn(); await safe.refresh() }
    catch (e) { setMsg({ tone: 'bad', text: e instanceof ApiError ? e.detail : walletError(e) }) }
    finally { setBusy(undefined) }
  }
  const allocate = (action: 'deposit' | 'withdraw', value: string) => run(action, async () => {
    const r: Decision = await safeApi.allocate(chosen, action, value)
    setMsg(r.verdict === 'EXECUTED'
      ? { tone: 'ok', text: `${action === 'deposit' ? 'Deposited' : 'Withdrew'} through the teller window`, txs: r.txs }
      : { tone: 'bad', text: `Refused: ${r.detail ?? r.reason}` })
  })
  const reseal = () => run('seal', async () => {
    const owner = await connectWallet(d.chain_id)
    if (owner.toLowerCase() !== d.owner?.toLowerCase()) throw new Error(`Switch your wallet to the Safe owner ${short(d.owner)}.`)
    const req = await safeApi.prepare('seal', ticked.length ? ticked : sealed)
    const r = await safeApi.submit(req.safe_tx_hash, await signTypedData(owner, req.typed_data))
    setMsg({ tone: 'ok', text: 'List sealed again with the new markets', txs: [r.tx_hash] })
  })
  const fund = () => run('fund', async () => { const r = await safeApi.fund(); setMsg({ tone: 'ok', text: 'Test tokens credited', txs: r.txs }) })

  const Tx = ({ hash }: { hash: string }) => explorer
    ? <a href={`${explorer}/tx/${hash}`} target="_blank" rel="noreferrer" className="font-mono text-signal-violet hover:underline">{shortHash(hash)} ↗</a>
    : <span className="font-mono">{shortHash(hash)}</span>

  return (
    <section data-testid="safe-panel" className="mt-6 rounded-[28px] border border-white bg-white/75 p-7 shadow-[0_20px_60px_-30px_rgba(21,27,46,.25)] backdrop-blur sm:p-9">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="font-mono text-[12px] font-medium uppercase tracking-[0.24em] text-fog-400">Your Safe</div>
          <h2 className="mt-3 font-display text-[26px] font-semibold tracking-[-0.02em]">
            {explorer ? <a href={`${explorer}/address/${d.safe}`} target="_blank" rel="noreferrer" className="hover:underline">{short(d.safe)}</a> : short(d.safe)}
          </h2>
          <p className="mt-1 text-[14px] text-fog-400">Owned by {short(d.owner)} alone · the platform relays, it holds no key
            {onDisconnect && <> · <button onClick={onDisconnect} className="font-medium text-rose-glow hover:underline">Disconnect</button></>}</p>
        </div>
        <Pill tone={d.seal_status === 'sealed' ? 'ok' : 'warn'}>{d.seal_status === 'sealed' ? 'list sealed' : d.seal_status === 'stale' ? 're-seal needed' : 'not sealed'}</Pill>
      </div>

      {d.seal_status === 'stale' && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[14px] text-amber-800">
          The test network was reset: the markets have new addresses, so your list must be sealed again.
          <button onClick={() => void reseal()} disabled={!!busy} className={BTN}>{busy === 'seal' ? 'Sign in your wallet…' : 'Seal again (sign)'}</button>
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className={CARD}>
          <div className="flex items-center justify-between"><b>Holdings</b>
            <button onClick={() => void fund()} disabled={!!busy} className="text-[13px] font-medium text-signal-violet hover:underline disabled:opacity-40">{busy === 'fund' ? 'Crediting…' : 'Top up test tokens'}</button>
          </div>
          <table className="mt-3 w-full table-fixed text-left text-[14px]" data-testid="safe-holdings">
            <colgroup><col /><col className="w-[150px]" /><col className="w-[110px]" /></colgroup>
            <thead className="font-mono text-[10px] uppercase tracking-[0.14em] text-fog-500"><tr><th className="py-2">Where</th><th className="text-right">Amount</th><th className="text-right">Withdrawable</th></tr></thead>
            <tbody>
              {Object.entries(d.balances ?? {}).map(([sym, v]) => (
                <tr key={sym} className="border-t border-ink-700"><td className="py-2">In the Safe</td><td className="text-right tabular-nums">{formatUnits(v, dec[sym] ?? 18)} {sym}</td><td className="text-right text-fog-400">—</td></tr>
              ))}
              {(d.positions ?? []).map((p) => {
                const sym = p.integration.split(':')[1]
                const m = monitored.get(p.integration)
                const pct = m ? Math.round(m.withdrawable_ratio_bps / 100) : undefined
                return (
                  <tr key={p.integration} className="border-t border-ink-700">
                    <td className="py-2">{labels[p.integration] ?? p.integration}</td>
                    <td className="text-right tabular-nums">{formatUnits(p.supplied, dec[sym] ?? 18)} {sym}</td>
                    <td className={`text-right tabular-nums font-semibold ${pct === undefined ? 'text-fog-400' : pct >= 80 ? 'text-green-700' : pct >= 50 ? 'text-amber-600' : 'text-red-600'}`}>{pct === undefined ? '…' : `${pct}%`}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <div className={CARD}>
          <b>Allocate</b>
          <p className="mt-1 text-[13px] text-fog-400">Only what your sealed list allows: the teller window proves each operation against the root you signed.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_140px]">
            <select data-testid="allocate-integration" value={chosen} onChange={(e) => setIntegration(e.target.value)} className={INPUT}>
              {sealed.map((id) => <option key={id} value={id}>{labels[id] ?? id}</option>)}
            </select>
            <input data-testid="allocate-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={`amount ${asset}`} className={`${INPUT} text-right font-mono`} />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button data-testid="deposit" disabled={!!busy || !chosen || !/^\d+(\.\d+)?$/.test(amount) || d.seal_status !== 'sealed'} onClick={() => void allocate('deposit', amount)} className={BTN}>{busy === 'deposit' ? 'Depositing…' : 'Deposit'}</button>
            <button disabled={!!busy || !chosen || !/^\d+(\.\d+)?$/.test(amount) || d.seal_status !== 'sealed'} onClick={() => void allocate('withdraw', amount)} className={BTN_LIGHT}>{busy === 'withdraw' ? 'Withdrawing…' : 'Withdraw'}</button>
            <button disabled={!!busy || !chosen || d.seal_status !== 'sealed'} onClick={() => void allocate('withdraw', 'max')} className={BTN_LIGHT}>Withdraw all</button>
          </div>
          <p className="mt-3 text-[12px] text-fog-400">The attack drains WETH on the Ethereum deployment: allocate there to watch your Safe get caught.</p>
        </div>
      </div>

      {msg && (
        <div role={msg.tone === 'bad' ? 'alert' : 'status'} className={`mt-4 rounded-xl px-4 py-3 text-[14px] ${msg.tone === 'ok' ? 'border border-green-200 bg-green-50 text-green-800' : 'border border-red-200 bg-red-50 text-red-700'}`}>
          {msg.text}{msg.txs?.length ? ': ' : ''}{msg.txs?.map((h, i) => <span key={h}>{i > 0 && ' · '}<Tx hash={h} /></span>)}
        </div>
      )}
    </section>
  )
}
