"""Structured constraints, not an NLP parser or source authentication service."""
from datetime import date, datetime, timedelta, timezone
from .engine import ValidationError, timestamp

TYPES = {"actor_execution": "execution", "holdings": "holdings", "plan": "plan", "business": "business"}
STAGES = {"execution": "executed", "holdings": "holdings", "plan": "planned", "business": "business", "indirect": "indirect"}


def analyze(data):
    if not isinstance(data, dict):
        raise ValidationError("叙事输入须为对象")
    cutoff = timestamp(data.get("as_of", ""))
    replay_mode = data.get("replay_mode", "confirmed_state")
    if replay_mode not in {"confirmed_state", "public_information"}:
        raise ValidationError("replay_mode为confirmed_state或public_information")
    claims, records = data.get("claims", []), data.get("evidence", [])
    if not isinstance(claims, list) or not isinstance(records, list):
        raise ValidationError("claims/evidence须为列表")
    available, excluded, gaps = [], [], []
    ids = set()
    for evidence in records:
        if not isinstance(evidence, dict) or not evidence.get("id") or evidence["id"] in ids:
            raise ValidationError("证据ID必填且唯一")
        ids.add(evidence["id"])
        e = dict(evidence)
        reason = None
        try:
            usable_at = timestamp(e.get("available_at", ""))
        except ValidationError:
            reason = "证据可用时间未知，不能用于时点确认"
        else:
            if usable_at > cutoff:
                reason = "截止时刻之后才可用"
        if reason is None and e.get("verified") is not True:
            reason = "仅有转述或未完成原文核验"
        if reason is None:
            try:
                verified_at = timestamp(e.get("verified_at", ""))
                if verified_at > cutoff:
                    if replay_mode == "confirmed_state":
                        reason = "截止时刻之后才完成核验，不能改写当时已确认结论"
                    else:
                        e["retrospectively_verified"] = True
            except ValidationError:
                reason = "核验时间未知，不能声称当时已确认"
        if reason is None and (not e.get("source") or not e.get("quote")):
            reason = "来源或原句缺失"
        if reason is None and (not e.get("actor") or not e.get("scope")):
            reason = "主体或范围不明确"
        if reason is None and STAGES.get(e.get("source_type")) != e.get("stage"):
            reason = "来源类别与行为阶段不一致"
        if reason is None:
            try:
                start = date.fromisoformat(e.get("period_start", ""))
                end = date.fromisoformat(e.get("period_end", ""))
                if start > end:
                    raise ValueError()
                if e["source_type"] != "plan" and end > datetime.fromisoformat(usable_at).astimezone(timezone(timedelta(hours=8))).date():
                    reason = "执行/持仓/业务期间晚于披露时间，不能确认尚未发生的事实"
            except (ValueError, TypeError):
                reason = "行为期间未知或不合法"
        if reason:
            excluded.append({"id": e["id"], "reason": reason})
        else:
            available.append(e)
    superseded = set()
    by_id = {e["id"]: e for e in available}
    for e in available:
        replaces = e.get("supersedes", [])
        if not isinstance(replaces, list):
            raise ValidationError("supersedes须为证据ID列表")
        for old_id in replaces:
            old = by_id.get(old_id)
            if not old or any(e[k] != old[k] for k in ["actor", "scope", "source_type"]) or timestamp(e["available_at"]) <= timestamp(old["available_at"]):
                raise ValidationError("更正只可替代同主体、范围、类型且更早的可用证据")
            superseded.add(old_id)
    effective = [e for e in available if e["id"] not in superseded]
    results = []
    seen_claims = set()
    for claim in claims:
        if not isinstance(claim, dict) or not claim.get("id") or claim["id"] in seen_claims or claim.get("type") not in TYPES:
            raise ValidationError("主张ID须唯一，type为actor_execution/holdings/plan/business")
        seen_claims.add(claim["id"])
        matches, limited, conflicts = [], [], []
        for e in effective:
            if e["actor"] != claim.get("actor"):
                continue
            if e["scope"] != claim.get("scope"):
                limited.append({"id": e["id"], "reason": "证据范围与具体主张不同，不能扩写"})
                continue
            if e["source_type"] != TYPES[claim["type"]]:
                limited.append({"id": e["id"], "reason": "计划、执行、持仓或业务证据不能相互替代"})
                continue
            if claim.get("day"):
                if e["period_start"] != claim["day"] or e["period_end"] != claim["day"]:
                    limited.append({"id": e["id"], "reason": "区间证据不证明指定单日行为"})
                    continue
            if claim.get("action") and e.get("action") != claim["action"]:
                limited.append({"id": e["id"], "reason": "具体交易/业务动作缺失或不匹配"})
                continue
            if claim.get("amount_cny") is not None:
                if e.get("amount_cny") is None:
                    limited.append({"id": e["id"], "reason": "原文未披露对应金额"})
                    continue
                if e["amount_cny"] != claim["amount_cny"]:
                    conflicts.append({"id": e["id"], "reason": "同范围金额与主张不同"})
                    continue
            if e.get("supports") is False:
                conflicts.append({"id": e["id"], "reason": "原文对该具体主张给出反证"})
                continue
            matches.append(e["id"])
        retrospective = any(e.get("retrospectively_verified") and e["id"] in matches for e in effective)
        status = "存在冲突，需核对" if conflicts else "当时公开资料在范围内支持（事后核验）" if matches and retrospective else "在证据范围内有支持" if matches else "证据不足，不能确认"
        results.append({"claim_id": claim["id"], "claim": claim, "status": status, "support_ids": matches, "limited": limited, "conflicts": conflicts})
    if not records:
        gaps.append("没有原始证据，仅能讨论可能解释，不能确认账户身份或执行")
    if excluded:
        gaps.append("部分证据因时点、来源或阶段条件不符，未用于确认")
    return {"as_of": cutoff, "replay_mode": replay_mode, "simulation": data.get("simulation") is True, "scenario": data.get("scenario", ""), "claims": results, "available_evidence": available, "superseded_evidence_ids": sorted(superseded), "excluded_evidence": excluded, "gaps": gaps, "limitations": ["这是结构化边界检查，不自动理解原文、不认证来源或verified标记", "仍须人工核实原句含义、动作、范围、日期和金额口径", "公开信息回放中的事后核验不等于当时系统已审核，不恢复当时决策", "合成情景结果不代表真实行情或识别准确率"]}
