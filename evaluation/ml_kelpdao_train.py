"""Train and evaluate KelpDAO-pattern detectors on scenario-specific features, without leakage.

Honest protocol with a single real attack:
  - NORMAL data: 5 real Aave windows, weeks before the incident.
  - Negatives also include the PRE-ATTACK part of the attack file (same protocol, same day).
  - Supervised models cannot be trained on KelpDAO and tested on KelpDAO. So we train them on SYNTHETIC positives?
    No: here we test two things that are legitimate with one attack:
      (A) Unsupervised / one-class models fitted on NORMAL ONLY, scored on the attack day  -> true out-of-sample detection.
      (B) Supervised models in TEMPORAL mode: train on normal windows + attack-day windows up to block attack+K
          (the first K blocks of the attack), test on the rest of the attack day. Reports how early a model that saw
          only the very beginning can flag the continuation. Clearly labeled as such.
  - Thresholds are set on normal data only (max score over normal windows -> zero false alerts by construction on
    the normal set we have). False-alert rate is then measured on HELD-OUT normal windows (one normal file left out).

Outputs data/external/ml/kelpdao/results.md and results.json.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler
from sklearn.svm import OneClassSVM

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "external" / "ml" / "kelpdao"
ATTACK = 24908285
SEED = 42
Q = 0.995  # threshold = this quantile of scores on normal training windows (set before looking at the attack day)


def unsupervised_models():
    import lightgbm as lgb  # noqa: F401 (import check for the supervised block)
    return {
        "iforest": lambda: make_pipeline(RobustScaler(), IsolationForest(n_estimators=500, contamination=0.01, random_state=SEED)),
        "ocsvm": lambda: make_pipeline(RobustScaler(), OneClassSVM(nu=0.02, gamma="scale")),
        "lof": lambda: make_pipeline(RobustScaler(), LocalOutlierFactor(n_neighbors=35, novelty=True, contamination=0.01)),
        "robust_z": None,
    }


def score_unsup(name, model, X):
    if name == "robust_z":
        return model(X)
    return -model.score_samples(X)


def fit_robust_z(Xn: np.ndarray):
    med = np.median(Xn, axis=0)
    mad = np.median(np.abs(Xn - med), axis=0) + 1e-9
    def scorer(X):
        z = np.abs((X - med) / mad)
        return np.sort(z, axis=1)[:, -3:].mean(axis=1)  # mean of the 3 most deviant features
    return scorer


def evaluate(y, s, thr, ends):
    pred = s >= thr
    tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum()); fn = int((~pred & (y == 1)).sum())
    flagged = ends[pred & (ends >= ATTACK)]
    first = int(flagged.min()) if len(flagged) else None
    return {"roc_auc": float(roc_auc_score(y, s)) if y.sum() and (y == 0).sum() else None,
            "pr_auc": float(average_precision_score(y, s)) if y.sum() else None,
            "recall": tp / (tp + fn) if tp + fn else 0.0, "precision": tp / (tp + fp) if tp + fp else 0.0,
            "false_alerts": fp, "detected": tp, "positives": int(y.sum()),
            "first_detection_block": first, "latency_blocks": (first - ATTACK) if first is not None else None}


def main():
    df = pd.read_csv(D / "windows.csv")
    meta = {"window_start", "window_end", "label", "file"}
    features = [c for c in df.columns if c not in meta and df[c].std() > 0]
    normal_files = sorted(df.loc[df.file != "attack", "file"].unique())
    attack = df[df.file == "attack"].reset_index(drop=True)
    results = {"features": features, "unsupervised": {}, "temporal_supervised": {}}
    lines = ["# KelpDAO-pattern detectors — scenario features, leakage-free", "",
             f"Windows: {len(df)} (attack day {len(attack)}, positives {int(attack.label.sum())}); normal files: {len(normal_files)}; features: {len(features)}.", ""]

    # ---------------- (A) unsupervised, fitted on normal only, held-out normal file for false-alert rate -------------
    lines += ["## A. One-class / anomaly models fitted on NORMAL ONLY, scored on the attack day", "",
              f"Threshold = {Q:.3%} quantile of scores on the normal training files (chosen a priori, never on the attack day).", "",
              "| model | held-out normal false alerts (per file, mean) | attack ROC-AUC | attack PR-AUC | recall | precision | pre-attack false alerts | latency (blocks) |",
              "|---|---|---|---|---|---|---|---|"]
    for name, factory in unsupervised_models().items():
        fold_fp = []
        for held in normal_files:
            Xn = df.loc[(df.file != "attack") & (df.file != held), features].values
            Xh = df.loc[df.file == held, features].values
            model = fit_robust_z(RobustScaler().fit(Xn).transform(Xn)) if name == "robust_z" else factory().fit(Xn)
            if name == "robust_z":
                sc = RobustScaler().fit(Xn)
                s_tr, s_h = model(sc.transform(Xn)), model(sc.transform(Xh))
            else:
                s_tr, s_h = score_unsup(name, model, Xn), score_unsup(name, model, Xh)
            thr = float(np.quantile(s_tr, Q))
            fold_fp.append(int((s_h >= thr).sum()))
        Xn = df.loc[df.file != "attack", features].values
        if name == "robust_z":
            sc = RobustScaler().fit(Xn)
            model = fit_robust_z(sc.transform(Xn))
            s_tr, s_a = model(sc.transform(Xn)), model(sc.transform(attack[features].values))
            blob = pickle.dumps(("robust_z", sc, np.median(sc.transform(Xn), axis=0)))
        else:
            model = factory().fit(Xn)
            s_tr, s_a = score_unsup(name, model, Xn), score_unsup(name, model, attack[features].values)
            blob = pickle.dumps(model)
        thr = float(np.quantile(s_tr, Q))
        m = evaluate(attack.label.values, s_a, thr, attack.window_end.values)
        pre_fp = int(((s_a >= thr) & (attack.window_end.values < ATTACK)).sum())
        m.update(threshold=thr, heldout_normal_false_alerts_mean=float(np.mean(fold_fp)), heldout_per_file=fold_fp,
                 pre_attack_false_alerts=pre_fp, model_hash="sha256:" + hashlib.sha256(blob).hexdigest())
        results["unsupervised"][name] = m
        (D / f"model_{name}.pkl").write_bytes(blob)
        lat = m["latency_blocks"]
        lines.append(f"| {name} | {np.mean(fold_fp):.1f} | {m['roc_auc']:.3f} | {m['pr_auc']:.3f} | {m['recall']:.3f} | {m['precision']:.3f} | {pre_fp} | {lat if lat is not None else 'missed'} |")

    # ---------------- (B) temporal supervised: learn from the first K attack blocks, flag the rest ------------------
    import lightgbm as lgb
    lines += ["", "## B. Supervised, TEMPORAL split on the attack day (sees only the first K blocks of the attack)", "",
              "Train = all normal windows + attack-day windows ending <= attack+K. Test = attack-day windows ending > attack+K.",
              "This measures early continuation detection, not zero-shot detection.", "",
              "| model | K (blocks seen) | test positives | recall | precision | false alerts on test | ROC-AUC |", "|---|---|---|---|---|---|---|"]
    normal = df[df.file != "attack"]
    for K in (40, 100, 200):
        tr = pd.concat([normal, attack[attack.window_end <= ATTACK + K]])
        te = attack[attack.window_end > ATTACK + K]
        if tr.label.sum() == 0:
            continue
        for name, model in (
            ("logreg", make_pipeline(RobustScaler(), LogisticRegression(max_iter=3000, class_weight="balanced", C=0.3, random_state=SEED))),
            ("lgbm", lgb.LGBMClassifier(n_estimators=200, num_leaves=7, max_depth=3, learning_rate=0.05, min_child_samples=5,
                                       scale_pos_weight=float((tr.label == 0).sum() / max(1, tr.label.sum())), random_state=SEED, verbose=-1)),
        ):
            model.fit(tr[features].values, tr.label.values)
            s_tr = model.predict_proba(tr.loc[tr.label == 0, features].values)[:, 1]
            thr = float(np.quantile(s_tr, 0.999))
            s_te = model.predict_proba(te[features].values)[:, 1]
            m = evaluate(te.label.values, s_te, thr, te.window_end.values)
            results["temporal_supervised"][f"{name}_K{K}"] = {**m, "K": K, "threshold": thr}
            lines.append(f"| {name} | {K} | {m['positives']} | {m['recall']:.3f} | {m['precision']:.3f} | {m['false_alerts']} | {m['roc_auc'] if m['roc_auc'] is None else round(m['roc_auc'], 3)} |")

    # ---------------- feature deviation at first detection (explainability) ----------------------------------------
    best = max(results["unsupervised"], key=lambda n: (results["unsupervised"][n]["recall"], -results["unsupervised"][n]["heldout_normal_false_alerts_mean"]))
    Xn = df.loc[df.file != "attack", features].values
    sc = RobustScaler().fit(Xn)
    fb = results["unsupervised"][best]["first_detection_block"]
    if fb is not None:
        row = attack[attack.window_end == fb].iloc[0]
        xr = row[features].values.astype(float)
        p99 = np.quantile(Xn, 0.99, axis=0)
        ratio = {f: (xr[i] / p99[i] if p99[i] > 0 else (float("inf") if xr[i] > 0 else 0.0)) for i, f in enumerate(features)}
        top = sorted(ratio.items(), key=lambda kv: -kv[1])[:6]
        lines += ["", f"## Explanation at first detection (block {fb}, model {best})", "",
                  "Value in the flagged window divided by the 99th percentile of normal windows:", ""]
        lines += [f"- {f}: x{v:,.0f}" if np.isfinite(v) else f"- {f}: non-zero while normal p99 is zero" for f, v in top]
        results["first_detection_explanation"] = {"block": fb, "model": best, "top_deviations": top}

    (D / "results.json").write_text(json.dumps(results, indent=2, default=float), encoding="utf-8")
    (D / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
