"""Benchmark several detectors on the cleaned incident dataset with a leakage-free protocol.

Protocol
  1. Leave-one-incident-out CV on data/external/ml/train (folds.json). Every metric is per fold; we report mean and worst.
  2. The decision threshold of each model is chosen ON VALIDATION FOLDS (target: precision >= 0.9 on pooled out-of-fold
     predictions), never on the test set.
  3. Each model is refit on the full training set, frozen (sha256 of the pickled model), then scored ONCE on KelpDAO.
  4. Detection latency on KelpDAO = first window with score >= threshold whose end is >= attack block, in blocks.

Models
  - logreg      : standardized logistic regression (class_weight balanced)        -> interpretable baseline
  - rf          : random forest (balanced)                                          -> robust non-linear baseline
  - xgb         : XGBoost, shallow                                                  -> gradient boosting #1
  - lgbm        : LightGBM, shallow                                                 -> gradient boosting #2 (candidate)
  - iforest     : Isolation Forest fitted on NEGATIVE windows only (unsupervised)   -> anomaly baseline
  - ensemble    : mean of lgbm and iforest normalized scores                        -> literature-style ensemble

Outputs data/external/ml/results/{cv_metrics.json, test_metrics.json, report.md, models/*.pkl, shap_lgbm.json}.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
ML = ROOT / "data" / "external" / "ml"
TRAIN_DIR, OUT = ML / "train", ML / "results"
SEED, TARGET_PRECISION = 42, 0.90


def load():
    spec = json.loads((TRAIN_DIR / "features.json").read_text())
    train = pd.read_csv(TRAIN_DIR / "train.csv")
    test = pd.read_csv(TRAIN_DIR / "test.csv")
    folds = json.loads((TRAIN_DIR / "folds.json").read_text())
    features = [f for f in spec["features"] if train[f].std() > 0]
    return train, test, folds, features


def make_models(pos_weight: float):
    import lightgbm as lgb
    import xgboost as xgb
    return {
        "logreg": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced", C=0.5, random_state=SEED)),
        "rf": lambda: RandomForestClassifier(n_estimators=400, max_depth=6, min_samples_leaf=5, class_weight="balanced_subsample", random_state=SEED, n_jobs=-1),
        "xgb": lambda: xgb.XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                                         min_child_weight=5, reg_lambda=2.0, scale_pos_weight=pos_weight, eval_metric="aucpr",
                                         random_state=SEED, n_jobs=-1, verbosity=0),
        "lgbm": lambda: lgb.LGBMClassifier(n_estimators=300, num_leaves=15, max_depth=4, learning_rate=0.05, subsample=0.8,
                                           subsample_freq=1, colsample_bytree=0.8, min_child_samples=10, reg_lambda=2.0,
                                           scale_pos_weight=pos_weight, random_state=SEED, n_jobs=-1, verbose=-1),
        "iforest": lambda: IsolationForest(n_estimators=400, contamination="auto", random_state=SEED, n_jobs=-1),
    }


def fit_score(name, factory, Xtr, ytr, Xev):
    model = factory()
    if name == "iforest":
        model.fit(Xtr[ytr == 0])
        return model, -model.score_samples(Xev)  # higher = more anomalous
    model.fit(Xtr, ytr)
    return model, model.predict_proba(Xev)[:, 1]


def minmax(a: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.clip((a - lo) / (hi - lo), 0, 1) if hi > lo else np.zeros_like(a)


def threshold_for_precision(y, s, target):
    p, r, t = precision_recall_curve(y, s)
    ok = [(thr, rec) for prec, rec, thr in zip(p[:-1], r[:-1], t) if prec >= target]
    if ok:
        return max(ok, key=lambda x: x[1])[0]
    return float(np.quantile(s, 0.99))


def metrics(y, s, thr):
    pred = (s >= thr).astype(int)
    tp, fp, fn = int(((pred == 1) & (y == 1)).sum()), int(((pred == 1) & (y == 0)).sum()), int(((pred == 0) & (y == 1)).sum())
    return {"roc_auc": float(roc_auc_score(y, s)) if len(set(y)) > 1 else None,
            "pr_auc": float(average_precision_score(y, s)) if len(set(y)) > 1 else None,
            "precision": tp / (tp + fp) if tp + fp else 0.0, "recall": tp / (tp + fn) if tp + fn else 0.0,
            "false_alerts": fp, "detected_positives": tp, "positives": int(y.sum())}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "models").mkdir(exist_ok=True)
    train, test, folds, features = load()
    pos_weight = float((train.label == 0).sum() / max(1, (train.label == 1).sum()))
    factories = make_models(pos_weight)
    names = list(factories) + ["ensemble"]
    oof = {n: np.zeros(len(train)) for n in names}
    cv = {n: [] for n in names}
    t0 = time.time()
    for fold in folds:
        va = train.incident == fold["validation_incident"]
        tr = train.incident.isin(fold["train_incidents"])
        Xtr, ytr, Xva, yva = train.loc[tr, features].values, train.loc[tr, "label"].values, train.loc[va, features].values, train.loc[va, "label"].values
        scores = {}
        for n, f in factories.items():
            _, s = fit_score(n, f, Xtr, ytr, Xva)
            scores[n] = s
        _, lg_tr = fit_score("lgbm", factories["lgbm"], Xtr, ytr, Xtr)
        _, if_tr = fit_score("iforest", factories["iforest"], Xtr, ytr, Xtr)
        scores["ensemble"] = 0.5 * minmax(scores["lgbm"], lg_tr.min(), lg_tr.max()) + 0.5 * minmax(scores["iforest"], if_tr.min(), if_tr.max())
        for n in names:
            oof[n][va.values] = scores[n]
            m = metrics(yva, scores[n], np.quantile(scores[n], 0.9))  # provisional per-fold threshold for AUCs only
            cv[n].append({"fold": fold["validation_incident"], "roc_auc": m["roc_auc"], "pr_auc": m["pr_auc"], "positives": m["positives"]})
    print(f"CV done in {time.time() - t0:.0f}s")

    thresholds, cv_summary = {}, {}
    y_oof = train.label.values
    for n in names:
        thr = threshold_for_precision(y_oof, oof[n], TARGET_PRECISION)
        thresholds[n] = float(thr)
        pooled = metrics(y_oof, oof[n], thr)
        per_fold_rec = []
        for fold in folds:
            va = (train.incident == fold["validation_incident"]).values
            per_fold_rec.append(metrics(y_oof[va], oof[n][va], thr))
        cv_summary[n] = {"threshold": float(thr), "pooled_oof": pooled,
                         "mean_pr_auc": float(np.mean([f["pr_auc"] for f in cv[n] if f["pr_auc"] is not None])),
                         "worst_pr_auc": float(np.min([f["pr_auc"] for f in cv[n] if f["pr_auc"] is not None])),
                         "mean_roc_auc": float(np.mean([f["roc_auc"] for f in cv[n] if f["roc_auc"] is not None])),
                         "per_fold": [{**cvf, "recall_at_thr": pf["recall"], "false_alerts_at_thr": pf["false_alerts"]} for cvf, pf in zip(cv[n], per_fold_rec)]}
    (OUT / "cv_metrics.json").write_text(json.dumps(cv_summary, indent=2), encoding="utf-8")

    # Final fit on all training data, freeze, then a single pass on KelpDAO.
    Xall, yall = train[features].values, train.label.values
    Xte, yte = test[features].values, test.label.values
    attack_block = 24908285
    test_summary, frozen = {}, {}
    fitted = {}
    for n, f in factories.items():
        model, s_te = fit_score(n, f, Xall, yall, Xte)
        fitted[n] = (model, s_te)
    _, lg_all = fit_score("lgbm", factories["lgbm"], Xall, yall, Xall)
    _, if_all = fit_score("iforest", factories["iforest"], Xall, yall, Xall)
    fitted["ensemble"] = (None, 0.5 * minmax(fitted["lgbm"][1], lg_all.min(), lg_all.max()) + 0.5 * minmax(fitted["iforest"][1], if_all.min(), if_all.max()))
    for n in names:
        model, s_te = fitted[n]
        if model is not None:
            blob = pickle.dumps(model)
            (OUT / "models" / f"{n}.pkl").write_bytes(blob)
            frozen[n] = "sha256:" + hashlib.sha256(blob).hexdigest()
        thr = thresholds[n]
        m = metrics(yte, s_te, thr)
        attack_rows = (test.file == "attack.jsonl").values
        flagged = np.where(attack_rows & (s_te >= thr) & (test.window_end.values >= attack_block))[0]
        first = int(test.window_end.values[flagged].min()) if len(flagged) else None
        pre_fp = int(((s_te >= thr) & attack_rows & (test.window_end.values < attack_block)).sum())
        normal_fp = int(((s_te >= thr) & ~attack_rows).sum())
        test_summary[n] = {**m, "threshold": thr, "first_detection_window_end": first,
                           "detection_latency_blocks": (first - attack_block) if first is not None else None,
                           "false_alerts_pre_attack": pre_fp, "false_alerts_normal_days": normal_fp, "model_hash": frozen.get(n)}
    (OUT / "test_metrics.json").write_text(json.dumps(test_summary, indent=2), encoding="utf-8")

    try:
        import shap
        expl = shap.TreeExplainer(fitted["lgbm"][0])
        sv = expl.shap_values(Xte[yte == 1])
        sv = sv[1] if isinstance(sv, list) else sv
        imp = sorted(zip(features, np.abs(sv).mean(axis=0).tolist()), key=lambda kv: -kv[1])
        (OUT / "shap_lgbm.json").write_text(json.dumps({"kelpdao_positive_windows_mean_abs_shap": imp}, indent=2), encoding="utf-8")
    except Exception as exc:
        imp = []
        (OUT / "shap_lgbm.json").write_text(json.dumps({"error": type(exc).__name__}), encoding="utf-8")

    lines = ["# ML benchmark — leave-one-incident-out CV, single pass on KelpDAO", "",
             f"Train: {len(train)} windows / {int(yall.sum())} positive / {train.incident.nunique()} incidents. Test (KelpDAO): {len(test)} windows / {int(yte.sum())} positive.",
             f"Thresholds chosen on out-of-fold predictions for precision >= {TARGET_PRECISION}. Features: {len(features)}.", "",
             "## Cross-validation (per-incident folds)", "",
             "| model | mean PR-AUC | worst PR-AUC | mean ROC-AUC | pooled recall @thr | pooled precision @thr |", "|---|---|---|---|---|---|"]
    for n in names:
        c = cv_summary[n]
        lines.append(f"| {n} | {c['mean_pr_auc']:.3f} | {c['worst_pr_auc']:.3f} | {c['mean_roc_auc']:.3f} | {c['pooled_oof']['recall']:.3f} | {c['pooled_oof']['precision']:.3f} |")
    lines += ["", "## Test on KelpDAO (never seen)", "",
              "| model | PR-AUC | ROC-AUC | recall | precision | latency (blocks) | false alerts pre-attack | false alerts normal days |", "|---|---|---|---|---|---|---|---|"]
    for n in names:
        t = test_summary[n]
        lat = t["detection_latency_blocks"]
        lines.append(f"| {n} | {t['pr_auc']:.3f} | {t['roc_auc']:.3f} | {t['recall']:.3f} | {t['precision']:.3f} | {lat if lat is not None else 'missed'} | {t['false_alerts_pre_attack']} | {t['false_alerts_normal_days']} |")
    lines += ["", "## Per-fold PR-AUC", "", "| model | " + " | ".join(f["validation_incident"] for f in folds) + " |", "|---|" + "---|" * len(folds)]
    for n in names:
        lines.append(f"| {n} | " + " | ".join(f"{f['pr_auc']:.2f}" for f in cv_summary[n]["per_fold"]) + " |")
    if imp:
        lines += ["", "## LightGBM: feature importance on KelpDAO positive windows (mean |SHAP|)", ""] + [f"- {f}: {v:.3f}" for f, v in imp[:10]]
    lines += ["", "Model hashes: " + ", ".join(f"{n}={h[:19]}…" for n, h in frozen.items())]
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
