"""Small offline CLI scenario index, reusing the existing demo and 44 checks."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys


def run(output):
    out = Path(output).resolve()
    if out.exists():
        raise FileExistsError("Scenario output already exists; choose a new directory")
    out.mkdir(parents=True)
    cli = Path(__file__).with_name("run.py")
    commands, cases = [], []

    def invoke(*args, code=0):
        command = [sys.executable, "-X", "utf8", str(cli), *map(str, args)]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        commands.append({"command": command, "returncode": result.returncode,
                         "stdout": result.stdout, "stderr": result.stderr})
        assert result.returncode == code, commands[-1]
        return json.loads(result.stdout) if code == 0 else result.stderr

    def snapshot(paths):
        return json.loads(Path(paths["snapshot"]).read_text(encoding="utf-8"))

    def case(name, inputs, expected, actual, method):
        cases.append({"name": name, "teaching": True, "inputs": inputs,
                      "expected": expected, "actual": actual, "method": method, "passed": True})

    checks = invoke("self-test", "--out-dir", out / "existing-checks")
    assert checks["passed"] == 44 and checks["failed"] == 0 and checks["errors"] == 0
    db = out / "teaching.sqlite3"
    paths = invoke("demo", "--db", db, "--out-dir", out / "baseline")
    baseline = snapshot(paths)
    frozen = Path(paths["snapshot"]).read_bytes()
    frozen_hash = hashlib.sha256(frozen).hexdigest()
    # Preserve the exact generated source CSVs, rather than invent a second demo dataset.
    with sqlite3.connect(db) as connection:
        batches = connection.execute("SELECT kind,source,raw FROM batch").fetchall()
    inputs = out / "inputs"
    inputs.mkdir()
    for kind, source, raw in batches:
        (inputs / f"demo-{kind}.csv").write_text(raw, encoding="utf-8")
    card = next(c for c in baseline["cards"] if c["instrument"] == "SSE:510300")
    expected_proxy = .4 * .04 + (.6 / 9) * (7 * -.002 + 2 * .001)
    assert abs(card["breadth"] - .3) < 1e-12
    assert abs(card["index_return_proxy"] - expected_proxy) < 1e-12
    assert card["index_return_proxy"] > 0 and card["median_return"] < 0
    case("指数贡献代理上涨、样本多数下跌", ["inputs/demo-breadth.csv"],
         {"sample_up_fraction": .3, "weighted_proxy": expected_proxy, "median": -.002},
         {k: card[k] for k in ["breadth", "index_return_proxy", "median_return", "structure"]},
         "10只中3涨7跌；权重0.4×4%+(0.6/9)×(7×-0.2%+2×0.1%)=1.52%；仅样本代理")
    assert card["amount_percentile"] == 100 and card["net_share_change"] == -1_000_000
    assert card["identity"].startswith("未知")
    financing = baseline["financing"][0]
    assert financing["value"] == 1_000_000_000
    case("成交异常、份额减少、融资增加，主体未知", ["inputs/demo-market.csv", "inputs/demo-fund.csv", "inputs/demo-financing.csv"],
         {"percentile": 100, "share_change": -1_000_000, "financing_activity_cny": 1_000_000_000, "identity": "未知"},
         {"card": card, "financing": financing},
         "当前成交高于179个先前记录；相邻份额差-100万；80亿买入-70亿偿还=10亿，观察池不能推断账户")

    # Three cumulative versions of the same event, plus its separate plan ceiling.
    def evidence(amount, published, **extra):
        data = dict(event_id="synthetic-buyback", actor="教学公司", scope="本公司股份",
                    kind="回购", stage="进展", level="E3", published_at=published,
                    period_start="2026-10-07", period_end="2026-10-07",
                    quote=f"合成公告：累计回购{amount}元。", source="教学材料，非真实公告", location="教学原句",
                    cumulative_amount_cny=amount)
        data.update(extra)
        return data

    def record(label, payload):
        file = inputs / f"{label}.json"
        file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return invoke("record-evidence", "--db", db, "--demo", "--input", file)

    record("plan", evidence(None, "2026-10-07T17:00:00+08:00", stage="计划", level="E2", plan_max_cny=1_000_000_000))
    old = record("execution-old", evidence(200_000_000, "2026-10-07T18:00:00+08:00"))
    record("execution-correction", evidence(20_000_000, "2026-10-07T19:00:00+08:00", corrects_evidence_id=old["id"]))
    record("execution-next", evidence(50_000_000, "2026-10-07T20:00:00+08:00"))
    event_paths = invoke("assess", "--db", db, "--demo", "--as-of", "2026-10-09T22:00:00+08:00", "--out-dir", out / "event")
    event = snapshot(event_paths)["evidence"][0]
    assert event["cumulative_amount_cny"] == 50_000_000 and event["increment_amount_cny"] == 30_000_000
    assert event["execution_confirmed"] is False  # CLI-created evidence is pending review.
    with sqlite3.connect(db) as connection:
        raw_events = [json.loads(r[0]) for r in connection.execute("SELECT data FROM evidence ORDER BY id")]
    assert raw_events[2]["revision_adjustment_cny"] == -180_000_000
    assert raw_events[2]["increment_amount_cny"] is None
    story = {"simulation": True, "as_of": "2026-10-09T18:00:00+08:00",
             "claims": [{"id": "executed", "type": "actor_execution", "actor": "教学公司", "scope": "本公司股份", "action": "buy", "amount_cny": 50_000_000}],
             "evidence": [{"id": "plan", "source_type": "plan", "stage": "planned", "actor": "教学公司", "scope": "本公司股份",
                           "period_start": "2026-10-07", "period_end": "2026-10-07", "available_at": "2026-10-07T17:00:00+08:00",
                           "verified_at": "2026-10-07T17:10:00+08:00", "verified": True, "source": "教学计划", "quote": "教学：拟回购不超过10亿元。"}]}
    plan_file = inputs / "plan-only-story.json"
    plan_file.write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
    plan_result = snapshot(invoke("narrative", "--input", plan_file, "--out-dir", out / "plan-story"))
    assert plan_result["claims"][0]["status"] == "证据不足，不能确认"
    story["evidence"].append(dict(story["evidence"][0], id="executed", source_type="execution", stage="executed",
                                  action="buy", amount_cny=50_000_000, source="教学执行披露", quote="教学：已累计回购5000万元。"))
    execution_file = inputs / "execution-story.json"
    execution_file.write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
    execution_result = snapshot(invoke("narrative", "--input", execution_file, "--out-dir", out / "execution-story"))
    assert execution_result["claims"][0]["support_ids"] == ["executed"]
    case("计划上限、累计更正与执行审核分开", ["inputs/plan.json", "inputs/execution-old.json", "inputs/execution-correction.json", "inputs/execution-next.json", "inputs/plan-only-story.json", "inputs/execution-story.json"],
         {"latest_cumulative": 50_000_000, "next_increment": 30_000_000, "correction": -180_000_000, "execution_confirmed": False},
         {"latest": event, "versions": raw_events, "plan_only": plan_result, "explicit_execution": execution_result},
         "2亿元更正为0.2亿元是-1.8亿元修订，非卖出；后累计0.5亿减0.2亿=0.3亿；10亿计划非执行，待审核不确认")
    invalid = evidence(1, "2026-10-07T21:00:00+08:00", stage="计划", level="E3")
    bad_file = inputs / "invalid-plan-e3.json"
    bad_file.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
    before_count = len(raw_events)
    error = invoke("record-evidence", "--db", db, "--demo", "--input", bad_file, code=2)
    assert "E3" in error
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == before_count
    case("计划伪标执行拒绝且不污染证据", ["inputs/invalid-plan-e3.json"], {"exit": 2, "evidence_count": before_count},
         {"error": error, "evidence_count": before_count}, "阶段与E3约束；失败前后证据行数守恒")

    unknown_input = {"simulation": True, "as_of": "2026-10-09T18:00:00+08:00",
                     "claims": [{"id": "c", "type": "actor_execution", "actor": "教学公司", "scope": "本公司股份"}],
                     "evidence": [{"id": "unknown", "available_at": None}]}
    unknown_file = inputs / "unknown-time.json"
    unknown_file.write_text(json.dumps(unknown_input, ensure_ascii=False), encoding="utf-8")
    unknown = snapshot(invoke("narrative", "--input", unknown_file, "--out-dir", out / "unknown-time"))
    assert unknown["claims"][0]["status"] == "证据不足，不能确认"
    assert "可用时间未知" in unknown["excluded_evidence"][0]["reason"]
    case("未知可得时间不补当前时刻", ["inputs/unknown-time.json"], {"status": "证据不足，不能确认"}, unknown, "缺历史可得时点不能用于时点确认")

    market_raw = next(raw for kind, source, raw in batches if kind == "market")
    row = next(r for r in reversed(list(csv.DictReader(io.StringIO(market_raw)))) if r["instrument"] == "SSE:510300")
    row.update(open="9", high="10", low="8", close="9")
    conflict_file = inputs / "conflicting-market.csv"
    with conflict_file.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    invoke("import", "--db", db, "--demo", "--kind", "market", "--input", conflict_file, "--source", "另一教学来源")
    conflict = snapshot(invoke("assess", "--db", db, "--demo", "--as-of", baseline["as_of"], "--out-dir", out / "conflict"))
    issues = [i for i in conflict["quality_issues"] if i["kind"] == "market" and i["code"] == "G01"]
    assert issues
    affected = next(c for c in conflict["cards"] if c["instrument"] == "SSE:510300")
    assert affected["date"] < row["date"]  # Latest conflicting record is excluded; older date is explicit.
    invoke("replay", "--db", db, "--demo", "--run-id", baseline["run_id"], "--out-dir", out / "baseline")
    assert Path(paths["snapshot"]).read_bytes() == frozen
    case("来源冲突阻断当日输入、旧结果冻结", ["inputs/conflicting-market.csv"],
         {"quality_code": "G01", "latest_record_excluded": True, "frozen_sha256": frozen_hash},
         {"issues": issues, "affected_date": affected["date"], "frozen_sha256": hashlib.sha256(frozen).hexdigest()},
         "同证券/日期两个互异价格不能择一当当天事实；报告注明实际较早行情日，原run回放字节不变")
    manifest = {"simulation": True, "method_version": baseline["version"], "reused_checks": checks,
                "cases": cases, "commands": commands, "scope": "CLI reports and synthetic cases only; no real-source authentication"}
    (out / "scenario-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "scenario-index.md").write_text("# MarketLens教学情景\n\n全部为合成输入，不代表真实市场覆盖。\n\n" +
        "\n".join(f"- {c['name']}：通过；{c['method']}" for c in cases) +
        "\n\n复用44项原有约束检查；详细输入、预期、实际、命令和方法版本见scenario-manifest.json。\n", encoding="utf-8")
    print(json.dumps({"passed_cases": len(cases), "reused_checks": checks["passed"], "output": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    try:
        run(parser.parse_args().output)
    except FileExistsError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        sys.exit(2)
