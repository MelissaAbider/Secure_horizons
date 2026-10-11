# T6 dashboard (frontend/)

Run without backend:   cp .env.example .env   (VITE_USE_FIXTURES=true)  then  make frontend
Run against backend:   VITE_USE_FIXTURES=false make frontend   (backend on :8000)
Tests:                 make test-t6   (typecheck + build + 23 vitest tests)

Notes for the team
- src/types.ts is a DRAFT. It belongs to T0: when T0's version lands, keep T0's.
- dev-fixtures/ are stand-ins. When ../fixtures/state.json exists (T0), Vite uses ../fixtures automatically.
- Production build: leave VITE_API_URL empty, calls go to relative /api (nginx, T8).
- App name is one constant: APP_NAME in src/lib/labels.ts.
