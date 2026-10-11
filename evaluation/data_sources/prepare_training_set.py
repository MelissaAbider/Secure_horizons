"""Clean the windowed dataset and produce leakage-free training material.

Input : data/external/ml/windows.csv (from build_ml_dataset.py)
Output: data/external/ml/train/
  - train.csv / test.csv       : KelpDAO strictly held out as the primary test; everything else is train
  - folds.json                 : leave-one-incident-out folds over the training incidents (for CV)
  - features.json              : ordered feature list, dtypes, and per-feature train statistics
  - integrity_report.json      : checks performed and their results
  - card.json                  : counts per incident / split

Cleaning rules (all recorded in integrity_report.json):
  1. keep only incidents with >= MIN_POS positive windows and >= MIN_NEG negative windows
  2. drop windows with fewer than MIN_ACTIVE_BLOCKS active blocks (near-empty windows carry no signal)
  3. drop exact duplicate feature rows within the same incident/file (idle periods repeat)
  4. clip non-finite values; assert no NaN/inf remains
  5. assert incident disjointness between train and test and between CV folds
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ML = ROOT / "data" / "external" / "ml"
OUT = ML / "train"
TEST_INCIDENTS = {"kelpdao_2026"}
MIN_POS, MIN_NEG, MIN_ACTIVE_BLOCKS = 30, 100, 3
MIN_FOLD_POS, MIN_FOLD_NEG = 20, 50
META = ("incident", "category", "chain", "file", "window_start", "window_end", "label")


def load() -> list[dict]:
    with open(ML / "windows.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            if k in META and k not in ("window_start", "window_end", "label"):
                continue
            try:
                r[k] = float(v) if "." in v or "e" in v.lower() else int(v)
            except ValueError:
                pass
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load()
    features = [c for c in rows[0] if c not in META]
    report = {"input_windows": len(rows), "steps": []}

    counts = defaultdict(Counter)
    for r in rows:
        counts[r["incident"]][r["label"]] += 1
    kept_incidents = {i for i, c in counts.items() if c[1] >= MIN_POS and c[0] >= MIN_NEG}
    dropped = sorted(set(counts) - kept_incidents)
    rows = [r for r in rows if r["incident"] in kept_incidents]
    report["steps"].append({"step": "incident_filter", "min_pos": MIN_POS, "min_neg": MIN_NEG,
                            "kept": sorted(kept_incidents), "dropped": dropped, "windows_after": len(rows)})

    before = len(rows)
    rows = [r for r in rows if r["blocks_with_activity"] >= MIN_ACTIVE_BLOCKS]
    report["steps"].append({"step": "drop_sparse_windows", "min_active_blocks": MIN_ACTIVE_BLOCKS, "removed": before - len(rows)})

    before = len(rows)
    seen, deduped = set(), []
    for r in rows:
        key = (r["incident"], r["file"], tuple(round(float(r[f]), 9) for f in features))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    rows = deduped
    report["steps"].append({"step": "dedupe_identical_feature_rows", "removed": before - len(rows)})

    clipped = 0
    for r in rows:
        for f in features:
            v = float(r[f])
            if not math.isfinite(v):
                r[f] = 0.0
                clipped += 1
    report["steps"].append({"step": "clip_non_finite", "values_replaced": clipped})
    assert all(math.isfinite(float(r[f])) for r in rows for f in features)

    test = [r for r in rows if r["incident"] in TEST_INCIDENTS]
    train = [r for r in rows if r["incident"] not in TEST_INCIDENTS]
    assert not ({r["incident"] for r in train} & {r["incident"] for r in test})
    train_incidents = sorted({r["incident"] for r in train})
    per_inc = {inc: Counter(r["label"] for r in train if r["incident"] == inc) for inc in train_incidents}
    # An incident can only be a validation fold if it has enough of both classes after cleaning; thin incidents
    # still contribute to training in every fold but never evaluate alone (their score would be noise).
    eligible = [inc for inc in train_incidents if per_inc[inc][1] >= MIN_FOLD_POS and per_inc[inc][0] >= MIN_FOLD_NEG]
    folds = [{"fold": k, "validation_incident": inc, "train_incidents": [i for i in train_incidents if i != inc]}
             for k, inc in enumerate(eligible)]
    for fold in folds:
        assert fold["validation_incident"] not in fold["train_incidents"]
    report["steps"].append({"step": "fold_eligibility", "min_fold_pos": MIN_FOLD_POS, "min_fold_neg": MIN_FOLD_NEG,
                            "validation_eligible": eligible, "train_only": [i for i in train_incidents if i not in eligible]})
    report["steps"].append({"step": "split", "test_incidents": sorted(TEST_INCIDENTS), "train_incidents": train_incidents,
                            "train_windows": len(train), "test_windows": len(test), "cv_folds": len(folds)})

    stats = {}
    for f in features:
        values = sorted(float(r[f]) for r in train)
        n = len(values)
        mean = sum(values) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in values) / n)
        stats[f] = {"mean": mean, "std": std, "min": values[0], "p50": values[n // 2], "max": values[-1],
                    "zero_fraction": sum(1 for v in values if v == 0) / n}
    constant = [f for f, s in stats.items() if s["std"] == 0]
    report["steps"].append({"step": "feature_stats", "constant_features_in_train": constant})

    def write(path: Path, data: list[dict]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(META) + features)
            w.writeheader()
            w.writerows({k: r[k] for k in list(META) + features} for r in data)

    write(OUT / "train.csv", train)
    write(OUT / "test.csv", test)
    (OUT / "folds.json").write_text(json.dumps(folds, indent=2), encoding="utf-8")
    (OUT / "features.json").write_text(json.dumps({"features": features, "label": "label", "group": "incident",
                                                   "meta": list(META), "train_stats": stats}, indent=2), encoding="utf-8")
    card = {"train": {inc: {"pos": sum(1 for r in train if r["incident"] == inc and r["label"] == 1),
                            "neg": sum(1 for r in train if r["incident"] == inc and r["label"] == 0)} for inc in train_incidents},
            "test": {inc: {"pos": sum(1 for r in test if r["incident"] == inc and r["label"] == 1),
                           "neg": sum(1 for r in test if r["incident"] == inc and r["label"] == 0)} for inc in sorted(TEST_INCIDENTS)},
            "totals": {"train_pos": sum(r["label"] for r in train), "train_neg": sum(1 for r in train if r["label"] == 0),
                       "test_pos": sum(r["label"] for r in test), "test_neg": sum(1 for r in test if r["label"] == 0)}}
    (OUT / "card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    (OUT / "integrity_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"train: {len(train)} windows ({card['totals']['train_pos']} pos) over {len(train_incidents)} incidents")
    print(f"test : {len(test)} windows ({card['totals']['test_pos']} pos) -> {sorted(TEST_INCIDENTS)}")
    print(f"folds: {len(folds)} leave-one-incident-out on {eligible} | dropped incidents: {dropped}")
    for inc in train_incidents:
        c = card["train"][inc]
        print(f"  {inc:22} pos={c['pos']:3} neg={c['neg']:5}")
    if constant:
        print("constant features (drop before training):", constant)


if __name__ == "__main__":
    main()
