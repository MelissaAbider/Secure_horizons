# Documentation

## Product: what we build, and what holds

| Document | Purpose |
|---|---|
| [`product/STATUS.md`](product/STATUS.md) | **Current status.** Task table, validated Fuji runs, session log. If a chat disagrees with this file, the file wins. |
| [`product/CONTEXT.md`](product/CONTEXT.md) | Project context: the problem, the users, the story. English working copy of the brief. |
| [`product/SCOPE.md`](product/SCOPE.md) | What the demo must show, and what waits. |
| [`product/INVARIANTS.md`](product/INVARIANTS.md) | Security and product invariants. Every change must keep them. |
| [`product/THRESHOLDS.md`](product/THRESHOLDS.md) | Detection rules R1–R5 (version 4): semantics, thresholds, evidence limits. |
| [`product/DECISIONS.md`](product/DECISIONS.md) | Decisions taken by the team, with date and reason. |
| [`product/SOURCES.md`](product/SOURCES.md) | Sources for every incident fact used in code or claims. |
| [`brief/projet-en-bref.pdf`](brief/projet-en-bref.pdf) | Original project brief (French). |

## Plan and interface contract

| Document | Purpose |
|---|---|
| [`../TASKS.md`](../TASKS.md) | Full MVP plan: tasks T0–T10, the frozen interface contract (models, API, make targets), acceptance tests. |
| [`tasks/README.md`](tasks/README.md) | Short version of the plan, one file per task (`T0.md` … `T10.md`) and per shared contract (`contract-*.md`, `integration.md`). |
| [`contract-requests.md`](contract-requests.md) | Requested changes to the shared contract, with status. |

## Feature guides

| Document | Purpose |
|---|---|
| [`tasks/T10.md`](tasks/T10.md) | Sealed list: Safe, teller-window module, Merkle root, and the dashboard flow (connect, seal, allocate, disconnect). |
| [`agent.md`](agent.md) | Allocation agent: MCP tools, guaranteed rules, Bedrock loop. |
| [`discord-actions.md`](discord-actions.md) | Withdraw buttons on the Discord fraud alert: guards and one-time setup. |
| [`../data/external/README.md`](../data/external/README.md) | Datasets behind the ML anomaly layer, and how to rebuild them. |
| [`../frontend/README.md`](../frontend/README.md) | Dashboard: modes, commands, code map. |
