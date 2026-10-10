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


def run(output, human=False):
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
    # Bounded CN follow-up: official conditions are documented, all payloads remain synthetic.
    quarterly = {"simulation": True, "scenario": "教学沪股通季末存量，公布时刻假设，非真实第五交易日计算",
                 "as_of": "2026-07-15T18:00:00+08:00",
                 "claims": [{"id": "stock", "type": "holdings", "actor": "沪股通投资者合计（教学）", "scope": "教学证券"},
                            {"id": "live-buy", "type": "actor_execution", "actor": "沪股通投资者合计（教学）", "scope": "教学证券", "action": "buy", "day": "2026-07-15"}],
                 "evidence": [{"id": "quarter-end", "source_type": "holdings", "stage": "holdings", "actor": "沪股通投资者合计（教学）", "scope": "教学证券",
                               "period_start": "2026-06-30", "period_end": "2026-06-30", "available_at": "2026-07-08T18:00:00+08:00",
                               "verified_at": "2026-07-08T18:10:00+08:00", "verified": True, "source": "合成季末持仓资料", "quote": "教学：截至6月末合计持有100万股，非7月15日买入披露。"}]}
    quarterly_file = inputs / "cn-quarterly-holdings.json"
    quarterly_file.write_text(json.dumps(quarterly, ensure_ascii=False, indent=2), encoding="utf-8")
    quarterly_result = snapshot(invoke("narrative", "--input", quarterly_file, "--out-dir", out / "cn-quarterly"))
    assert quarterly_result["claims"][0]["support_ids"] == ["quarter-end"]
    assert quarterly_result["claims"][1]["status"] == "证据不足，不能确认"
    bad_quarterly = json.loads(json.dumps(quarterly))
    bad_quarterly["evidence"][0]["stage"] = "executed"
    invalid_file = inputs / "cn-invalid-holdings-stage.json"
    invalid_file.write_text(json.dumps(bad_quarterly, ensure_ascii=False), encoding="utf-8")
    invalid_result = snapshot(invoke("narrative", "--input", invalid_file, "--out-dir", out / "cn-invalid-holdings"))
    assert "阶段不一致" in invalid_result["excluded_evidence"][0]["reason"]
    assert quarterly_file.read_text(encoding="utf-8") == json.dumps(quarterly, ensure_ascii=False, indent=2)
    case("季度北向持仓不推实时资金", ["inputs/cn-quarterly-holdings.json", "inputs/cn-invalid-holdings-stage.json"],
         {"holdings_supported": True, "live_buy_supported": False, "invalid_stage_excluded": True},
         {"normal": quarterly_result, "invalid": invalid_result},
         "上证发〔2024〕106号；季末存量与随后披露分开，持仓不等于7月15日交易，合计持仓不识别最终账户；不计算实际交易日")
    financing_file = inputs / "cn-financing-scopes.csv"
    with financing_file.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["date", "available_at", "universe", "buy_cny", "repay_cny", "balance_cny"])
        writer.writeheader()
        for scope, buy, repay in [("教学上交所当前标的明细池", 200_000_000, 300_000_000), ("教学沪深股票汇总池（可能重叠）", 500_000_000, 100_000_000)]:
            writer.writerow(dict(date=baseline["data_day"], available_at=baseline["data_day"]+"T21:00:00+08:00", universe=scope, buy_cny=buy, repay_cny=repay, balance_cny=""))
    invoke("import", "--db", db, "--demo", "--kind", "financing", "--input", financing_file, "--source", "CN教学不同融资覆盖池，人民币元")
    pools_result = snapshot(invoke("assess", "--db", db, "--demo", "--as-of", baseline["as_of"], "--out-dir", out / "cn-pools"))
    pools = {p["universe"]: p for p in pools_result["financing"]}
    assert pools["教学上交所当前标的明细池"]["value"] == -100_000_000
    assert pools["教学沪深股票汇总池（可能重叠）"]["value"] == 400_000_000
    assert all(p["balance"] is None for scope, p in pools.items() if scope.startswith("教学"))
    assert len(pools) == 3  # Includes the pre-existing demo pool, without combining overlapping scopes.
    assert "不同" in next(iter(pools.values()))["scope_note"]
    case("ETF与融资池不同覆盖不可相加", ["inputs/cn-financing-scopes.csv", "inputs/demo-fund.csv"],
         {"pool_a_cny": -100_000_000, "pool_b_cny": 400_000_000, "missing_balance": None, "separate_pools": 3},
         {"pools": pools_result["financing"], "fund_scope": pools_result["fund_aggregate"]["scope"]},
         "2亿-3亿=-1亿，5亿-1亿=4亿；范围可能重叠不合并，余额缺失不补零；融资偿还不是单纯卖出，ETF申赎估值不归因身份")
    business = {"simulation": True, "as_of": "2026-10-09T18:00:00+08:00",
                "claims": [{"id": "test", "type": "business", "actor": "教学机器人公司", "scope": "教学机器人项目", "action": "technical_test"},
                           {"id": "revenue", "type": "business", "actor": "教学机器人公司", "scope": "教学机器人项目", "action": "recognized_revenue", "amount_cny": 100_000_000},
                           {"id": "investor", "type": "actor_execution", "actor": "未知机构", "scope": "教学机器人公司股票", "action": "buy"}],
                "evidence": [{"id": "technical", "source_type": "business", "stage": "business", "actor": "教学机器人公司", "scope": "教学机器人项目", "action": "technical_test",
                              "period_start": "2026-10-08", "period_end": "2026-10-08", "available_at": "2026-10-08T17:00:00+08:00", "verified_at": "2026-10-08T17:10:00+08:00",
                              "verified": True, "source": "教学技术进展原句", "quote": "教学：样机完成内部技术试验；未提供客户合同、交付控制权、收入或投资者信息。"}]}
    business_file = inputs / "cn-business-versus-revenue.json"
    business_file.write_text(json.dumps(business, ensure_ascii=False, indent=2), encoding="utf-8")
    business_result = snapshot(invoke("narrative", "--input", business_file, "--out-dir", out / "cn-business"))
    assert business_result["claims"][0]["support_ids"] == ["technical"]
    assert all(c["status"] == "证据不足，不能确认" for c in business_result["claims"][1:])
    invoke("replay", "--db", db, "--demo", "--run-id", baseline["run_id"], "--out-dir", out / "baseline")
    assert Path(paths["snapshot"]).read_bytes() == frozen
    case("主题技术事实不确认收入与证券买家", ["inputs/cn-business-versus-revenue.json"],
         {"technical_supported": True, "revenue_supported": False, "investor_supported": False, "frozen_sha256": frozen_hash},
         business_result, "收入准则第4/5/11/13条须结合合同/控制权，内部试验不是客户验收或收入证据；商业主体与证券账户分开，未知不等于零")
    manifest = {"simulation": True, "method_version": baseline["version"], "reused_checks": checks,
                "cases": cases, "commands": commands, "scope": "CLI reports and synthetic cases only; no real-source authentication"}
    (out / "scenario-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "scenario-index.md").write_text("# MarketLens教学情景\n\n全部为合成输入，不代表真实市场覆盖。CN官方依据见包内references/cn-scenarios.md（核验2026-10-10），不推算真实沪股通交易日。\n\n" +
        "\n".join(f"- {c['name']}：通过；{c['method']}" for c in cases) +
        "\n\n复用44项原有约束检查；详细输入、预期、实际、命令和方法版本见scenario-manifest.json。\n", encoding="utf-8")
    print(json.dumps({"passed_cases": len(cases), "reused_checks": checks["passed"], "output": str(out)}, ensure_ascii=False))
    if human:
        print(f"市场明镜 MarketLens｜教学情景已生成，非真实市场覆盖。\n结果目录：{out}"
              f"\n打开Markdown：{out / 'scenario-index.md'}\n输入/预期/实际：{out / 'scenario-manifest.json'}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--human", action="store_true", help="中文提示走stderr，stdout保持JSON")
    try:
        args = parser.parse_args()
        run(args.output, args.human)
    except FileExistsError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        if "--human" in sys.argv:
            print("下一步：给--output换一个尚不存在的新目录名；旧结果保留，不提供强制覆盖。", file=sys.stderr)
        sys.exit(2)
