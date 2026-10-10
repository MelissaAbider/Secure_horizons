"use strict";
// Guided T4 + T5 demo for a non-specialist audience.
// Data comes from the real T4/T5 API (/api/...); the scenario is driven by demo-only routes (/demo/api/...).

const DEC_ID = "DEC-fuji-45201812-1";
const DECIMALS = { USDC: 6, WETH: 18, rsETH: 18 };
const MARKET = { "lend-eth": "Lending market A (Ethereum)", "lend-avax": "Lending market B (Avalanche)" };
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const usd = (n) => (n == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n));
const num = (n, d = 0) => (n == null ? "—" : Number(n).toLocaleString("en-US", { maximumFractionDigits: d }));
const badge = (v, cls) => `<span class="badge b-${esc(cls || String(v).toLowerCase())}">${esc(v)}</span>`;
const short = (h) => (h && h.length > 16 ? `${h.slice(0, 10)}…${h.slice(-4)}` : h || "—");
const utc = (iso) => (iso ? iso.replace("T", " ").replace(/\.\d+/, "").replace("Z", " UTC").replace("+00:00", " UTC") : "—");
const term = (word, tip) => `<span class="term" tabindex="0" data-tip="${esc(tip)}">${esc(word)}</span>`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const OPERATOR = "jury-member";

function units(base, decimals) {
  if (base == null) return "—";
  const v = BigInt(base), d = 10n ** BigInt(decimals);
  const whole = (v / d).toLocaleString("en-US");
  const frac = (v % d).toString().padStart(decimals, "0").slice(0, 2).replace(/0+$/, "");
  return frac ? `${whole}.${frac}` : whole;
}

function toast(msg) {
  const t = $("toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove("show"), 3500);
}

async function call(method, url, body) {
  const opt = { method, headers: {} };
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const res = await fetch(url, opt);
  const text = await res.text();
  let data; try { data = JSON.parse(text); } catch { data = text; }
  return { status: res.status, ok: res.ok, data };
}

// ---------------------------------------------------------------- state
const S = {
  step: 0, world: null, decision: null, incident: null, deps: [], report: "", verify: null, playing: false,
  flags: { replay: null, firstMatch: false, tamperDiffs: null, restoredMatch: false, approveCodes: [], submitCodes: [] },
};
function resetFlags() {
  S.flags = { replay: null, firstMatch: false, tamperDiffs: null, restoredMatch: false, approveCodes: [], submitCodes: [] };
  S.verify = null;
}

// ---------------------------------------------------------------- plain-language action texts
function actionText(a) {
  const p = a.params || {};
  const amount = a.amount && p.asset ? `${units(a.amount, DECIMALS[p.asset] ?? 18)} ${p.asset}` : p.asset || "";
  switch (a.type) {
    case "NOTIFY": return { ico: "📣", what: "Alert the on-call team", why: "A message goes out immediately (log here; e-mail / Slack once configured). It never delays the next steps." };
    case "PAUSE_DEPOSITS": return { ico: "🚪", what: "Lock the vault's front door", why: "No new money can be sent to the markets while we investigate." };
    case "EMERGENCY_WITHDRAW": return { ico: "🏃", what: `Bring ${amount} home from ${MARKET[p.deployment_id] || p.deployment_id}`,
      why: "Withdraw everything that can still be withdrawn, back into our own vault. The platform's key can only pull money home, never send it anywhere else." };
    case "OPEN_INCIDENT": return { ico: "📁", what: "Open an incident file", why: "Starts the compliance record and the regulatory clock (see step 7)." };
    case "UNPAUSE_DEPOSITS": return { ico: "🧑‍⚖️", what: "Re-open deposits — waiting for a human", why: "Loosening the rules is never automatic: a human signer must approve it (step 6)." };
    default: return { ico: "•", what: a.type, why: "" };
  }
}

// ---------------------------------------------------------------- plan checklist (T4 / T5 task sheets)
const EXPECTED_ACTIONS = [["NOTIFY", "auto"], ["PAUSE_DEPOSITS", "auto"], ["EMERGENCY_WITHDRAW", "auto"], ["EMERGENCY_WITHDRAW", "auto"],
  ["EMERGENCY_WITHDRAW", "auto"], ["EMERGENCY_WITHDRAW", "auto"], ["OPEN_INCIDENT", "auto"], ["UNPAUSE_DEPOSITS", "human"]];
const EXPECTED_EW = [["lend-eth", "USDC", "400000000000"], ["lend-eth", "WETH", "150000000000000000000"],
  ["lend-avax", "USDC", "300000000000"], ["lend-avax", "WETH", "100000000000000000000"]];
const REPORT_TITLES = ["1. General information", "2. Classification proposal", "3. Description", "4. Classification criteria",
  "5. Actions taken", "6. Deadlines", "7. Third parties involved", "8. Human review"];
const H = 3600e3;

const PLAN = [
  // ---- T4
  { t: "T4", ref: "T4-02", step: 3, text: "R1 critical alert at block 45,201,812 gives exactly one decision DEC-fuji-45201812-1",
    check: () => { const d = S.decision; return d && [d.id === DEC_ID, `id=${d.id}, severity=${d.severity}`]; } },
  { t: "T4", ref: "2.8", step: 3, text: "Critical row of the playbook: NOTIFY → PAUSE → 4 × WITHDRAW (auto) → OPEN_INCIDENT → UNPAUSE (human)",
    check: () => { const d = S.decision; if (!d) return null; const got = d.actions.map((a) => [a.type, a.mode]);
      return [JSON.stringify(got) === JSON.stringify(EXPECTED_ACTIONS), `${d.actions.length} actions: ${d.actions.map((a) => a.type.split("_")[0]).join(", ")}`]; } },
  { t: "T4", ref: "T4-02", step: 3, text: "4 withdrawals in order: A USDC 400,000 · A WETH 150 · B USDC 300,000 · B WETH 100, all executed",
    check: () => { const d = S.decision; if (!d) return null; const ew = d.actions.filter((a) => a.type === "EMERGENCY_WITHDRAW");
      const ok = ew.length === 4 && ew.every((a, i) => a.params.deployment_id === EXPECTED_EW[i][0] && a.params.asset === EXPECTED_EW[i][1] && a.amount === EXPECTED_EW[i][2] && a.status === "executed");
      return [ok, ew.map((a) => `${a.params.asset} ${units(a.amount, DECIMALS[a.params.asset])} ${a.status}`).join(" · ")]; } },
  { t: "T4", ref: "T4-09", step: 3, text: "Exposure counted once: 1,325,000 $, matrix cell critical|exposure>=1k|exit_possible",
    check: () => { const d = S.decision; return d && [d.exposure_usd === 1325000 && d.matrix_cell === "critical|exposure>=1k|exit_possible", `${usd(d.exposure_usd)} · ${d.matrix_cell}`]; } },
  { t: "T4", ref: "dry-run", step: 3, text: "Dry-run executor: no real transaction is sent (hashes 0xdry…)",
    check: () => { const d = S.decision; if (!d) return null; const tx = d.actions.map((a) => a.tx_hash).filter(Boolean);
      return [tx.length > 0 && tx.every((h) => h.startsWith("0xdry")), `${tx.length} simulated tx, e.g. ${short(tx[0])}`]; } },
  { t: "T4", ref: "notify", step: 3, text: "Humans notified without blocking the withdrawals",
    check: () => { const a = S.decision && S.decision.actions[0]; return a && [a.type === "NOTIFY" && a.status === "executed", `NOTIFY ${a.status} · ${a.note || ""}`]; } },
  { t: "T4", ref: "3.4", step: 3, text: "Discord message built from the decision (red embed, 8 actions, evidence hash, no @mentions)",
    check: () => { const p = S.discord && S.discord.payload; if (!p) return null; const e = p.embeds[0];
      return [e.color === 0xE53935 && e.fields.some((f) => f.name === "Actions") && p.allowed_mentions.parse.length === 0,
        S.discord.webhook_configured ? "posted to the Discord webhook" : "built (no webhook configured)"]; } },
  { t: "T4", ref: "T4-17", step: 5, text: "The same alert replayed creates no second decision and no second incident",
    check: () => { const r = S.flags.replay; return r && [r.decisions === 1 && r.incidents === 1, `after replay: ${r.decisions} decision, ${r.incidents} incident`]; } },
  { t: "T4", ref: "evidence", step: 5, text: "Evidence file written, fingerprint (record_hash) computed and anchored",
    check: () => { const v = S.verify; return v && [!!v.stored_hash && v.anchored, `record_hash ${short(v.stored_hash)} · anchored=${v.anchored}`]; } },
  { t: "T4", ref: "verify", step: 5, text: "verify replays the decision from its evidence: MATCH",
    check: () => S.flags.firstMatch ? [true, "POST /api/verify → match=true"] : null },
  { t: "T4", ref: "T4-22", step: 5, text: "Tampered evidence gives MISMATCH naming record_hash and action[2]",
    check: () => { const d = S.flags.tamperDiffs; return d && [d.some((x) => x.startsWith("record_hash")) && d.some((x) => x.startsWith("action[2]")), `${d.length} differences found`]; } },
  { t: "T4", ref: "restore", step: 5, text: "restore puts the original back: MATCH again",
    check: () => S.flags.restoredMatch ? [true, "POST /api/verify → match=true after restore"] : null },
  { t: "T4", ref: "T4-24", step: 6, text: "Human approval of UNPAUSE_DEPOSITS: 200, then 409 when replayed",
    check: () => { const c = S.flags.approveCodes; return c.length ? [c[0] === 200 && c.includes(409), `HTTP ${c.join(" then ")}`] : null; } },
  { t: "T4", ref: "T4-25", ext: "needs T1 contracts + T2 seed (anvil)", text: "Real withdrawals and on-chain anchoring on a local chain" },
  // ---- T5
  { t: "T5", ref: "T5-17", step: 7, text: "One incident opened from the decision's OPEN_INCIDENT: INC-20261011-001",
    check: () => { const i = S.incident; return i && [i.id === "INC-20261011-001" && i.decision_ids.includes(DEC_ID), `${i.id} · decisions ${i.decision_ids.join(", ")}`]; } },
  { t: "T5", ref: "T5-17", step: 7, text: "Money: saved 1,325,000 $ · exposure 1,325,000 $ · still at risk 0 $ (integer maths)",
    check: () => { const i = S.incident; return i && [i.saved_usd === 1325000 && i.exposure_usd === 1325000 && i.at_risk_usd === 0, `saved ${usd(i.saved_usd)} · at risk ${usd(i.at_risk_usd)}`]; } },
  { t: "T5", ref: "T5-17", step: 7, text: "Contained after 10 calm snapshots (block 45,201,832 = 08:01:04 UTC)",
    check: () => { const i = S.incident; return i && [i.status === "contained" && (i.contained_at || "").startsWith("2026-10-11T08:01:04"), `status=${i.status} · contained_at=${i.contained_at || "—"}`]; } },
  { t: "T5", ref: "Art. 8-9", step: 7, text: "DORA proposal: major incident via Art. 8(1)(b), thresholds 9(1) and 9(4)",
    check: () => { const d = S.incident && S.incident.dora; if (!d) return null; const t = d.thresholds_met.map((x) => x.split(" ")[0]);
      return [d.is_major && t.join() === "9(1),9(4)", `is_major=${d.is_major} · ${t.join(", ")}`]; } },
  { t: "T5", ref: "2025/301", step: 7, text: "Deadlines: initial = min(classification + 4 h, detection + 24 h), +72 h, +30 days",
    check: () => { const d = S.incident && S.incident.dora; if (!d || !d.deadlines) return null; const dl = d.deadlines;
      const init = Date.parse(dl.initial_notification_due), want = Math.min(Date.parse(d.classified_at) + 4 * H, Date.parse(d.aware_at) + 24 * H);
      const ok = init === want && Date.parse(dl.intermediate_report_due) - init === 72 * H && Date.parse(dl.final_report_due) - Date.parse(dl.intermediate_report_due) === 720 * H;
      return [ok, `initial ${utc(dl.initial_notification_due)}`]; } },
  { t: "T5", ref: "T5-12", step: 7, text: "Draft report: the 8 sections in order, 1,325,000 USD, no None / nan / TODO",
    check: () => { const r = S.report; if (!r) return null; const titles = r.split("\n").filter((l) => l.startsWith("## ")).map((l) => l.slice(3));
      const inOrder = REPORT_TITLES.every((t, i) => (titles[i] || "").startsWith(t));
      return [inOrder && r.includes("1,325,000 USD") && !/\bNone\b|\bnan\b|TODO/.test(r), `${titles.length} sections · ${r.length} chars`]; } },
  { t: "T5", ref: "T5-20", step: 7, text: "Timeline rebuilt from alerts, decisions, actions, humans and DORA",
    check: () => { const i = S.incident; if (!i) return null; const k = new Set(i.timeline.map((e) => e.kind));
      return [["alert", "decision", "action", "human", "dora"].every((x) => k.has(x)), `${i.timeline.length} events · ${[...k].join(", ")}`]; } },
  { t: "T5", ref: "T5-13", step: 7, text: "AI (Bedrock) switched off: deterministic template, nothing blocks",
    check: () => { const d = S.incident && S.incident.dora; return d && [Array.isArray(d.ai_drafted_sections) && d.ai_drafted_sections.length === 0, `ai_drafted_sections=[${d.ai_drafted_sections.join(", ")}]`]; } },
  { t: "T5", ref: "T5-26", step: 7, text: "Only a human submits: 200, then 409 already submitted",
    check: () => { const c = S.flags.submitCodes; return c.length ? [c[0] === 200 && c.includes(409), `HTTP ${c.join(" then ")}`] : null; } },
  { t: "T5", ref: "e-mail", step: 7, text: "DORA draft PDF e-mailed to a reviewer (allow-listed address, not a submission)",
    check: () => (S.mail && S.mail.ok ? [true, S.mail.text] : null) },
  { t: "T5", ref: "T5-27", step: 8, text: "Third-party register with live status (rsETH bridge down)",
    check: () => { const r = S.deps.find((d) => d.id === "rseth"); return S.deps.length ? [S.deps.length === 9 && r && r.status === "down", `${S.deps.length} providers · rseth=${r ? r.status : "?"}`] : null; } },
  { t: "T5", ref: "E2E", ext: "needs T1 + T2 + T3 (make attack SEED=42 on anvil)", text: "Same flow fed by the real monitoring engine on a local chain" },
];

function renderPlan() {
  const groups = { T4: "T4 · Response & evidence", T5: "T5 · Incident & DORA" };
  let html = "";
  for (const t of ["T4", "T5"]) {
    const items = PLAN.filter((p) => p.t === t);
    const done = items.filter((p) => !p.ext && evalCheck(p)[0] === true).length;
    const total = items.filter((p) => !p.ext).length;
    html += `<h3><span>${groups[t]}</span><span>${done}/${total}</span></h3>`;
    for (const p of items) {
      if (p.ext) { html += `<div class="req ext"><div class="st">⏳</div><div><div class="tx"><span class="ref">${p.ref}</span>${esc(p.text)}</div><div class="ev">${esc(p.ext)}</div></div></div>`; continue; }
      const [ok, ev] = evalCheck(p);
      const st = ok === true ? "✅" : ok === false ? "❌" : "⚪";
      html += `<div class="req ${ok === true ? "done" : ""}"><div class="st">${st}</div><div><div class="tx"><span class="ref">${p.ref}</span>${esc(p.text)}</div>
        <div class="ev">${ok == null ? `shown at step ${p.step}` : esc(ev)}</div></div></div>`;
    }
  }
  $("plan").innerHTML = html;
}
function evalCheck(p) { try { const r = p.check(); return r ? [!!r[0], r[1]] : [null, ""]; } catch { return [null, ""]; } }

// ---------------------------------------------------------------- scoreboard
function renderBoard() {
  const w = S.world;
  $("block").textContent = w && w.block ? num(w.block) : "—";
  $("clock").textContent = w && w.block_time ? utc(w.block_time) : "—";
  if (!w || !w.ours) return;
  $("ours-safe").textContent = usd(w.ours.safe_usd);
  $("ours-stuck").textContent = usd(w.ours.stuck_usd);
  $("pas-safe").textContent = usd(w.passive.safe_usd);
  $("pas-stuck").textContent = usd(w.passive.stuck_usd);
  const b = w.rseth ? w.rseth.backing_ratio_bps / 100 : 100;
  $("backing").textContent = `${b.toFixed(1)} %`;
  $("backing").className = `num ${b < 99 ? "bad" : ""}`;
  $("backing-bar").style.width = `${Math.min(100, b)}%`;
  $("backing-bar").style.background = b < 99 ? "var(--bad)" : "var(--ok)";
}

// ---------------------------------------------------------------- shared visual blocks
function marketsBlock() {
  const w = S.world; if (!w || !w.markets) return "";
  const lend = w.markets.filter((m) => m.borrowable);
  const byDep = {};
  lend.forEach((m) => (byDep[m.deployment_id] = byDep[m.deployment_id] || []).push(m));
  const frozen = w.markets.filter((m) => m.frozen || m.paused);
  return `<div class="markets">${Object.entries(byDep).map(([dep, ms]) => `
    <div class="market"><h4>${esc(MARKET[dep] || dep)} ${frozen.some((f) => f.deployment_id === dep) ? badge("frozen", "bad") : ""}</h4>
      ${ms.map((m) => { const pct = m.supplied ? (m.available / m.supplied) * 100 : 0;
        const col = pct < 2 ? "var(--bad)" : pct < 20 ? "var(--warn)" : "var(--ok)";
        return `<div style="margin:.5rem 0"><b>${esc(m.asset)}</b> — cash in the till: <b>${num(m.available)}</b> of ${num(m.supplied)} deposited
          <div class="bar" role="progressbar" aria-valuenow="${pct.toFixed(0)}" aria-valuemin="0" aria-valuemax="100"><div style="width:${pct}%;background:${col}"></div></div>
          <span class="note">${pct < 2 ? "EMPTY: depositors can no longer withdraw" : `${pct.toFixed(0)} % available · ${(m.utilization_bps / 100).toFixed(0)} % lent out`}</span></div>`; }).join("")}
    </div>`).join("")}</div>`;
}

function positionsList(list) {
  if (!list.length) return `<p class="note">No money left in the markets.</p>`;
  return `<table><thead><tr><th>Where</th><th>Asset</th><th>Amount</th><th>Value</th><th>Can leave now</th></tr></thead><tbody>${list.map((p) =>
    `<tr><td>${esc(MARKET[p.deployment_id] || p.deployment_id)}</td><td>${esc(p.asset)}</td><td>${num(p.amount)}</td><td>${usd(p.value_usd)}</td>
     <td>${p.withdrawable_usd >= p.value_usd ? badge("100 %", "ok") : badge(`${((p.withdrawable_usd / p.value_usd) * 100).toFixed(0)} %`, "bad")}</td></tr>`).join("")}</tbody></table>`;
}

function nav(prev, next, nextLabel = "Next step →") {
  return `<div class="nav">${prev ? `<button class="btn ghost" data-go="${S.step - 1}">← Back</button>` : "<span></span>"}
    ${next ? `<button class="btn" data-go="${S.step + 1}">${nextLabel}</button>` : "<span></span>"}</div>`;
}

// ---------------------------------------------------------------- steps
const STEPS = [
  { title: "Why this matters", tag: "", render: () => `
    <div class="kicker">Context</div>
    <h2>Companies now park cash in crypto “savings accounts”</h2>
    <p class="lead">Fintechs, crypto funds and company treasuries deposit dollars (as ${term("stablecoins", "Digital dollars: 1 USDC ≈ 1 US dollar.")})
      in automated ${term("lending markets", "Programs on a blockchain that work like a bank: you deposit, others borrow against a guarantee (collateral), you earn interest.")}.
      It works like a savings account, except nobody is on call at night when something goes wrong.</p>
    <div class="story">
      <div class="tile"><div class="emoji">🏦</div><h4>Our client</h4><p>A treasury of <b>1,325,000 $</b> spread over two lending markets, kept in a shared company vault.</p></div>
      <div class="tile"><div class="emoji">💥</div><h4>What really happened (April 2026)</h4><p>An attacker created counterfeit <b>rsETH</b> tokens, used them as a fake guarantee, and borrowed all the real money. Depositors rushed to withdraw; the last ones were stuck.</p></div>
      <div class="tile"><div class="emoji">⏱️</div><h4>The window</h4><p>The fastest people had between 20 minutes and an hour to get out. A human checking dashboards would likely miss it.</p></div>
    </div>
    <h3>What the platform does</h3>
    <div class="story">
      <div class="tile"><h4>1 · Detect <span class="tag">T3</span></h4><p>Watches the markets every block. Raises an alert in plain English. <i>Simulated in this demo (another team's part).</i></p></div>
      <div class="tile"><h4>2 · Respond &amp; prove <span class="tag">T4</span></h4><p>Applies a fixed rulebook: locks deposits, pulls the money home, notifies humans, and seals a tamper-proof record of the decision.</p></div>
      <div class="tile"><h4>3 · Report <span class="tag">T5</span></h4><p>Opens an incident, computes what was saved, and pre-fills the EU regulatory report (DORA) that a human then submits.</p></div>
    </div>
    <div class="analogy">Think of it as a circuit breaker for the treasury: it cannot spend money or send it anywhere, it can only cut the power and bring the money back home — and it keeps the receipts.</div>
    <div class="actions"><button class="btn" id="go-start">Start: show a normal day →</button></div>` ,
    bind: () => $("go-start").onclick = async () => { await doReset(); go(1); } },

  { title: "A normal day", tag: "", render: () => `
    <div class="kicker">Step 1</div>
    <h2>Everything is calm</h2>
    <p class="lead">The treasury has money in two lending markets. Each market keeps some cash in the till so depositors can withdraw anytime.
      The rsETH token is fully backed (100 %).</p>
    <div class="actions"><button class="btn ghost" id="b-reset">↺ Reset to a normal day</button></div>
    <h3>Where our money is</h3>${positionsList(S.world && S.world.ours ? S.world.ours.positions : [])}
    <h3>The markets</h3>${marketsBlock()}
    ${nav(true, true, "Next: the attack →")}`,
    bind: () => $("b-reset").onclick = doReset },

  { title: "The attack starts", tag: "T3", render: () => {
    const done = !!S.decision;
    return `
    <div class="kicker">Step 2 · the trigger</div>
    <h2>Counterfeit tokens appear</h2>
    <p class="lead">At block 45,201,812 an attacker prints <b>5,000 rsETH out of thin air</b> through a flaw in the token's bridge.
      Suddenly only 1,200 of the 6,200 tokens are backed by real ETH: <b>19.4 %</b>. Both of our markets accept rsETH as a guarantee, so <b>all our money is exposed</b>.</p>
    <div class="analogy">Like someone printing fake banknotes and using them as a deposit to take out real loans from your bank.</div>
    <div class="actions"><button class="btn red" id="b-attack" ${done ? "disabled" : ""}>${done ? "Attack launched" : "⚡ Launch the attack"}</button></div>
    ${done ? `<div class="alert-card">${badge("critical")} <span class="note">alert raised by the monitoring engine (T3 — simulated here)</span>
      <h3>rsETH backing below threshold</h3>
      <p>“rsETH backing fell to 19.4 % (1,200 WETH backing for 6,200 rsETH supply).”</p>
      <p class="note">Rule R1 · threshold 99 % · exposure ${usd(S.decision.exposure_usd)} · block 45,201,812</p></div>
      <p>The alert is handed to <b>T4</b>, which decides what to do. Next step →</p>` : `<p class="note">In production the monitoring engine (T3) raises this alert by itself. Here we inject the exact same alert.</p>`}
    ${nav(true, done, "Next: our response →")}`; },
    bind: () => { const b = $("b-attack"); if (b) b.onclick = doAttack; } },

  { title: "Automatic response", tag: "T4", render: () => {
    const d = S.decision;
    if (!d) return `<div class="kicker">Step 3</div><h2>Automatic response</h2><p class="lead">Launch the attack first (step 2).</p>${nav(true, false)}`;
    const ew = d.actions.filter((a) => a.type === "EMERGENCY_WITHDRAW" && a.status === "executed");
    return `
    <div class="kicker">Step 3 · T4 decides and acts</div>
    <h2>Within the same block: deposits locked, money brought home</h2>
    <p class="lead">T4 looks the alert up in a fixed ${term("rulebook", "backend/config/playbook.yaml: severity → list of actions. No AI decides anything here: same input, same decision, every time.")}:
      <b>critical + more than 1,000 $ exposed + money can still leave</b>. That row says exactly what to do, in this order:</p>
    <ul class="timeline-actions">${d.actions.map((a, i) => { const t = actionText(a);
      return `<li style="animation-delay:${i * 0.25}s"><div class="ico">${t.ico}</div><div><div class="what">${esc(t.what)}</div><div class="why">${esc(t.why)}</div></div>
        <div class="meta">${badge(a.mode === "auto" ? "automatic" : "human", a.mode)}<br>${badge(a.status.replace("_", " "), a.status)}${a.tx_hash ? `<br><span class="mono">${esc(short(a.tx_hash))}</span>` : ""}</div></li>`; }).join("")}</ul>
    <div class="vs"><div class="tile good"><h4>Brought home</h4><p class="num">${usd(ew.length ? d.withdrawable_usd : 0)}</p><p>${ew.length} withdrawals, 100 % of what we had.</p></div>
      <div class="tile"><h4>Decision record</h4><p class="mono">${esc(d.id)}</p><p>${esc(d.rationale)}</p></div></div>
    <div class="tile" style="margin:1rem 0"><h4>📣 Message sent to the team's Discord</h4>
      <p>${S.discord && S.discord.webhook_configured ? "The NOTIFY action posted this alert to the <b>#alerts</b> channel (check Discord)." : "No Discord webhook configured (ALERT_WEBHOOK_URL in .env): the alert is only logged."}</p>
      <details><summary>JSON sent to Discord</summary><pre class="mono" style="white-space:pre-wrap;max-height:22rem;overflow:auto">${esc(S.discord ? JSON.stringify(S.discord.payload, null, 2) : "…")}</pre></details></div>
    <details><summary>The full rulebook (why this row)</summary>
      <table><thead><tr><th>Severity</th><th>Exposure</th><th>Actions</th></tr></thead><tbody>
      <tr style="background:#2a1313"><td>${badge("critical")}</td><td>≥ 1,000 $</td><td>Notify → pause deposits → withdraw each exposed position (automatic) → open incident → re-open deposits (human)</td></tr>
      <tr><td>${badge("high")}</td><td>≥ 1,000 $</td><td>Notify → pause deposits → withdraw each position <b>only after human approval</b> → open incident</td></tr>
      <tr><td>${badge("warning", "warn")}</td><td>any</td><td>Notify only</td></tr>
      <tr><td>${badge("info")}</td><td>—</td><td>Nothing</td></tr>
      <tr><td>any</td><td>&lt; 1,000 $</td><td>Notify if severity ≥ high, otherwise nothing</td></tr></tbody></table>
      <p class="note">Matrix cell used: <span class="mono">${esc(d.matrix_cell)}</span></p></details>
    <details><summary>Technical details</summary><table><thead><tr><th>#</th><th>Type</th><th>Params</th><th>Amount (base units)</th><th>Note</th></tr></thead><tbody>
      ${d.actions.map((a, i) => `<tr><td>${i}</td><td>${esc(a.type)}</td><td class="mono">${esc(JSON.stringify(a.params))}</td><td class="mono">${esc(a.amount ?? "—")}</td><td>${esc(a.note ?? "")}</td></tr>`).join("")}</tbody></table>
      <p class="mono note">inputs_hash ${esc(d.inputs_hash)}<br>record_hash ${esc(d.record_hash)}<br>playbook_version ${esc(d.playbook_version)}</p></details>
    ${nav(true, true, "Next: meanwhile in the market →")}`; } },

  { title: "Meanwhile in the market", tag: "", render: () => {
    const w = S.world || {}; const end = w.block && w.last_block && w.block >= w.last_block;
    return `
    <div class="kicker">Step 4 · the next two minutes</div>
    <h2>The attacker drains the market. Who is left holding the bag?</h2>
    <p class="lead">With the fake guarantee, the attacker borrows the real WETH, chunk by chunk. Other depositors panic and withdraw.
      The till of market A empties. Then the market's own operator freezes it — too late for passive depositors.</p>
    <div class="actions"><button class="btn" id="b-play" ${S.playing || end || !S.decision ? "disabled" : ""}>${S.playing ? "Playing…" : end ? "Played to the end" : "▶ Play the next 2 minutes"}</button></div>
    ${marketsBlock()}
    <div class="vs">
      <div class="tile good"><h4>✅ Our treasury</h4><p class="num">${usd(w.ours && w.ours.safe_usd)}</p><p>safe in our vault · ${usd(w.ours && w.ours.stuck_usd)} stuck</p></div>
      <div class="tile badb"><h4>❌ The same treasury without the platform</h4><p class="num bad">${usd(w.passive && w.passive.stuck_usd)}</p><p>stuck in an empty market · ${usd(w.passive && w.passive.safe_usd)} could still leave</p>
        ${positionsList(w.passive ? w.passive.positions : [])}</div>
    </div>
    <p class="note">Same market data on both sides; the only difference is whether the circuit breaker acted at block 45,201,812.</p>
    ${nav(true, true, "Next: prove it →")}`; },
    bind: () => { const b = $("b-play"); if (b) b.onclick = doPlay; } },

  { title: "Prove it", tag: "T4", render: () => {
    const v = S.verify;
    return `
    <div class="kicker">Step 5 · T4 evidence</div>
    <h2>Anyone can check the decision was not changed afterwards</h2>
    <p class="lead">Every decision is saved with everything it was based on, and sealed with a ${term("fingerprint", "A hash (keccak256): a 64-character code computed from the content. Change one letter and the code changes completely.")}
      that is ${term("anchored on the blockchain", "Written into a public, append-only registry (EvidenceRegistry contract). In this demo the anchoring is simulated.")}.
      An auditor can replay the decision from scratch and compare.</p>
    <div class="analogy">Like a notary's seal: you can read the document, but if someone edits it later, the seal no longer matches.</div>
    <div class="actions">
      <button class="btn green" id="b-verify">🔍 Verify the decision</button>
      <button class="btn red" id="b-tamper">✏️ Tamper with the record</button>
      <button class="btn ghost" id="b-restore">↺ Restore the original</button>
      <button class="btn ghost" id="b-replay">🔁 Send the same alert again</button>
    </div>
    <p class="note">“Tamper” secretly edits the saved file: it changes the 3rd action from “withdraw USDC” to “withdraw DAI”, as a fraudster would.</p>
    <div id="verify-out">${v ? verifyBlock(v) : ""}</div>
    ${S.flags.replay ? `<p class="resp ok">Same alert sent again → still ${S.flags.replay.decisions} decision and ${S.flags.replay.incidents} incident: nothing is done twice.</p>` : ""}
    <p class="note">Command-line equivalent for auditors: <code>make verify ID=${DEC_ID}</code></p>
    ${nav(true, true, "Next: humans stay in control →")}`; },
    bind: () => { $("b-verify").onclick = () => doVerify("manual"); $("b-tamper").onclick = doTamper; $("b-restore").onclick = doRestore; $("b-replay").onclick = doReplay; } },

  { title: "Humans stay in control", tag: "T4", render: () => {
    const d = S.decision; const a = d && d.actions[7]; const c = S.flags.approveCodes;
    return `
    <div class="kicker">Step 6 · human in the loop</div>
    <h2>Tightening is automatic. Loosening needs a person.</h2>
    <p class="lead">The platform's key can only <b>lock deposits</b> and <b>bring money home</b>. Re-opening deposits is a business decision,
      so it waits for a human signer of the company vault.</p>
    ${a ? `<div class="tile"><h4>${actionText(a).ico} Re-open deposits</h4><p>Status: ${badge(a.status.replace("_", " "), a.status)} ${a.note ? `· ${esc(a.note)}` : ""}</p></div>` : "<p>Launch the attack first.</p>"}
    <div class="actions"><button class="btn green" id="b-approve" ${a ? "" : "disabled"}>✅ Approve as “${OPERATOR}”</button></div>
    ${c.length ? `<p class="resp ${c[c.length - 1] === 200 ? "ok" : "warn"}">${c.map((x) => (x === 200 ? "HTTP 200: approved and executed" : `HTTP ${x}: already decided — an approval cannot be replayed`)).join("<br>")}</p>` : ""}
    <p class="note">Try clicking twice: the second click is refused (409). Every approval is written into the evidence file.</p>
    ${nav(true, true, "Next: the regulator →")}`; },
    bind: () => { const b = $("b-approve"); if (b) b.onclick = doApprove; } },

  { title: "Incident & regulator", tag: "T5", render: () => {
    const i = S.incident;
    if (!i) return `<div class="kicker">Step 7</div><h2>Incident & regulator</h2><p class="lead">Launch the attack first (step 2).</p>${nav(true, false)}`;
    const d = i.dora || {}; const dl = d.deadlines || {}; const c = S.flags.submitCodes;
    const plain = { "9(1)": "100 % of the treasury's clients are affected", "9(4)": "clients in 2 EU countries (FR, DE)", "9(6)": "economic loss above 100,000 €" };
    return `
    <div class="kicker">Step 7 · T5 incident & DORA</div>
    <h2>The incident file writes itself</h2>
    <p class="lead">${term("DORA", "EU regulation on the digital resilience of financial firms (Reg. (EU) 2022/2554). Major ICT incidents must be reported to the regulator within strict deadlines.")}
      requires financial firms to report major incidents within hours. T5 tracks the incident and pre-fills the report; a human reviews and submits it.</p>
    <div class="story">
      <div class="tile"><h4>Incident ${esc(i.id)}</h4><p>${badge(i.status)} ${badge(i.severity)}</p><p class="note">${i.status === "contained" ? `Contained at ${esc(utc(i.contained_at))}: 10 calm readings in a row, no position stuck.` : "Still open: play step 4 to let it calm down."}</p></div>
      <div class="tile"><h4>Saved</h4><p class="num">${usd(i.saved_usd)}</p><p>of ${usd(i.exposure_usd)} exposed</p></div>
      <div class="tile"><h4>Still at risk</h4><p class="num ${i.at_risk_usd > 0 ? "bad" : ""}">${usd(i.at_risk_usd)}</p></div>
    </div>
    <div class="cols"><div>
      <h3>Is it a “major” incident? ${d.is_major ? badge("major", "bad") : badge("not major", "ok")}</h3>
      <p>${esc(d.legal_basis || "")}</p>
      <p>In plain words: critical services were hit <b>and</b> at least two thresholds are crossed:</p>
      <ul>${(d.thresholds_met || []).map((t) => { const k = t.split(" ")[0]; return `<li><b>${esc(k)}</b> — ${esc(plain[k] || t)}</li>`; }).join("")}</ul>
      <h3>Deadlines</h3>
      <table><tbody>
        <tr><td>Initial notification</td><td class="mono">${esc(utc(dl.initial_notification_due))}</td><td>${esc(countdown(dl.initial_notification_due))}</td></tr>
        <tr><td>Intermediate report</td><td class="mono">${esc(utc(dl.intermediate_report_due))}</td><td>${esc(countdown(dl.intermediate_report_due))}</td></tr>
        <tr><td>Final report</td><td class="mono">${esc(utc(dl.final_report_due))}</td><td>${esc(countdown(dl.final_report_due))}</td></tr></tbody></table>
      <p class="note">Initial = the earlier of classification + 4 h and detection + 24 h; then + 72 h; then + 30 days (Reg. (EU) 2025/301).</p>
      <div class="actions"><button class="btn green" id="b-submit">📨 Submit to the regulator as “${OPERATOR}”</button>
        <a class="btn" style="text-decoration:none;padding:.7rem 1.1rem;border-radius:10px;color:#fff;background:linear-gradient(90deg,#4f6dff,#7c5cff)" href="/demo/api/report.pdf/${esc(i.id)}" target="_blank" rel="noreferrer">📄 Open the DORA report (PDF)</a>
        <a class="btn ghost" style="text-decoration:none;padding:.7rem 1.1rem;border:1px solid var(--line);border-radius:10px;color:var(--ink)" href="/api/incidents/${esc(i.id)}/report.md" target="_blank" rel="noreferrer">report.md</a></div>
      <div class="tile" style="margin:.8rem 0"><h4>✉️ Receive the draft by e-mail</h4>
        <p class="note">Sends the PDF to a reviewer. This is <b>not</b> the submission to the regulator.</p>
        <div class="actions" style="margin:.4rem 0"><label for="mail-to" class="note">Your e-mail</label>
          <input id="mail-to" type="email" autocomplete="email" placeholder="you@example.com" value="${esc(S.mailTo || "")}"
            style="flex:1;min-width:14rem;padding:.6rem .7rem;border-radius:8px;border:1px solid var(--line);background:#0e1628;color:var(--ink);font:inherit">
          <button class="btn" id="b-mail" ${S.mailBusy ? "disabled" : ""}>${S.mailBusy ? "Sending…" : "Email me the DORA report"}</button></div>
        ${S.mail ? `<p class="resp ${S.mail.ok ? "ok" : S.mail.status === 429 ? "warn" : "err"}">${esc(S.mail.text)}</p>` : ""}
        ${S.mailConfigured === false ? `<p class="note">E-mail is not configured yet (SMTP_USER, SMTP_PASSWORD, MAIL_ALLOWED_RECIPIENTS in .env).</p>` : ""}</div>
      ${d.submitted ? `<p class="resp ok">Submitted by ${esc(d.submitted_by)} at ${esc(utc(d.submitted_at))}</p>` : `<p class="note">The platform only proposes. Nothing is sent until a person clicks.</p>`}
      ${c.length ? `<p class="resp ${c[c.length - 1] === 200 ? "ok" : "warn"}">${c.map((x) => (x === 200 ? "HTTP 200: submitted" : `HTTP ${x}: already submitted, cannot be sent twice`)).join("<br>")}</p>` : ""}
      <p class="note">${(d.ai_drafted_sections || []).length ? "Some sections were drafted by AI and are flagged for review." : "AI drafting is off: the description comes from a fixed template, so the report never waits on an AI."}</p>
    </div><div>
      <h3>Pre-filled report (draft)</h3><div class="report">${md(S.report)}</div>
    </div></div>
    <details><summary>Incident timeline (${i.timeline.length} events)</summary><table><thead><tr><th>Time (UTC)</th><th>Kind</th><th>Event</th></tr></thead><tbody>
      ${[...i.timeline].sort((a, b) => (a.at < b.at ? -1 : 1)).map((e) => `<tr><td class="mono">${esc(utc(e.at))}</td><td>${badge(e.kind, "info")}</td><td>${esc(e.text)}</td></tr>`).join("")}</tbody></table></details>
    ${nav(true, true, "Next: third parties & summary →")}`; },
    bind: () => { const b = $("b-submit"); if (b) b.onclick = doSubmit;
      const m = $("b-mail"); if (m) m.onclick = doMail;
      const i = $("mail-to"); if (i) i.oninput = (e) => { S.mailTo = e.target.value; }; } },

  { title: "Third parties & summary", tag: "T5", render: () => {
    const order = { critical: 0, important: 1, standard: 2 };
    const done = PLAN.filter((p) => !p.ext && evalCheck(p)[0] === true).length, total = PLAN.filter((p) => !p.ext).length;
    return `
    <div class="kicker">Step 8 · T5 register & recap</div>
    <h2>Who we depend on, and how they are doing</h2>
    <p class="lead">DORA also asks firms to keep a register of their technology suppliers. T5 keeps it live: right now the rsETH bridge is <b>down</b> (its token lost its backing).</p>
    <table><thead><tr><th>Supplier</th><th>Type</th><th>Criticality</th><th>Backup plan</th><th>Status</th></tr></thead><tbody>
      ${[...S.deps].sort((a, b) => (order[a.criticality] ?? 9) - (order[b.criticality] ?? 9)).map((d) => `<tr><td><b>${esc(d.name)}</b></td><td>${esc(d.kind)}</td>
        <td>${badge(d.criticality, d.criticality === "critical" ? "bad" : d.criticality === "important" ? "warn" : "info")}</td><td>${esc(d.fallback ?? "—")}</td><td>${badge(d.status)}</td></tr>`).join("")}</tbody></table>
    <h3>Recap</h3>
    <div class="story">
      <div class="tile"><h4>🛡️ Money</h4><p><b>${usd(S.incident ? S.incident.saved_usd : 0)}</b> brought home, versus <b>${usd(S.world && S.world.passive ? S.world.passive.stuck_usd : 0)}</b> stuck for a passive treasury.</p></div>
      <div class="tile"><h4>🔏 Proof</h4><p>Every decision sealed and replayable; tampering is detected.</p></div>
      <div class="tile"><h4>📋 Compliance</h4><p>Incident classified, deadlines computed, report pre-filled; a human submits.</p></div>
      <div class="tile"><h4>✅ Plan coverage</h4><p><b>${done} / ${total}</b> requirements shown live in this demo. The 2 remaining ones need the other teams' contracts and monitoring.</p></div>
    </div>
    <div class="actions"><button class="btn ghost" id="b-again">↺ Run the demo again</button></div>
    ${nav(true, false)}`; },
    bind: () => $("b-again").onclick = async () => { await doReset(); go(0); } },
];

function countdown(iso) {
  if (!iso) return "—";
  const ms = Date.parse(iso) - Date.now(), abs = Math.abs(ms), h = Math.floor(abs / H), m = Math.floor((abs % H) / 6e4);
  const txt = h >= 48 ? `${Math.floor(h / 24)} d ${h % 24} h` : `${h} h ${String(m).padStart(2, "0")} min`;
  return ms >= 0 ? `${txt} left` : `overdue by ${txt}`;
}

function verifyBlock(v) {
  return `<div style="margin:1rem 0"><span class="big-word ${v.match ? "ok" : "bad"}">${v.match ? "MATCH" : "MISMATCH"}</span></div>
    <p>${v.match ? "The record replays to the very same decision and fingerprint. Nothing was changed." : "The record does not match its seal any more. Here is exactly what differs:"}</p>
    ${v.diffs.length ? `<ul class="diffs">${v.diffs.map((x) => `<li class="mono">${esc(x)}</li>`).join("")}</ul>` : ""}
    <p class="note mono">stored ${esc(short(v.stored_hash))} · recomputed ${esc(short(v.recomputed_hash))} · anchored ${v.anchored ? "yes" : "no"} (block ${esc(v.anchor_block ?? "—")})</p>`;
}

// Tiny safe markdown renderer (headings, tables, lists, bold, italics, code). Escapes everything first.
function md(src) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/_\((.+?)\)_/g, "<i>($1)</i>").replace(/`(.+?)`/g, "<code>$1</code>");
  const out = []; let list = false, table = null;
  const closeList = () => { if (list) { out.push("</ul>"); list = false; } };
  const closeTable = () => { if (table) { out.push(`<table>${table.join("")}</table>`); table = null; } };
  for (const line of String(src || "").split("\n")) {
    const t = line.trim();
    if (t.startsWith("|")) {
      if (/^\|[\s:|-]+\|$/.test(t)) continue;
      closeList();
      const cells = t.slice(1, -1).split("|").map((c) => c.trim()), tag = table ? "td" : "th";
      table = table || []; table.push(`<tr>${cells.map((c) => `<${tag}>${inline(c)}</${tag}>`).join("")}</tr>`); continue;
    }
    closeTable();
    const h = t.match(/^(#{1,4})\s+(.*)$/);
    if (h) { closeList(); out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); continue; }
    if (/^[-*]\s+/.test(t)) { if (!list) { out.push("<ul>"); list = true; } out.push(`<li>${inline(t.replace(/^[-*]\s+/, ""))}</li>`); continue; }
    closeList();
    if (t) out.push(`<p>${inline(t)}</p>`);
  }
  closeList(); closeTable();
  return out.join("");
}

// ---------------------------------------------------------------- actions
async function doReset() {
  await call("POST", "/demo/api/reset"); resetFlags(); S.report = ""; S.incident = null; S.decision = null;
  await refresh(true); toast("Reset: a normal day, 1,325,000 $ invested.");
}
async function doAttack() {
  const r = await call("POST", "/demo/api/trigger-r1");
  toast(r.ok ? `Alert raised → ${r.data.decision_id} and ${r.data.incident_id}` : `HTTP ${r.status}: ${r.data.detail}`);
  await refresh(true);
}
async function doPlay() {
  S.playing = true; draw();
  while (true) {
    const r = await call("POST", "/demo/api/advance?n=1");
    if (!r.ok || !r.data.added) break;
    await refresh(true); await sleep(250);
  }
  S.playing = false; await refresh(true);
}
async function doVerify(source) {
  const r = await call("POST", `/api/verify/${DEC_ID}`);
  if (!r.ok) { toast(`HTTP ${r.status}: ${r.data.detail}`); return null; }
  S.verify = r.data;
  if (r.data.match && source === "manual") S.flags.firstMatch = true;
  if (!r.data.match && source === "tamper") S.flags.tamperDiffs = r.data.diffs;
  if (r.data.match && source === "restore") S.flags.restoredMatch = true;
  draw(); return r.data;
}
async function doTamper() {
  const r = await call("POST", `/demo/api/tamper/${DEC_ID}`);
  toast(r.data.output || `HTTP ${r.status}`); await doVerify("tamper");
}
async function doRestore() {
  const r = await call("POST", `/demo/api/restore/${DEC_ID}`);
  toast(r.data.output || `HTTP ${r.status}`); await doVerify("restore");
}
async function doReplay() {
  const r = await call("POST", "/demo/api/replay-r1");
  if (r.ok) S.flags.replay = r.data; else toast(`HTTP ${r.status}: ${r.data.detail}`);
  await refresh(true);
}
async function doApprove() {
  const r = await call("POST", `/api/decisions/${DEC_ID}/approve`, { action_index: 7, approver: OPERATOR, approve: true });
  S.flags.approveCodes.push(r.status); toast(r.ok ? "Deposits re-opened by a human." : `HTTP ${r.status}: ${r.data.detail}`);
  await refresh(true);
}
async function doMail() {
  if (!S.incident) return;
  S.mailTo = ($("mail-to") || {}).value || S.mailTo || "";
  S.mailBusy = true; draw(true);
  const r = await call("POST", `/demo/api/email-report/${S.incident.id}`, { email: S.mailTo });
  S.mailBusy = false;
  S.mail = { ok: r.ok, status: r.status, text: r.ok ? `HTTP 200: sent to ${r.data.sent_to} (check your inbox and spam folder)` : `HTTP ${r.status}: ${r.data.detail ?? r.data}` };
  toast(S.mail.text); draw(true);
}
async function doSubmit() {
  if (!S.incident) return;
  const r = await call("POST", `/api/incidents/${S.incident.id}/submit`, { submitted_by: OPERATOR });
  S.flags.submitCodes.push(r.status); toast(r.ok ? "Report submitted by a human." : `HTTP ${r.status}: ${r.data.detail}`);
  await refresh(true);
}

// ---------------------------------------------------------------- rendering & polling
function renderStepper() {
  const doneAt = [true, !!S.world, !!S.decision, !!S.decision, S.world && S.world.block >= S.world.last_block,
    S.flags.restoredMatch, S.flags.approveCodes.includes(200), S.flags.submitCodes.includes(200), false];
  $("stepper").innerHTML = STEPS.map((s, i) => `<li><button class="${i === S.step ? "active" : ""} ${doneAt[i] && i !== S.step ? "done" : ""}" data-go="${i}">
    <span class="t">${esc(s.title)}</span>${s.tag ? `<span class="tag">${s.tag}</span>` : ""}</button></li>`).join("");
}
let lastSig = "";
function draw(force) {
  renderBoard(); renderPlan(); renderStepper();
  const sig = JSON.stringify([S.step, S.world && S.world.block, S.decision, S.incident, S.verify, S.flags, S.playing, S.deps.map((d) => d.status), S.report.length]);
  if (!force && sig === lastSig) return;
  lastSig = sig;
  $("stage").innerHTML = STEPS[S.step].render();
  if (STEPS[S.step].bind) STEPS[S.step].bind();
}
function go(i) { S.step = Math.max(0, Math.min(STEPS.length - 1, i)); draw(true); window.scrollTo({ top: 0, behavior: "smooth" }); }

let busy = false;
async function refresh(force) {
  if (busy && !force) return; busy = true;
  try {
    const [w, dec, inc, deps] = await Promise.all([call("GET", "/demo/api/world"), call("GET", "/api/decisions"), call("GET", "/api/incidents"), call("GET", "/api/dependencies")]);
    if (w.ok) S.world = w.data;
    S.decision = dec.ok && dec.data.length ? dec.data[0] : null;
    S.incident = inc.ok && inc.data.length ? inc.data[0] : null;
    if (deps.ok) S.deps = deps.data;
    if (S.incident) { const r = await call("GET", `/api/incidents/${S.incident.id}/report.md`); if (r.ok) S.report = r.data; } else S.report = "";
    if (S.mailConfigured === undefined) { const m = await call("GET", "/demo/api/email-status"); if (m.ok) S.mailConfigured = m.data.configured; }
    if (S.decision && !S.discord) { const p = await call("GET", `/demo/api/discord-preview/${DEC_ID}`); if (p.ok) S.discord = p.data; }
    if (!S.decision) S.discord = null;
    if (S.decision && !S.verify) { const v = await call("POST", `/api/verify/${DEC_ID}`); if (v.ok) S.verify = v.data; }
    draw();
  } catch (e) { toast(`Backend unreachable: ${e}`); } finally { busy = false; }
}

document.addEventListener("click", (e) => { const b = e.target.closest("[data-go]"); if (b) go(Number(b.dataset.go)); });
document.addEventListener("keydown", (e) => { if (e.target.tagName === "INPUT") return; if (e.key === "ArrowRight") go(S.step + 1); if (e.key === "ArrowLeft") go(S.step - 1); });

(async () => { await call("POST", "/demo/api/reset"); await refresh(true); })();
setInterval(() => { if (!S.playing) refresh(); }, 2000);
