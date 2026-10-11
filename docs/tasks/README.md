# Task docs (light)

Short version of `TASKS.md`, split so you (and your agent) only read what you need. Same section numbers as `TASKS.md`.

| File | What is inside | Read it when |
|---|---|---|
| `context.md` | what we build, the single scenario, architecture, stack, who owns which file, collaboration rules | first, once |
| `T0.md` … `T9.md` | one task each: goal, what you build, what must work at the end, key specs, deliverables, acceptance tests, mocks | you work on or ask about that task |
| `contract-chain.md` | env variables and keys (2.1), contracts summary and initial numbers (2.2), deployments file (2.3), Python chain helpers (2.4) | contracts, scenario, anything touching the chain |
| `contract-backend.md` | data conventions (2.5), models (2.6), rules R1–R5 (2.7), response matrix (2.8), store and wiring (2.10) | backend work: monitoring, response, incidents |
| `contract-api.md` | HTTP routes and errors (2.9), make commands (2.11), contract changes (2.12), fixtures (2.13) | API, dashboard, tests, commands |
| `integration.md` | assembly order, end-to-end tests (local, Fuji, AWS), demo script, phase 2 list | merging, demo prep |

Full detail of a task (algorithms, every test, pitfalls): `TASKS.md` section 3, the line is given at the end of each `Tn.md`.

## Start a task with your agent

```
You work on task Tn. Read docs/tasks/context.md and docs/tasks/Tn.md, then the contract files listed in it.
For full detail, read the Tn sheet in TASKS.md section 3. Only edit the files Tn owns (context.md 1.5).
Write the acceptance tests first, run make test-tn before each commit, and put contract change requests
in docs/contract-requests.md.
```
