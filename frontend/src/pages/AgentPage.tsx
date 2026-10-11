import { AgentChat } from '../components/AgentChat'
import { AGENT_RULES } from '../lib/agentDemo'

/** /agent: talk to the live agent. It proposes, the guard decides. */
export function AgentPage() {
  return (
    <div className="mx-auto grid max-w-[1240px] gap-6 py-6 lg:grid-cols-[1fr_320px]">
      <div>
        <div className="font-mono text-[12px] uppercase tracking-[0.28em] text-fog-400">Agent</div>
        <h1 className="mt-3 font-display text-[clamp(2.2rem,4vw,3.4rem)] font-bold leading-none tracking-[-0.04em]">
          Ask the agent. <span className="font-serif font-normal italic tracking-normal text-signal-violet">The guard decides.</span>
        </h1>
        <div className="mt-8"><AgentChat /></div>
      </div>
      <aside className="h-fit rounded-[28px] bg-[#0B0F1C] p-7 text-white lg:mt-[7.5rem]">
        <div className="font-mono text-[12px] uppercase tracking-[0.28em] text-white/50">Sealed rules</div>
        <dl className="mt-6 space-y-4">
          {AGENT_RULES.map((r) => (
            <div key={r.k} className="flex items-baseline justify-between gap-4 border-b border-white/10 pb-3">
              <dt className="text-white/55">{r.k}</dt><dd className="font-mono text-[14px]">{r.v}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-6 text-[13px] text-white/50">The agent never holds a key. Every proposal is re-checked against these rules before anything runs.</p>
      </aside>
    </div>
  )
}
