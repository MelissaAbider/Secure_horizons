# Decisions

Format: date, decision, why, who. Agents add a row only after a human on the team has decided.

| Date | Decision | Why | Who |
| --- | --- | --- | --- |
| 2026-10-10 | Versioned product context lives in `docs/product/`, translated from `projet-en-bref.pdf`. | Stop agents drifting outside the brief. | initial setup |
| 2026-10-10 | All repo docs, code, commits, and UI copy are English. The French PDF stays the source brief only. | The group codes in English. | initial setup |
| 2026-10-10 | `docs/product/STATUS.md` is the only progress tracker. | A session must be able to resume without the previous chat. | initial setup |
| 2026-10-10 | Agents work one demo step at a time and must update STATUS before stopping. | Keeps coding sessions on the Sunday objective. | initial setup |
| 2026-10-10 | Agents default to building. They stop only for a security or secret hard stop, not for missing non-security details. | A hackathon agent that asks too often does not ship. | initial setup |
| 2026-10-10 | Shared agent files live in `AGENTS.md` and `.agents/skills/`, not in a tool-specific directory. | The whole group does not use the same coding agent. | initial setup |
| 2026-10-10 | T3 uses five deterministic KelpDAO rules: bridge invariant, collateral surge, liquidity drain, treasury exitability, and on-chain containment. | Tracks the real causal chain and removes utilization/liquidity redundancy. | team request |
| 2026-10-11 | ML dependencies for the T3 corroborator: scikit-learn 1.6, lightgbm 4.5, xgboost 2.1, pandas 2.2, shap 0.47 (all released > 7 days before). Not yet in requirements.txt: evaluation-only until the model is wired into T3. | Needed to benchmark detectors on real incident data. | Melissa (requested the ML track) |
| 2026-10-11 | ML corroborator candidate = Local Outlier Factor on 22 scenario-specific Aave features, fitted on normal data only, threshold at the 99.5% quantile of normal scores. Supervised cross-incident models rejected (ROC 0.54–0.80 on KelpDAO, no transfer between incidents). | Only approach that detected the real KelpDAO day with ~1.8 false alerts per normal 2,000-block file and zero pre-attack false alerts. | measured, see data/external/ml/kelpdao/results.md |
| 2026-10-11 | ML corroborator v2 = Elliptic Envelope (robust covariance) on the 28 "flows" features of feature set v2 (collateral + borrow + withdraw, multi-scale, surge memory), fitted on normal only, Q=0.995. Selected among 240 candidates by held-out false-alert rate on normal data only; the attack day was read once after selection. Supersedes the LOF v1 candidate. | On the real KelpDAO day: recall 0.76 (was 0.59), precision 0.86, 0 pre-attack false alerts, first alert +29 blocks; 0.87% held-out false alerts. | measured, see data/external/ml/kelpdao/search_report.md |
