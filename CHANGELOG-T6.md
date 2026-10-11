# Dashboard (T6) changelog

## v0 — 2026-10-10 22:45 (Paris)
First complete version. 8 pages (Overview, Charts, Alerts & decisions, Incident & DORA,
Evidence, Third parties, Metrics, Demo), fixture mode, 23 tests passing, typecheck and build clean.
Stand-in types.ts and dev-fixtures until T0 delivers the real ones.

## v1 — 2026-10-10 23:00 (Paris)
Light fintech theme, inspired by the reference screenshot: off-white page, navy text, one bright
blue accent, floating pill navigation with a "Run demo" button, navy pill buttons, large rounded
white cards, Plus Jakarta Sans. Overview opens with the headline
"The agent proposes. The platform checks. The vault executes." No logic changes; 23 tests passing.

## v2 — 2026-10-10 23:05 (Paris)
Overview opens on a glossy blue $ coin (original drawing) with floating chips: deposits paused,
$ in the vault, rsETH backing. Headline shortened to "Your treasury, guarded."
Much less text: no hints under totals, market tables cut to Asset / Used / Free / State,
chart notes and page intros removed. 23 tests passing.

## v3 — 2026-10-10 23:10 (Paris)
Overview in the style of mojek.money: soft blue blobs behind the hero, headline "Treasury guarded.",
a dark app-style treasury widget (total, coloured split of vault balances, Vault / Free / At risk tiles),
and three feature cards that are one word plus one line: Detect, Respond, Prove (they mirror NIST CSF).
Market tables are folded under "Markets · Show". 23 tests passing.

## v4 — 2026-10-10 23:20 (Paris)
New direction, inspired by velmax.llc (own design, no copied code or logo): near-black page,
animated dot-matrix shield with a blue signal sweep, monospace labels with a live Paris clock,
huge gradient headline "The *alert* before the loss." (italic serif word), cyan primary button,
crisp bordered cells. One numbers strip (Risk, Treasury, In the vault, Free, At risk), then
01 Detect / 02 Respond / 03 Prove. DORA criteria and report folded behind "show +".
Fonts: Inter, Inter Tight, Instrument Serif, JetBrains Mono. 23 tests passing.

## v5 — 2026-10-10 23:50 (Paris)
New direction, inspired by exactis.pro (own design, no copied code or logo): light page, floating pill
navbar, one long scroll home page with only two subjects, the agent and the attack.
Hero: animated isometric cubes flowing to a guard line (attack cubes stop there), headline
"Your AI agent runs the treasury. *It never holds the keys.*". Sections: #agent (sealed rules +
sample agent log: executed / needs signature / blocked), #detection (rsETH backing 19.4%, chart,
alerts, vault status), #response (4 steps with a sticky isometric Markets / Guard engine / Vault
illustration, totals strip), closing "Replay the attack" panel. Other pages moved to the footer.
Agent rows are labelled as samples (agent is phase 2). 23 tests passing.

## v6 — 2026-10-11 00:20 (Paris)
Scroll story mixing all the references (own design, no copied code): the dollar amount first (fintech
screenshot), dark dot-matrix shield and serif italic (velmax), glass stat chips and bento cards
(mojek), isometric layered scene and long scroll (exactis). Motion: GSAP ScrollTrigger + Lenis
smooth scroll. Hero counts up to $1,325,000 while the shield blocks red attack sparks; manifesto
words light up as the page turns from night to day; agent asks slide sideways with verdict stamps;
the attack is one pinned scene scrubbed by the scroll (fake rsETH falls in, backing 100% → 19.4%,
bait message struck out, guard BLOCKED, money back to the vault, proof anchored); proof bento with
3D tilt and count-ups; giant words slide in the outro; magnetic CTA. Lighter on the GPU than v5
(canvas pauses off screen, no heavy blur). Animations off in tests and with "reduce motion".
23 tests passing.

## v7 — 2026-10-11 02:10 (Paris)
New page /setup ("Set up" in the menu), in a clean workspace style: greeting, "Getting started ·
N of 4 steps done" with a progress ring, and a "Your guard" card. The 4 steps follow the project brief:
1 connect the Safe (address check, network, 3 of 5 signers, read-only), 2 choose protocols (the sealed
list), 3 set the agent (guaranteed rules: 40% per protocol, 0.5% max loss, signature above $100k,
circuit breaker; plus "what you want" in free text: a line like "Never more than 30% on Aave" is
spotted as a rule and can be turned into one), 4 sign and start monitoring (R1-R5).
Alerts channels (Telegram, Slack, email), policy fingerprint (SHA-256) and policy file download.
Saved in the browser (no setup API in the MVP; agent is phase 2). 25 tests passing.

## v8 — 2026-10-11 02:40 (Paris)
Light theme by default on every page, with a sun/moon switch in the top bar for dark mode
(remembered in the browser). Colours are now CSS variables, so all pages switch at once.
Home hero is light (deep-blue amount, blue dot shield); the attack chapter and the final panel
stay dark on purpose in both themes (the "alarm" moments). Count-ups always land on the real number.
25 tests passing.
