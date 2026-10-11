"""Hyperparameter and feature-set search for one-class KelpDAO detectors, selected WITHOUT looking at the attack.

Selection criterion (computable from normal data only), for each candidate (feature set, model, params, quantile Q):
  - fit on 4 normal files, threshold = Q-quantile of training scores, count false alerts on the 5th held-out file;
  - rotate over the 5 files; the candidate's cost = mean held-out false alerts per file (lower is better).
  - Ties and near-ties are broken by a proxy of sensitivity that does not use the attack: the fraction of a SYNTHETIC
    stress window flagged, where the stress window is built by scaling the collateral/borrow features of a normal window
    by the ratios that define the scenario in THRESHOLDS.md (collateral surge >= 200%, drain >= 60%). This is a weak,
    rule-derived proxy; it is only used to avoid selecting a model that never fires.
After selection, the chosen configurations are refit on all normal data and scored ONCE on the attack day.
We also report the attack-day result of every candidate for transparency, clearly separated, but it is not used
for selection.

Output: data/external/ml/kelpdao/search_results.json, search_report.md
"""
from __future__ import annotations

import itertools
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler, StandardScaler
from sklearn.svm import OneClassSVM
from sklearn.decomposition import PCA
from sklearn.covariance import EllipticEnvelope

warnings.filterwarnings("ignore")
D = Path(__file__).resolve().parents[1] / "data" / "external" / "ml" / "kelpdao"
ATTACK = 24908285
SEED = 42
META = {"window_start", "window_end", "label", "file"}


def feature_sets(df_v1: pd.DataFrame, df_v2: pd.DataFrame) -> dict[str, tuple[pd.DataFrame, list[str]]]:
    f1 = [c for c in df_v1.columns if c not in META and df_v1[c].std() > 0]
    f2 = [c for c in df_v2.columns if c not in META and df_v2[c].std() > 0]
    scenario = [c for c in f2 if c.startswith(("coll_", "bor_borrow", "borrow_to", "blocks_since", "surge_", "log_borrow_since", "log_coll_since", "rate_"))]
    flows = [c for c in f2 if c.startswith(("coll_", "bor_"))]
    return {"v1_all": (df_v1, f1), "v2_all": (df_v2, f2), "v2_scenario": (df_v2, scenario), "v2_flows": (df_v2, flows)}


def models():
    grid = {}
    for n in (20, 35, 50, 80):
        for scaler in ("robust", "standard"):
            grid[f"lof_k{n}_{scaler}"] = lambda n=n, scaler=scaler: make_pipeline(
                RobustScaler() if scaler == "robust" else StandardScaler(), LocalOutlierFactor(n_neighbors=n, novelty=True, contamination="auto"))
    for n_est, msamp in ((300, 256), (500, "auto"), (800, 512)):
        grid[f"iforest_{n_est}_{msamp}"] = lambda n_est=n_est, msamp=msamp: make_pipeline(
            RobustScaler(), IsolationForest(n_estimators=n_est, max_samples=msamp, contamination="auto", random_state=SEED))
    for nu in (0.005, 0.01, 0.02):
        for gamma in ("scale", 0.01):
            grid[f"ocsvm_nu{nu}_g{gamma}"] = lambda nu=nu, gamma=gamma: make_pipeline(RobustScaler(), OneClassSVM(nu=nu, gamma=gamma))
    for k in (5, 8):
        grid[f"pca{k}_lof35"] = lambda k=k: make_pipeline(RobustScaler(), PCA(n_components=k, random_state=SEED), LocalOutlierFactor(n_neighbors=35, novelty=True))
    grid["elliptic"] = lambda: make_pipeline(RobustScaler(), EllipticEnvelope(contamination=0.01, support_fraction=0.9, random_state=SEED))
    return grid


def score(model, X):
    return -model.score_samples(X)


def stress_proxy(df_norm: pd.DataFrame, feats: list[str]) -> np.ndarray:
    """Rule-derived synthetic stress: scale scenario features of normal windows by THRESHOLDS ratios. Weak proxy only."""
    X = df_norm[feats].copy()
    for c in feats:
        if c.startswith("coll_") and ("vs_p99" in c or "vs_baseline" in c):
            X[c] = X[c] + 3.0  # collateral >= 200% above normal extreme
        if c.startswith("bor_borrow") and ("vs_p99" in c or "vs_baseline" in c):
            X[c] = X[c] + 2.0
        if c.startswith("bor_withdraw") and ("vs_p99" in c or "vs_baseline" in c):
            X[c] = X[c] + 1.5
        if c in ("coll_and_borrow", "surge_recent"):
            X[c] = 1
    return X.values


def evaluate_attack(y, s, thr, ends):
    pred = s >= thr
    tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum()); fn = int((~pred & (y == 1)).sum())
    flagged = ends[pred & (ends >= ATTACK)]
    first = int(flagged.min()) if len(flagged) else None
    pre_fp = int((pred & (ends < ATTACK)).sum())
    return {"recall": tp / (tp + fn) if tp + fn else 0.0, "precision": tp / (tp + fp) if tp + fp else 0.0,
            "pre_attack_fp": pre_fp, "latency": (first - ATTACK) if first is not None else None}


def main():
    v1 = pd.read_csv(D / "windows.csv")
    v2 = pd.read_csv(D / "windows_v2.csv")
    sets = feature_sets(v1, v2)
    grid = models()
    quantiles = (0.99, 0.995, 0.999)
    results = []
    for fs_name, (df, feats) in sets.items():
        normal_files = sorted(df.loc[df.file != "attack", "file"].unique())
        attack = df[df.file == "attack"]
        for m_name, factory in grid.items():
            fold_fp = {q: [] for q in quantiles}
            fold_stress = {q: [] for q in quantiles}
            ok = True
            for held in normal_files:
                tr = df[(df.file != "attack") & (df.file != held)]
                te = df[df.file == held]
                try:
                    model = factory().fit(tr[feats].values)
                    s_tr, s_te = score(model, tr[feats].values), score(model, te[feats].values)
                    s_stress = score(model, stress_proxy(te, feats))
                except Exception:
                    ok = False
                    break
                for q in quantiles:
                    thr = np.quantile(s_tr, q)
                    fold_fp[q].append(int((s_te >= thr).sum()) / max(1, len(te)) * 100)
                    fold_stress[q].append(float((s_stress >= thr).mean()))
            if not ok:
                continue
            model = factory().fit(df.loc[df.file != "attack", feats].values)
            s_norm = score(model, df.loc[df.file != "attack", feats].values)
            s_att = score(model, attack[feats].values)
            for q in quantiles:
                thr = float(np.quantile(s_norm, q))
                att = evaluate_attack(attack.label.values, s_att, thr, attack.window_end.values)
                results.append({"features": fs_name, "n_features": len(feats), "model": m_name, "q": q,
                                "heldout_fp_pct": float(np.mean(fold_fp[q])), "heldout_fp_pct_max": float(np.max(fold_fp[q])),
                                "stress_fire_rate": float(np.mean(fold_stress[q])), **{f"attack_{k}": v for k, v in att.items()}})
    res = pd.DataFrame(results)
    # Selection without the attack: lowest held-out false-alert % among candidates whose stress proxy fires at least 50%.
    eligible = res[res.stress_fire_rate >= 0.5].copy()
    if eligible.empty:
        eligible = res.copy()
    eligible["cost"] = eligible.heldout_fp_pct + 0.5 * eligible.heldout_fp_pct_max
    selected = eligible.sort_values(["cost", "stress_fire_rate"], ascending=[True, False]).head(10)
    res.to_json(D / "search_results.json", orient="records", indent=2)
    lines = ["# One-class detector search (selected on normal data only; attack read once, reported separately)", "",
             f"Candidates: {len(res)} (feature sets x models x quantiles). Eligible (stress proxy fires >= 50%): {len(eligible)}.", "",
             "## Top 10 by normal-only cost (held-out false-alert % + 0.5 x worst file)", "",
             "| features | model | Q | held-out FP % (mean / worst) | stress fire | attack recall | attack precision | pre-attack FP | latency |",
             "|---|---|---|---|---|---|---|---|---|"]
    for _, r in selected.iterrows():
        lines.append(f"| {r.features} | {r.model} | {r.q} | {r.heldout_fp_pct:.2f} / {r.heldout_fp_pct_max:.2f} | {r.stress_fire_rate:.2f} | {r.attack_recall:.3f} | {r.attack_precision:.3f} | {r.attack_pre_attack_fp} | {r.attack_latency if r.attack_latency is not None else 'missed'} |")
    best_att = res.sort_values(["attack_recall", "attack_precision"], ascending=False).head(5)
    lines += ["", "## For transparency: best 5 on the attack day (NOT used for selection; shows the ceiling)", "",
              "| features | model | Q | held-out FP % | attack recall | attack precision | pre-attack FP | latency |", "|---|---|---|---|---|---|---|---|"]
    for _, r in best_att.iterrows():
        lines.append(f"| {r.features} | {r.model} | {r.q} | {r.heldout_fp_pct:.2f} | {r.attack_recall:.3f} | {r.attack_precision:.3f} | {r.attack_pre_attack_fp} | {r.attack_latency if r.attack_latency is not None else 'missed'} |")
    (D / "search_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
