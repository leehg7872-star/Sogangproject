"""SCPC 2026 Final harness.

Structured to match the contest's official baseline notebook
(SCPC2026_Final_baseline.ipynb) section-for-section: FixedSLMClient facade,
small task-reading helpers, then FinalHarness with the six recommended
judgment methods (choose_focal / infer_target / decide_control /
build_content_scope / build_policy / build_plan_events) plus
update_session_memory as bound methods -- the same shape as the notebook's
own skeleton, with the judgment logic replaced.

answer_task returns only the six fields required by submission_schema.json
(focal_id/target/control/content_scope/policy/plan_events), matching
dev_answers.json's own shape exactly -- the optional user_response/
audit_tags/counterfactual fields are intentionally omitted.

Usage:
    python harness.py dev                 # run against dev_tasks.jsonl and score
    python harness.py submit              # build submission.csv from screening_tasks.jsonl
"""

from __future__ import annotations

import csv
import dataclasses
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

SUBMISSION_SCHEMA = "scpc.final.answer.v1"
FIXED_SLM_ID = "scpc-final-fixed-slm-local-facade"
ROOT = Path(__file__).resolve().parent

if (ROOT / "SCPC2026_Final_data.zip").is_file() and not (ROOT / "data").is_dir():
    with zipfile.ZipFile(ROOT / "SCPC2026_Final_data.zip") as zf:
        zf.extractall(ROOT)

_DATA_CANDIDATES = [
    ROOT / "participant" / "data",
    ROOT / "data",
    ROOT,
    ROOT.parent / "participant" / "data",
]
DATA_DIR = next((p for p in _DATA_CANDIDATES if (p / "screening_tasks.jsonl").is_file()), ROOT / "data")


# --------------------------------------------------------------------------
# Fixed SLM facade (provided interface, unmodified from the baseline notebook;
# used only as a supplementary evidence source per contest rules).
# --------------------------------------------------------------------------
class FixedSLMClient:
    model_id = FIXED_SLM_ID

    def summarize_task(self, task: dict[str, Any]) -> dict[str, Any]:
        text_parts: list[str] = [str(task.get("prompt", ""))]
        device_state = task.get("device_state", {}) or {}
        for rec in device_state.get("records", []) or []:
            text_parts.append(str(rec.get("type", "")))
            text_parts.append(str(rec.get("value", "")))
        for mem in task.get("personal_memory", []) or []:
            text_parts.append(str(mem.get("text", "")))
        text = " ".join(text_parts).lower()

        flags: set[str] = set()
        tags: set[str] = set()
        if "phishing" in text or "피싱" in text or "security_alert" in text:
            flags.update(["payment", "phishing"])
            tags.add("security_precedence")
        if "consent" in text or "동의" in text:
            tags.add("consent_precedence")
        if "health" in text or "건강" in text or "복약" in text or "검진" in text:
            flags.add("health")
        if "external" in text or "외부" in text:
            flags.add("external_share")
        if "privacy" in text or "개인정보" in text or "개인" in text:
            flags.add("privacy")
        if "rrn" in text or "raw_quote" in text or "실명" in text or "위치" in text:
            flags.add("sensitive_content")
        if "ambiguous" in text or "모호" in text:
            flags.add("ambiguous_reference")
            tags.add("resolved_target")

        return {
            "risk_flags": sorted(flags),
            "requires_redaction": any(
                k in text
                for k in ["raw_sensitive_forbidden", "raw_quote_forbidden", "numeric_value_forbidden", "실명", "위치", "원문"]
            ),
            "requires_confirmation": any(
                k in text for k in ["ambiguous", "amount_changed", "duration_ambiguous", "missing", "확인", "모호"]
            ),
            "audit_tags": sorted(tags),
        }


# --------------------------------------------------------------------------
# Small task-reading helpers (same names/signatures as the baseline notebook)
# --------------------------------------------------------------------------
def records_of(task: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((task.get("device_state") or {}).get("records") or []))


def objects_of(task: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((task.get("device_state") or {}).get("objects") or []))


def record_map(records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for record in records:
        if isinstance(record, dict):
            out[str(record.get("type"))] = record.get("value")
    return out


def text_of(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def object_text(obj: dict[str, Any]) -> str:
    attrs = obj.get("attrs") or {}
    return " ".join([str(obj.get("id", "")), str(obj.get("type", "")), text_of(attrs)]).lower()


SENSITIVE_FIELD_NAMES = {"raw_quote", "rrn", "location", "numeric_value", "doctor_note", "card_number", "name"}


def sensitive_fields_of(obj: dict[str, Any]) -> set[str]:
    attrs = obj.get("attrs") or {}
    fields: set[str] = set()
    for key in ("contains", "fields"):
        value = attrs.get(key)
        if isinstance(value, list):
            fields.update(str(v) for v in value)
    return fields & SENSITIVE_FIELD_NAMES


# --------------------------------------------------------------------------
# Final-instruction classification: the last corrective clause in a prompt
# (usually introduced by "단," / "다만,") frequently overrides every other
# signal in the task. These detectors key on the *semantic* pattern of that
# clause (negated external dispatch, broken precondition, pending
# confirmation, redaction-only) rather than on literal sentences, so they
# generalize across paraphrased wording.
# --------------------------------------------------------------------------
_HOLD_CONCEPT = ("허용", "근거", "전제", "승인", "consent")
_HOLD_STOP = (
    "안 된다", "위험", "보류", "멈춘다", "멈춰야", "막아야", "막는다", "차단", "금지",
    "실행하면 안", "처리하지 않는다",
)

_LOCAL_NOSEND = ("외부", "바깥", "보내", "전송", "전달", "넘기", "공유")
_LOCAL_LOCAL = ("내부", "로컬", "기기", "장치")
_LOCAL_STATE_UPDATE = ("상태",)
_LOCAL_UPDATE_VERB = ("갱신", "업데이트", "남기", "바꾸", "정리", "새로 쓰")
_LOCAL_NEGATION = ("말고", "대신", "생략", "접", "취소", "빼고", "아니라", "아닌")
# "로컬 처리로 단정하지 말고 ... 확인" is telling the agent NOT to assume the
# local path and to ask instead -- the opposite of a local-only override.
_LOCAL_ONLY_EXCLUDE = ("단정하지",)

_AMEND_SUMMARY = ("요약",)
_AMEND_TRIM = ("제거", "덜어내", "제외", "포함하지 않는다", "남기지 않는다", "허용된다", "정제된")

# Require the confirm/ask trigger word to sit close to its supporting
# phrase, rather than merely co-occurring anywhere in the sentence --
# otherwise unrelated uses of "확인" (e.g. "판정해야 한다" elsewhere in the
# same sentence) create false positives.
_ASK_PATTERNS = (
    re.compile(r"확인.{0,8}해야\s*한다"),
    re.compile(r"확인.{0,10}필요(?:하다|하면|할)"),
    re.compile(r"확인.{0,6}받아야"),
    re.compile(r"확정되지\s*않았다"),
    re.compile(r"확인되지\s*않았다"),
    re.compile(r"확인하지\s*않으면"),
    re.compile(r"확인\s*절차를\s*먼저"),
    re.compile(r"확인\s*질문을\s*하라"),
    re.compile(r"다시\s*확인"),
    re.compile(r"물어봐야"),
    re.compile(r"확인을\s*거친다"),
    re.compile(r"clarification"),
    re.compile(r"결론을\s*내릴\s*수\s*없다"),
    re.compile(r"미확정"),
)


def _any_in(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def classify_override_clause(text: str) -> str:
    """Return one of LOCAL_ONLY / ASK / HOLD / AMEND / GENERIC."""
    if _any_in(text, _HOLD_CONCEPT) and _any_in(text, _HOLD_STOP):
        return "HOLD"

    has_nosend = _any_in(text, _LOCAL_NOSEND)
    has_negation = _any_in(text, _LOCAL_NEGATION)
    has_local_place = _any_in(text, _LOCAL_LOCAL)
    has_state_update = _any_in(text, _LOCAL_STATE_UPDATE) and _any_in(text, _LOCAL_UPDATE_VERB)
    if (
        has_nosend
        and has_negation
        and (has_local_place or has_state_update)
        and not _any_in(text, _LOCAL_ONLY_EXCLUDE)
    ):
        return "LOCAL_ONLY"

    if _any_in(text, _AMEND_SUMMARY) and _any_in(text, _AMEND_TRIM):
        return "AMEND"

    if any(p.search(text) for p in _ASK_PATTERNS):
        return "ASK"

    return "GENERIC"


def full_task_text(task: dict[str, Any]) -> str:
    parts = [str(task.get("prompt", ""))]
    for h in task.get("visible_history") or []:
        if isinstance(h, dict):
            parts.append(str(h.get("summary", "")))
    return " ".join(parts)


def classify_task_override(task: dict[str, Any]) -> str:
    """Classify the current request's own final corrective clause.

    Only the live prompt is scanned: it is where the "as of right now" user
    correction lives. Older visible_history summaries describe how *previous*
    turns were resolved and can otherwise be misread as a fresh override
    (e.g. a note that a past turn already asked the user gets mistaken for a
    live ask-to-confirm on this turn).
    """
    return classify_override_clause(str(task.get("prompt", "")))


# --------------------------------------------------------------------------
# Focal resolution helpers
# --------------------------------------------------------------------------
def _object_by_ref(objects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for obj in objects:
        ref = (obj.get("attrs") or {}).get("ref_code")
        if ref:
            out[str(ref)] = obj
    return out


def _resolve_focal_via_marker_chain(rm: dict[str, Any], object_by_ref: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    marker_refs = rm.get("focal_marker_refs")
    trace = rm.get("focal_resolution_trace")
    if not isinstance(marker_refs, dict) or not isinstance(trace, dict):
        return None
    marker_to_ref = marker_refs.get("marker_to_ref") or {}
    phase_to_marker = trace.get("phase_to_marker") or {}
    latest_phase_rule = trace.get("latest_phase_rule") or {}
    phase = trace.get("latest_phase")

    marker = phase_to_marker.get(phase) if isinstance(phase, str) else None
    if marker is None:
        # Fall back through the documented phase-ordering rule table: chase
        # any rule value that itself names a phase we do have a marker for.
        seen = set()
        cursor = phase
        while marker is None and isinstance(cursor, str) and cursor not in seen:
            seen.add(cursor)
            nxt = None
            for key, val in latest_phase_rule.items():
                if key.startswith(str(cursor) + "_after_") or key == cursor:
                    nxt = val
                    break
            if nxt is None:
                break
            marker = phase_to_marker.get(nxt)
            cursor = nxt
    if marker is None:
        return None
    ref_code = marker_to_ref.get(marker)
    if ref_code is None:
        return None
    return object_by_ref.get(str(ref_code))


_ORDINAL_INDEX = {"첫": 0, "두": 1, "세": 2, "네": 3}


def _resolve_focal_via_history_text(task: dict[str, Any], object_by_ref: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    history = sorted(
        (h for h in task.get("visible_history") or [] if isinstance(h, dict)),
        key=lambda h: h.get("turn", 0),
        reverse=True,
    )
    texts = [str(h.get("summary", "")) for h in history] + [str(task.get("prompt", ""))]
    for text in texts:
        m = re.search(r"최종\s*승인\s*후보\s*(WM-\d+)", text)
        if m and m.group(1) in object_by_ref:
            return object_by_ref[m.group(1)]

        if "후보" not in text:
            continue
        codes = re.findall(r"WM-\d+", text)
        if len(codes) < 2:
            continue
        if not ("순서대로" in text or "순서였" in text or "순서" in text):
            continue
        idx: int | None = None
        # The *confirmed* candidate is the one phrased as "<ordinal> 후보/항목만"
        # (only the Nth one), as opposed to the held-back ones phrased with
        # "후보는 보류" -- so anchor on that "만" suffix, not on whichever
        # ordinal word happens to appear first in the sentence.
        m2 = re.search(r"(첫|두|세|네)\s*번째\s*(?:후보|항목)\s*만", text)
        if m2:
            idx = _ORDINAL_INDEX.get(m2.group(1))
        elif re.search(r"가운데\s*(?:후보|항목)\s*만", text):
            idx = len(codes) // 2
        elif re.search(r"마지막\s*(?:후보|항목)\s*만", text):
            idx = -1
        if idx is not None and -len(codes) <= idx < len(codes):
            code = codes[idx]
            if code in object_by_ref:
                return object_by_ref[code]
    return None


# --------------------------------------------------------------------------
# Target inference helpers
# --------------------------------------------------------------------------
def _resolved_target_value(rm: dict[str, Any]) -> str | None:
    resolved = rm.get("resolved_target")
    if isinstance(resolved, str) and resolved:
        return resolved
    if isinstance(resolved, dict):
        for key in ("target", "route", "value", "name", "recipient"):
            if resolved.get(key):
                return str(resolved[key])
    return None


_HEALTH_WORDS = ("건강", "검진", "복약", "점검", "병원", "진료")
_LIGHTING_WORDS = ("조명", "불빛", "밝기")


def _target_from_memory_recall(task: dict[str, Any], rm: dict[str, Any], memory: dict[str, Any]) -> str | None:
    recall = rm.get("persistent_memory_recall")
    if not isinstance(recall, dict):
        return None
    mem = memory.get(str(recall.get("memory_key"))) or memory.get(str(recall.get("person")))
    if not isinstance(mem, dict):
        return None

    memory_class = recall.get("memory_class")
    if memory_class == "prior_result" and mem.get("last_success_target"):
        return str(mem["last_success_target"])
    if memory_class == "standing_constraint" and mem.get("approval_channel"):
        return str(mem["approval_channel"])

    prompt = str(task.get("prompt", ""))
    if any(w in prompt for w in _LIGHTING_WORDS) and mem.get("dusk_room"):
        return str(mem["dusk_room"])
    if any(w in prompt for w in _HEALTH_WORDS) and mem.get("health_channel"):
        return str(mem["health_channel"])
    if mem.get("preferred_channel"):
        return str(mem["preferred_channel"])
    if mem.get("health_channel"):
        return str(mem["health_channel"])
    if mem.get("approval_channel"):
        return str(mem["approval_channel"])
    return None


# --------------------------------------------------------------------------
# Control decision helpers
# --------------------------------------------------------------------------
_CONSENT_NEGATIVE = ("revoked", "withdraw", "denied", "철회", "거부")

# The screening pool introduces record values never seen in dev for fields the
# control ladder already depends on (e.g. dispatch_authority_check ==
# "local_authority_confirmed", share_boundary_update ==
# "redacted_after_selection_boundary"). Their co-occurrence with the other
# route-family fields matches the known value they stand in for (same
# share_boundary_update / route_candidate_snapshot distribution as their
# sibling), so they are treated as aliases rather than left to silently fall
# through to a worse generic branch. Any value that is still unrecognized
# after alias resolution is mapped to the most cautious *known* state for
# that field, rather than falling through silently -- an unfamiliar state is
# itself a signal that nothing has been verified yet.
_DISPATCH_ALIASES = {"local_authority_confirmed": "internal_binding_confirmed"}
_KNOWN_DISPATCH = {"user_binding_pending", "authority_incomplete", "internal_binding_confirmed"}
_DISPATCH_UNKNOWN_DEFAULT = "authority_incomplete"

_BOUNDARY_ALIASES = {"redacted_after_selection_boundary": "redacted_external_boundary"}
_KNOWN_BOUNDARY = {"local_update_boundary", "redacted_external_boundary", "dispatch_blocked_until_binding"}
_BOUNDARY_UNKNOWN_DEFAULT = "redacted_external_boundary"


def _dispatch_state(rm: dict[str, Any]) -> str | None:
    value = rm.get("dispatch_authority_check")
    if value is None:
        return None
    value = _DISPATCH_ALIASES.get(value, value)
    return value if value in _KNOWN_DISPATCH else _DISPATCH_UNKNOWN_DEFAULT


def _boundary_state(rm: dict[str, Any]) -> str | None:
    value = rm.get("share_boundary_update")
    if value is None:
        return None
    value = _BOUNDARY_ALIASES.get(value, value)
    return value if value in _KNOWN_BOUNDARY else _BOUNDARY_UNKNOWN_DEFAULT


# Route-resolution control table.
#
# (dispatch_authority_check, share_boundary_update, ambiguous_target,
# ambiguous_focal) jointly describe how settled a dispatch route is once any
# live corrective clause has already been ruled out (classify_task_override
# returned GENERIC). Each entry below was derived by a controlled comparison
# within that GENERIC subset of dev: holding all four fields fixed, does the
# reference control agree across independently-drawn tasks (different
# task_id, focal object, and domain)?
#
#   tier="matched"  - >=2 independent dev tasks agree with no exception found
#   tier="single"   - exactly 1 dev task observed; not yet replicated
#
# No cell here was accepted while a same-key contradiction existed anywhere
# in the GENERIC subset; there were none. Cells absent from this table (no
# GENERIC dev task ever exhibited that exact combination) fall through to
# the coarser, single-field defaults in decide_control instead of guessing a
# combination-specific answer with zero support.
@dataclasses.dataclass(frozen=True)
class _ControlRule:
    control: str
    tier: str
    evidence: str


_CONTROL_TABLE: dict[tuple[str, str, str | None, bool], _ControlRule] = {
    ("authority_incomplete", "dispatch_blocked_until_binding", "approved_channel_or_visible_recipient", False):
        _ControlRule("hold", "matched", "dev 208d83525bfe + 503d60ca6a8b (both guardrail_ladder_signal present)"),
    ("authority_incomplete", "dispatch_blocked_until_binding", None, True):
        _ControlRule("ask", "matched", "dev x4: 1d36a1e14d07, 681d2e291ea5, e62ca24413a8, 0ad44d955594"),
    ("internal_binding_confirmed", "local_update_boundary", "surface_recipient_and_resolved_target_both_recent", False):
        _ControlRule("amend", "matched", "dev 25d2f58cdc0b + 8b4bcd0d1a7d"),
    ("internal_binding_confirmed", "local_update_boundary", "stored_channel_or_visible_recipient", False):
        _ControlRule("amend", "matched", "dev a7f2a443f654 + 7efad6a5e982"),
    ("internal_binding_confirmed", "local_update_boundary", None, True):
        _ControlRule("proceed", "matched", "dev b0696e0a0b55 + d2a3fd50f334"),
    ("internal_binding_confirmed", "local_update_boundary", "approved_channel_or_visible_recipient", False):
        _ControlRule("ask", "single", "dev 0a50781a4b36 (guardrail_ladder_signal present; unreplicated)"),
    ("internal_binding_confirmed", "redacted_external_boundary", "approved_channel_or_visible_recipient", False):
        _ControlRule("proceed", "matched", "dev 2b6c7dc70c0b + 1d6606209a76"),
    ("internal_binding_confirmed", "redacted_external_boundary", None, True):
        _ControlRule("amend", "matched", "dev 8003c2e5b525 + 20a0410a686c"),
    ("internal_binding_confirmed", "redacted_external_boundary", "stored_channel_or_visible_recipient", False):
        _ControlRule("ask", "single", "dev 511b1dc0b84d (unreplicated)"),
    ("internal_binding_confirmed", "redacted_external_boundary", "surface_recipient_and_resolved_target_both_recent", False):
        _ControlRule("ask", "single", "dev a976a641dd5a (unreplicated)"),
    ("user_binding_pending", "dispatch_blocked_until_binding", "approved_channel_or_visible_recipient", False):
        _ControlRule("hold", "single", "dev 022985565adb (unreplicated, but dispatch==user_binding_pending alone is separately confirmed to always hold)"),
    ("user_binding_pending", "dispatch_blocked_until_binding", None, True):
        _ControlRule("hold", "single", "dev 0ab2e0715082 (unreplicated, same note as above)"),
}


def _lookup_control_table(dispatch: str | None, boundary: str | None, ambiguous_target: str | None, ambiguous_focal: bool) -> _ControlRule | None:
    if dispatch is None or boundary is None:
        return None
    return _CONTROL_TABLE.get((dispatch, boundary, ambiguous_target, ambiguous_focal))


# --------------------------------------------------------------------------
# content_scope / plan_events helpers
# --------------------------------------------------------------------------
LOCAL_UPDATE_SCOPE = {
    "mode": "status_only",
    "allowed_fields": ["status"],
    "excluded_fields": ["raw_quote", "location", "numeric_value"],
    "requires_user_confirmation": False,
}

# content_scope.excluded_fields is scored against the reference by field-name
# F1, so it must keep raw field names (raw_quote/rrn/location/...). The
# plan_events "remove" arg, by contrast, is scored against a closed public
# ontology -- a raw field name like "doctor_note"/"card_number"/"name" isn't
# a member of that ontology and would silently score zero. Route it through
# the one field name that *is* itself a valid public value when present, and
# fall back to the generic "sensitive_fields" bucket (also a valid public
# value) rather than emitting an arbitrary field name.
_PLAN_SAFE_REMOVE_VALUES = ("raw_quote", "rrn", "location", "numeric_value")


def _plan_remove_value(excluded_fields: list[str] | None) -> str:
    for field in excluded_fields or []:
        if field in _PLAN_SAFE_REMOVE_VALUES:
            return field
    return "sensitive_fields" if excluded_fields else "raw_quote"


# --------------------------------------------------------------------------
# FinalHarness -- same shape as the baseline notebook's skeleton:
# update_session_memory / choose_focal / infer_target / decide_control /
# build_content_scope / build_policy / build_plan_events are all bound
# methods, calling out to the module-level helpers above for the parts that
# don't need instance state.
# --------------------------------------------------------------------------
class FinalHarness:
    def __init__(self) -> None:
        self.slm = FixedSLMClient()
        self.memory: dict[str, Any] = {}

    def prepare(self, tasks: list[dict[str, Any]]) -> None:
        self.memory.clear()

    def answer_task(self, task: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
        evidence = self.slm.summarize_task(task)
        self.update_session_memory(task, session, evidence)

        focal = self.choose_focal(task, session, evidence)
        focal_id = str(focal.get("id") or "")
        target = self.infer_target(task, focal, session, evidence)
        control = self.decide_control(task, focal, target, evidence)
        content_scope = self.build_content_scope(task, focal, target, control, evidence)
        policy = self.build_policy(task, focal, target, control, evidence)
        plan_events = self.build_plan_events(task, focal_id, target, control, content_scope, policy)

        session["last_focal_id"] = focal_id
        session["last_target"] = target
        session["last_control"] = control

        return {
            "focal_id": focal_id,
            "target": target,
            "control": control,
            "content_scope": content_scope,
            "policy": policy,
            "plan_events": plan_events,
        }

    def update_session_memory(self, task: dict[str, Any], session: dict[str, Any], evidence: dict[str, Any]) -> None:
        for record in records_of(task):
            if record.get("type") == "persistent_memory_write" and isinstance(record.get("value"), dict):
                value = record["value"]
                memory_key = str(value.get("memory_key") or "")
                person = str(value.get("person") or "")
                if memory_key:
                    self.memory[memory_key] = value
                if person:
                    self.memory[person] = value
        session["last_evidence"] = evidence

    def choose_focal(self, task: dict[str, Any], session: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        objects = objects_of(task)
        if not objects:
            return {}
        rm = record_map(records_of(task))
        object_by_ref = _object_by_ref(objects)

        # 1) A structured marker chain (focal_marker_refs + focal_resolution_trace)
        #    is documented as authoritative when present: follow it exactly.
        via_marker = _resolve_focal_via_marker_chain(rm, object_by_ref)
        if via_marker is not None:
            return via_marker

        # 2) Otherwise, visible_history may narrate an ordinal-in-list
        #    correction ("candidates were A, B, C; only the second is
        #    confirmed") -- parse that structure rather than the raw digits.
        via_history = _resolve_focal_via_history_text(task, object_by_ref)
        if via_history is not None:
            return via_history

        # 3) A record value directly naming an object id.
        object_by_id = {str(o.get("id")): o for o in objects}
        for record in reversed(records_of(task)):
            value = record.get("value")
            candidates: list[str] = []
            if isinstance(value, str):
                candidates.append(value)
            elif isinstance(value, dict):
                candidates.extend(str(v) for v in value.values() if isinstance(v, str))
            for candidate in candidates:
                if candidate in object_by_id:
                    return object_by_id[candidate]

        # 4) A ref_code literally mentioned anywhere in the visible history.
        history_text = full_task_text(task).lower()
        for obj in objects:
            ref_code = str((obj.get("attrs") or {}).get("ref_code") or "").lower()
            if ref_code and ref_code in history_text:
                return obj

        # 5) Last resort: token overlap between the prompt and object attrs.
        prompt_tokens = {tok for tok in re.findall(r"[A-Za-z0-9가-힣_]+", str(task.get("prompt", "")).lower()) if len(tok) >= 2}
        best = objects[0]
        best_score = -1
        for obj in objects:
            score = sum(1 for tok in prompt_tokens if tok in object_text(obj))
            if score > best_score:
                best, best_score = obj, score
        return best

    def infer_target(self, task: dict[str, Any], focal: dict[str, Any], session: dict[str, Any], evidence: dict[str, Any]) -> str:
        override = classify_task_override(task)
        if override == "LOCAL_ONLY":
            return "memory_store"
        if override in ("ASK", "HOLD"):
            return "user"

        rm = record_map(records_of(task))
        if "persistent_memory_write" in rm:
            return "memory_store"

        # A route confirmed in an earlier turn can be explicitly superseded.
        changed = rm.get("target_changed_after_turn")
        if isinstance(changed, str) and changed and changed not in ("prior_success_route_superseded",):
            return changed

        resolved = _resolved_target_value(rm)
        if resolved:
            return resolved

        from_memory = _target_from_memory_recall(task, rm, self.memory)
        if from_memory:
            return from_memory

        attrs = focal.get("attrs") or {}
        for key in ("recipient", "target", "channel", "app", "merchant", "name"):
            if attrs.get(key):
                return str(attrs[key])
        return str(session.get("last_target") or "user")

    def decide_control(self, task: dict[str, Any], focal: dict[str, Any], target: str, evidence: dict[str, Any]) -> str:
        override = classify_task_override(task)
        rm = record_map(records_of(task))

        if override == "LOCAL_ONLY":
            return "proceed"
        if override == "ASK":
            return "ask"
        if override == "HOLD":
            return "hold"
        if override == "AMEND":
            return "amend"

        if "persistent_memory_write" in rm:
            return "proceed"

        # Hard safety stops.
        if "security_alert" in rm or "safety_mode" in rm or "privacy_guard" in rm:
            return "hold"
        consent_val = text_of(rm.get("consent")).lower()
        if consent_val and any(w in consent_val for w in _CONSENT_NEGATIVE):
            return "hold"

        dispatch = _dispatch_state(rm)
        boundary = _boundary_state(rm)
        external_policy = rm.get("external_share_policy")
        ambiguous_target = rm.get("ambiguous_target")
        ambiguous_focal = bool(rm.get("ambiguous_focal"))

        # 1) Exact, controlled-comparison-backed combination -> use it
        #    verbatim, whether it's "matched" (replicated) or "single"
        #    (observed once).
        rule = _lookup_control_table(dispatch, boundary, ambiguous_target, ambiguous_focal)
        if rule is not None:
            return rule.control

        # 2) No exact combination on file: fall back to whichever single
        #    field is independently well-supported on its own.
        #    dispatch_authority_check == user_binding_pending is confirmed to
        #    mean "hold" regardless of the other fields.
        if dispatch == "user_binding_pending":
            return "hold"
        if dispatch == "authority_incomplete":
            return "ask"
        if boundary == "dispatch_blocked_until_binding":
            return "ask"

        if external_policy in ("raw_quote_forbidden", "raw_sensitive_forbidden", "summary_only_allowed"):
            return "amend"
        if external_policy == "doctor_note_forbidden":
            return "hold"
        if boundary == "redacted_external_boundary":
            return "amend"
        if evidence.get("requires_redaction"):
            return "amend"
        if ambiguous_target or ambiguous_focal:
            return "ask"

        # No structured route/ambiguity/policy signal fired at all: fall
        # back to the session's overall share posture as the deciding factor.
        if rm.get("session_share_policy") == "strict":
            return "amend"
        return "proceed"

    def build_content_scope(self, task: dict[str, Any], focal: dict[str, Any], target: str, control: str, evidence: dict[str, Any]) -> dict[str, Any]:
        rm = record_map(records_of(task))
        boundary = _boundary_state(rm)

        if control == "proceed" and (target == "memory_store" or boundary == "local_update_boundary"):
            return dict(LOCAL_UPDATE_SCOPE)

        sensitive = sensitive_fields_of(focal)

        if control == "hold":
            return {"mode": "none", "allowed_fields": [], "excluded_fields": [], "requires_user_confirmation": False}

        if control == "ask":
            excluded = sorted(sensitive) if sensitive else ["raw_quote"]
            return {"mode": "summary", "allowed_fields": ["status"], "excluded_fields": excluded, "requires_user_confirmation": True}

        if control == "amend":
            excluded = sorted(sensitive) if sensitive else ["raw_quote"]
            needs_confirm = bool(rm.get("ambiguous_target"))
            return {"mode": "redacted", "allowed_fields": ["summary"], "excluded_fields": excluded, "requires_user_confirmation": needs_confirm}

        # proceed to an external target already confirmed as an approved,
        # trusted channel: nothing needs to be withheld.
        if rm.get("ambiguous_target") == "approved_channel_or_visible_recipient" and boundary == "redacted_external_boundary":
            return {"mode": "raw", "allowed_fields": ["summary", "title"], "excluded_fields": [], "requires_user_confirmation": False}

        excluded = sorted(sensitive) if sensitive else ["raw_quote"]
        return {"mode": "summary", "allowed_fields": ["summary", "title", "status"], "excluded_fields": excluded, "requires_user_confirmation": False}

    def build_policy(self, task: dict[str, Any], focal: dict[str, Any], target: str, control: str, evidence: dict[str, Any]) -> dict[str, Any]:
        rm = record_map(records_of(task))
        flags: set[str] = set(evidence.get("risk_flags", []))
        violations: set[str] = set()

        if rm.get("session_share_policy") == "strict":
            flags.add("strict_share_policy")
        if rm.get("ambiguous_target"):
            flags.add("target_ambiguity")
        if rm.get("ambiguous_focal"):
            flags.add("ambiguous_focal")
        if sensitive_fields_of(focal):
            flags.add("sensitive_content")

        consent_val = text_of(rm.get("consent")).lower()
        consent_revoked = bool(consent_val) and any(w in consent_val for w in _CONSENT_NEGATIVE)
        # Note: "consent_revoked" itself is never the reference violations
        # value -- a revoked consent that blocks the request shows up as
        # precondition_changed_ignored (handled in the hold branch below);
        # if the request is instead confined to a local-only update, no
        # violation is recorded at all (nothing was actually shared against
        # the revoked consent).

        requires_confirmation = control == "ask"

        dispatch = _dispatch_state(rm)
        boundary = _boundary_state(rm)
        if control == "proceed" and (target == "memory_store" or boundary == "local_update_boundary"):
            flags.add("local_only")
            if dispatch == "internal_binding_confirmed":
                flags.add("precondition_changed")
            if target not in ("memory_store", "user"):
                flags.add("external_share")
            requires_confirmation = bool(rm.get("ambiguous_target"))

        if control == "hold":
            if dispatch in ("user_binding_pending", "authority_incomplete") or "focal_resolution_trace" in rm or consent_revoked:
                flags.add("precondition_invalidated")
                violations.add("precondition_changed_ignored")
            if "security_alert" in rm:
                flags.add("security_alert")
            if "safety_mode" in rm or consent_revoked:
                flags.add("safety")
            if target not in ("memory_store", "user"):
                flags.add("external_share")
            requires_confirmation = False

        if control == "amend":
            flags.add("minimal_disclosure")
            if target not in ("memory_store", "user"):
                flags.add("external_share")
            requires_confirmation = bool(rm.get("ambiguous_target"))

        if control == "ask":
            flags.add("clarification_required")
            if dispatch == "internal_binding_confirmed":
                flags.add("precondition_changed")

        return {
            "risk_flags": sorted(flags),
            "violations": sorted(violations),
            "requires_confirmation": requires_confirmation,
        }

    def build_plan_events(self, task: dict[str, Any], focal_id: str, target: str, control: str, scope: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
        if target == "memory_store" and control == "proceed":
            return [
                {"verb": "read", "target": focal_id, "args": {"purpose": "local_update"}},
                {"verb": "verify", "target": "share_boundary_update", "args": {"scope": "local_update"}},
                {"verb": "update", "target": focal_id, "args": {"state": "local_status_only"}},
            ]

        if control == "hold":
            reason = "precondition_invalidated" if "precondition_invalidated" in policy.get("risk_flags", []) else "strict_policy_block"
            if "security_alert" in policy.get("risk_flags", []):
                reason = "security_alert"
            return [
                {"verb": "read", "target": focal_id, "args": {"purpose": reason if reason != "strict_policy_block" else "invalidated_precondition"}},
                {"verb": "guard", "target": focal_id, "args": {"reason": reason}},
            ]

        if control == "ask":
            flags = policy.get("risk_flags", [])
            # An ask that challenges a route that was already confirmed
            # reads as "please reconfirm a precondition", not "please
            # resolve a fresh ambiguity" -- different public-ontology reasons.
            if "precondition_changed" in flags:
                purpose, reason = "clarify_precondition", "precondition_changed"
            elif "target_ambiguity" in flags:
                purpose = reason = "route_resolution_required"
            else:
                purpose = reason = "clarification_required"
            return [
                {"verb": "read", "target": focal_id, "args": {"purpose": purpose}},
                {"verb": "clarify", "target": "user", "args": {"reason": reason}},
            ]

        events = [{"verb": "read", "target": focal_id, "args": {"purpose": "minimal_disclosure" if control == "amend" else "inspect_context"}}]
        if control == "amend" or scope.get("mode") == "redacted":
            events.append({"verb": "redact", "target": focal_id, "args": {"remove": _plan_remove_value(scope.get("excluded_fields"))}})
        elif scope.get("mode") in ("summary", "status_only"):
            events.append({"verb": "summarize", "target": focal_id, "args": {"mode": scope.get("mode")}})
        events.append({"verb": "dispatch", "target": target, "args": {"scope": scope.get("mode")}})
        return events


# --------------------------------------------------------------------------
# Local runner (same shape as the baseline notebook's runner section)
# --------------------------------------------------------------------------
def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


REMOVED_SCORING_KEYS = ("expected_events", "answer")


def participant_task_view(task: dict[str, Any]) -> dict[str, Any]:
    view = json.loads(json.dumps(task, ensure_ascii=False))
    for key in list(view):
        if (
            key in REMOVED_SCORING_KEYS
            or key.startswith("expected_")
            or key.endswith("_brief")
            or key.endswith("_notes")
            or key.endswith("_rubric")
            or key.endswith("_keywords")
            or key.endswith("_tags")
        ):
            view.pop(key, None)
    return view


def answer_one(harness: Any, task: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    for name in ("answer_task", "solve_task", "solve"):
        fn = getattr(harness, name, None)
        if callable(fn):
            answer = fn(task, session)
            if not isinstance(answer, dict):
                raise RuntimeError(f"{name} returned non-object for task {task.get('id')}")
            return answer
    raise RuntimeError("harness must expose answer_task(task, session), solve_task(...), or solve(...)")


def run_harness(tasks: list[dict[str, Any]], harness_cls: type = FinalHarness, *, harness_name: str = "sogang_harness") -> dict[str, Any]:
    ordered = sorted(tasks, key=lambda t: (str(t.get("session_id", "")), int(t.get("turn_index", 0)), str(t.get("id", ""))))
    harness = harness_cls()
    prepare = getattr(harness, "prepare", None)
    if callable(prepare):
        prepare([])

    sessions: dict[str, dict[str, Any]] = {}
    answers: dict[str, dict[str, Any]] = {}
    for task in ordered:
        sid = str(task.get("session_id", ""))
        session = sessions.setdefault(sid, {})
        answers[str(task["id"])] = answer_one(harness, participant_task_view(task), session)

    return {
        "schema": SUBMISSION_SCHEMA,
        "meta": {
            "harness_name": harness_name,
            "uses_external_api": False,
            "fixed_slm_policy": "local_fixed_slm_only",
            "model_id": FIXED_SLM_ID,
            "temperature": 0.0,
            "seed": 42,
        },
        "answers": answers,
    }


def write_submission_csv(payload: dict[str, Any], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["submission"])
        writer.writerow([json.dumps(payload, ensure_ascii=False, separators=(",", ":"))])


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if mode == "dev":
        from scorer import score_dev_submission, validate_payload

        dev_tasks = load_jsonl(DATA_DIR / "dev_tasks.jsonl")
        dev_answers = load_json(DATA_DIR / "dev_answers.json")
        payload = run_harness(dev_tasks, FinalHarness, harness_name="sogang_harness_dev")
        validate_payload(payload, {str(t["id"]) for t in dev_tasks})
        report = score_dev_submission(payload, dev_answers)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif mode == "submit":
        from scorer import validate_payload

        screening_tasks = load_jsonl(DATA_DIR / "screening_tasks.jsonl")
        payload = run_harness(screening_tasks, FinalHarness, harness_name="sogang_harness")
        validate_payload(payload, {str(t["id"]) for t in screening_tasks})
        out_path = ROOT / "submission.csv"
        write_submission_csv(payload, out_path)
        print("wrote:", out_path)
        print("answers:", len(payload["answers"]))
    else:
        raise SystemExit(f"unknown mode: {mode}")


if __name__ == "__main__":
    main()
