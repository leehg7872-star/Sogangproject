# SCPC 2026 Final — Harness

A generalized `FinalHarness.answer_task(task, session)` implementation for the
SCPC 2026 Final Round agent-safety task, plus a local dev-set scorer and a
`submission.csv` builder for the 700 `screening_tasks.jsonl` tasks.

## Layout

- `harness.py` — `FixedSLMClient` facade, `FinalHarness`, and the CLI runner.
- `scorer.py` — local dev-set scorer, ported from the contest baseline
  notebook (`data/SCPC2026_Final_baseline.ipynb`), used only for local
  sanity-checking against `data/dev_answers.json`.
- `data/` — the public contest package (dev tasks/answers, screening tasks,
  submission schema, terms guide).
- `submission.csv` — generated output for the 700 screening tasks.

## Usage

```bash
cd scpc_harness
python3 harness.py dev      # score FinalHarness against the 120 dev tasks
python3 harness.py submit   # build submission.csv from screening_tasks.jsonl
```

`meta.fixed_slm_policy`/`meta.model_id` are pinned to the required
`local_fixed_slm_only` / `scpc-final-fixed-slm-local-facade` values, and no
network or external model calls are made anywhere in the harness.

## Design

The contest's own weak baseline (focal chosen by prompt/attrs token overlap,
control chosen by a handful of top-level record-type checks) scores **0.088**
on the local dev proxy metric. This harness instead treats each task as
having up to three independent evidence layers, and resolves them in this
order:

1. **A live corrective clause in the current prompt.** Most tasks end with a
   "단, ..." clause that overrides everything else for *this* turn (e.g. "do
   not send externally, just update local state", "ask the user first, the
   premise isn't confirmed yet", "a past approval no longer holds, stop").
   `classify_override_clause` recognizes these by *semantic* pattern (a
   negated-dispatch concept + a local-state concept; an approval concept +
   a broken/invalidated concept + a stop verb; etc.) rather than literal
   sentences, so it generalizes to the screening set's paraphrased wording
   of the same four clause families (LOCAL_ONLY / ASK / HOLD / AMEND).

2. **Structured route-resolution records**, when no live clause fires.
   `focal_marker_refs` + `focal_resolution_trace` give an exact chain
   (`latest_phase → phase_to_marker → marker_to_ref → object.ref_code`) for
   which object is authoritative; `dispatch_authority_check` /
   `share_boundary_update` / `ambiguous_target` / `guardrail_ladder_signal`
   jointly describe how settled a dispatch route is and drive `control`
   (see `decide_control`'s route-family branch).

3. **Cross-turn session memory.** `persistent_memory_write` records (turn 1
   of many sessions) are captured by `memory_key` and by `person`;
   `persistent_memory_recall` records later in the same run resolve against
   that memory (`memory_class: prior_result` → last successful target,
   `standing_constraint` → the enterprise approval channel, otherwise a
   domain-based field such as the health/lighting channel).

`choose_focal` layers a similar cascade for the *object* to act on: the
marker/phase chain above, then a Korean ordinal-in-list parse of
`visible_history` ("candidates in order A, B, C; only the second was
confirmed"), then literal id/ref-code references, then token overlap as a
last resort.

`content_scope`, `policy`, and `plan_events` are derived from
`(focal, target, control)` plus the same record signals — e.g. a
`local_update_boundary` dispatch always yields the same three-step
read/verify/update plan and `status_only` scope regardless of the literal
target name, matching the reference behavior across the sample tasks
examined.

## Local dev score

Scored with `scorer.score_dev_submission` (a local approximation of the
official server-side rubric — it does not implement `semantic_response` or
partial `control` credit, so the true leaderboard score should be somewhat
higher):

| axis | baseline | this harness |
| --- | --- | --- |
| overall | 0.088 | 0.82 |
| focal | 0.29 | 0.99 |
| target | 0.12 | 0.96 |
| control | 0.08 | 0.90 |
| content_scope | 0.02 | 0.77 |
| policy | 0.01 | 0.72 |
| plan | 0.01 | 0.78 |

No dev task IDs, sentences, or record values are hardcoded anywhere in
`harness.py`; every rule keys off the documented, reusable record-type
vocabulary described in `data/TERMS_GUIDE.md`, which is why the same logic
applies unmodified to all 700 screening tasks.
