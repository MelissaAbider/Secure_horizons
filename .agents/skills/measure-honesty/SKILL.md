---
name: measure-honesty
description: Block detection numbers when thresholds are unfrozen or edited after a run
---

Before any detection, alert, replay, or metrics code. Reply in English.

1. Read `docs/product/THRESHOLDS.md`.
2. If status is not FROZEN, do not write a measurement run and do not invent a threshold. You may write the mechanism with thresholds injected from that file.
3. If thresholds are frozen, do not edit them in the same change as a result.
4. Name the definition used: attack start, detection time, still recoverable, false alert.
5. Do not add an incident fact that is not in `docs/product/SOURCES.md`.
