# Dashboard

React 19, TypeScript, Vite and Tailwind. The live page is **`/setup`**:
1. connect a wallet;
2. seal the list of allowed markets;
3. allocate;
4. launch and watch the attack;
5. download the DORA draft and check the Discord summary.

| Command (repo root) | What it does |
|---|---|
| `make frontend` | dev server on http://localhost:5173; `/api` is proxied to the backend on :8000 |
| `make test-t6` | typecheck, production build, unit tests (Vitest) |

## Modes

- **Live (default).** No `frontend/.env` is needed. The app calls the backend on `http://localhost:8000` in development. Run `make live` for real data.
- **Production.** Build with `VITE_API_URL` empty: calls go to the relative `/api`, served on the same origin by the reverse proxy.
- **Fixtures.** `VITE_USE_FIXTURES=true make frontend` runs without a backend. The data comes from `../fixtures/*.json`, which is generated from `backend/models.py`. `frontend/.env.example` enables this mode.

## Code map

| Path | Role |
|---|---|
| `src/pages/Setup.tsx` | onboarding (wallet, sealed list, agent, monitoring) and the live panels |
| `src/components/SafePanel.tsx` | the connected Safe: holdings, withdrawable share, allocations |
| `src/components/LiveDemo.tsx` | attack on Fuji, detections, DORA draft, Discord status |
| `src/components/AgentAutopilot.tsx` | allocation agent: cycles, proposals, verdicts |
| `src/lib/wallet.ts` | browser wallet (EIP-1193, EIP-6963 discovery, EIP-712 signing) |
| `src/lib/safeApi.ts`, `src/api.ts` | backend clients |
| `src/types.ts` | mirror of `backend/models.py`, field by field (checked by `backend/tests/test_t0_contract.py`) |
