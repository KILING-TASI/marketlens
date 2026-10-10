from __future__ import annotations
import argparse
import csv
import io
import json
import html
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from marketlens.engine import SCHEMAS, Store, ValidationError, now
from marketlens.demo import install
from marketlens.narrative import analyze


def number(value, percent=False):
    if value is None:
        return "未知"
    return f"{value*100:.2f}%" if percent else f"{value:,.2f}"


def table_cell(value):
    return html.escape(str(value), quote=False).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def local_time(value):
    return datetime.fromisoformat(value).astimezone(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def report(data):
    if "available_evidence" in data:
        replay_label = "复现当时已审核结论" if data["replay_mode"] == "confirmed_state" else "事后核验当时公开信息"
        evidence_labels = {e["id"]: f"证据{i+1}" for i,e in enumerate(data["available_evidence"])}
        type_labels = {"actor_execution":"已执行交易", "holdings":"持仓披露", "plan":"计划", "business":"业务兑现"}
        lines = ["# 市场明镜 叙事证据检查", "", "**合成压力情景，非真实市场判断。**" if data["simulation"] else "按提供的资料进行结构化检查，来源真实性仍需人工核实。", "", f"截止时间：{local_time(data['as_of'])}；回放口径：{replay_label}", "", "| 主张 | 判断 | 支持来源 |", "|---|---|---|"]
        for c in data["claims"]:
            claim = c["claim"]
            label = f"{claim.get('actor','未知')} / {claim.get('scope','未知')} / {type_labels[claim['type']]}"
            if claim.get("summary"):
                label = str(claim["summary"])
            if claim.get("amount_cny") is not None:
                label += f"（{claim['amount_cny']/1e8:,.2f}亿元）"
            lines.append("| "+" | ".join(map(table_cell,[label, c["status"], ", ".join(evidence_labels[e] for e in c["support_ids"]) or "无"]))+" |")
        lines += ["", "## 原始依据与限制", ""]
        for e in data["available_evidence"]:
            lines += [f"- {evidence_labels[e['id']]}：{e['source']}，{local_time(e['available_at'])}；原句：{e['quote']}"]
        for e in data["excluded_evidence"]:
            lines += [f"- 未采用 {e['id']}：{e['reason']}"]
            if e.get("conditions_not_met"):
                lines += ["  未满足：" + table_cell("；".join(e["conditions_not_met"])), "  下一步：" + e["next_step"]]
        if data.get("superseded_evidence_ids"):
            lines += ["- 已被明确更正替代的旧依据："+", ".join(evidence_labels[e] for e in data["superseded_evidence_ids"])+"；历史原句仍留档。"]
        for c in data["claims"]:
            for item in c["limited"]+c["conflicts"]:
                lines += [f"- {c['claim'].get('actor','未知')} / {c['claim'].get('scope','未知')}，{evidence_labels[item['id']]}：{item['reason']}"]
        lines += ["", "## 判断边界", ""] + ["- "+s for s in data["gaps"]+data["limitations"]]
        return "\n".join(lines)+"\n"
    lines = ["# 市场明镜 日频市场观察", "", f"**{data['mode_note']}**", "", f"截止时间：{local_time(data['as_of'])}；最新行情日：{data['data_day'] or '无'}", "", "| ETF | 行情日 | 成交观察 | 历史样本 | 净申赎估值（元） | 身份 |", "|---|---|---|---|---|---|"]
    for c in data["cards"]:
        lines.append("| "+" | ".join(map(table_cell,[c["name"],c["date"], c["anomaly"],c["history_count"],number(c["net_creation_value_estimate"]),"未知"]))+" |")
    lines += ["", "## 市场结构与活动", ""]
    for c in data["cards"]:
        lines += [f"- {c['name']}：成交分位 {number(c['amount_percentile'])}，不是概率；成分样本 {c['member_count']}，上涨占比 {number(c['breadth'],True)}。{c['structure']}。", f"  来源：{c['source']}。缺口：{'；'.join(c['missing']) or '核心输入已齐，但来源与范围仍需核查'}。"]
    for f in data["financing"]:
        lines += [f"- {f['date']}融资池“{f['universe']}”：净活动 {number(f['value'])}元；{f['regime']}。{f['scope_note']}。"]
    for c in data["categories"]:
        lines += [f"- {c['category']}：本地池{c['count']}只ETF，净申赎规模估值 {number(c['value'])}元。"]
    for s in data["sectors"]:
        lines += [f"- {s['date']}主题“{s['theme']}”，范围“{s['market_scope']}”：成交占比{number(s['fraction'],True)}，历史分位{number(s['percentile'])}；{s['status']}。"]
    for item in data["cards"] + data["sectors"]:
        for diagnostic in item.get("diagnostics", []):
            lines += [f"- 输入检查 {diagnostic['code']}：{diagnostic['message']} 下一步：{diagnostic['next_step']}"]
    lines += ["", "## 事件证据", ""]
    if not data["evidence"]:
        lines += ["尚无可用主体证据。不能从市场异常推断谁在买卖。"]
    for e in data["evidence"]:
        status = "已执行披露在限定范围内确认" if e["execution_confirmed"] else "持仓披露在限定范围内确认" if e["holdings_confirmed"] else "未确认（待审核、时点受限或非执行证据）"
        lines += [f"- {e['actor']} / {e['scope']}：{e['stage']}，{e['level']}；{status}。原句：{e['quote']}。来源：{e['source']}，定位：{e['location']}。"]
    lines += ["", "## 使用边界", ""]+["- "+s for s in data["limitations"]]
    for issue in data["quality_issues"]:
        lines += [f"- 质量检查 {issue['code']}：{issue['message']}"]
    lines += ["", f"快照编号：{data['run_id']}；公式版本：{data['version']}。JSON底稿保留所选记录ID及来源哈希。"]
    return "\n".join(lines)+"\n"


def write_result(data, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    # 同次运行固定快照幂等；新增运行采用不同文件名，不覆写旧结果。
    stem = data.get("run_id") or __import__('hashlib').sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
    jp, mp = out/f"marketlens-{stem}.json", out/f"marketlens-{stem}.md"
    jp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    mp.write_text(report(data), encoding="utf-8")
    return {"report": str(mp.resolve()), "snapshot": str(jp.resolve())}


def main(argv=None):
    parser = argparse.ArgumentParser(description="市场明镜：本地数据计算与证据检查")
    sub = parser.add_subparsers(dest="command", required=True)
    template = sub.add_parser("template")
    kind_help = "market行情；fund基金份额/净值；financing融资买入/偿还/余额（不含完整两融或融券）；breadth成分收益/权重；sector主题成交与分母；calendar市场交易日历"
    template.add_argument("--kind", choices=SCHEMAS, required=True, help=kind_help)
    template.add_argument("--output", required=True)
    imp = sub.add_parser("import")
    imp.add_argument("--kind", choices=SCHEMAS, required=True, help=kind_help)
    imp.add_argument("--input", required=True)
    imp.add_argument("--source", required=True)
    for name in ["import", "assess", "demo", "record-evidence", "review-evidence", "replay", "status"]:
        cmd = imp if name == "import" else sub.add_parser(name)
        cmd.add_argument("--db", required=True)
        if name != "demo":
            cmd.add_argument("--demo", action="store_true")
        if name in {"assess", "replay", "demo"}:
            cmd.add_argument("--out-dir", required=True)
        if name == "assess":
            cmd.add_argument("--as-of", default=now())
        if name == "record-evidence":
            cmd.add_argument("--input", required=True)
        if name == "review-evidence":
            cmd.add_argument("--id", type=int, required=True)
            cmd.add_argument("--reviewer", required=True)
            cmd.add_argument("--decision", choices=["approve", "reject"], required=True)
        if name == "replay":
            cmd.add_argument("--run-id", required=True)
    narrative = sub.add_parser("narrative")
    narrative.add_argument("--input", required=True)
    narrative.add_argument("--out-dir", required=True)
    test = sub.add_parser("self-test")
    test.add_argument("--out-dir", required=True)
    for command_parser in sub.choices.values():
        command_parser.add_argument("--human", action="store_true", help="在stderr显示中文提示，stdout仍为原JSON")
    args = parser.parse_args(argv)
    teaching_mode = args.command == "demo" or getattr(args, "demo", False)
    if args.command == "template":
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(SCHEMAS[args.kind])
        result = {"template": str(out.resolve())}
    elif args.command == "narrative":
        narrative_data = analyze(json.loads(Path(args.input).read_text(encoding="utf-8-sig")))
        teaching_mode = narrative_data["simulation"]
        result = write_result(narrative_data, args.out_dir)
    elif args.command == "self-test":
        from marketlens.selftest import run_tests
        result = run_tests(args.out_dir)
    else:
        store = Store(args.db)
        mode = getattr(args, "demo", False)
        if args.command == "import":
            result = store.import_csv(args.kind, Path(args.input).read_text(encoding="utf-8-sig"), args.source, mode)
        elif args.command == "demo":
            install(store)
            result = write_result(store.assess(now(), True), args.out_dir)
        elif args.command == "assess":
            result = write_result(store.assess(args.as_of, mode), args.out_dir)
        elif args.command == "replay":
            result = write_result(store.get_run(args.run_id, mode), args.out_dir)
        elif args.command == "record-evidence":
            result = store.add_evidence(json.loads(Path(args.input).read_text(encoding="utf-8-sig")), mode)
        elif args.command == "review-evidence":
            result = store.review(args.id, args.reviewer, args.decision == "approve", mode)
        else:
            result = store.status(mode)
    print(json.dumps(result, ensure_ascii=False))
    if args.human:
        print("市场明镜 MarketLens｜本地CLI入口（Skill名称：marketlens）", file=sys.stderr)
        if "report" in result:
            print(f"已生成{'教学示例（非真实行情）' if teaching_mode else '本地资料分析报告（来源需核验）'}。"
                  f"\n结果目录：{Path(result['report']).parent}\n打开Markdown：{result['report']}"
                  f"\n审计JSON：{result['snapshot']}", file=sys.stderr)
        elif args.command == "template":
            print(f"已生成输入模板：{result['template']}；填写已核对的字段与单位，不把未知补零。", file=sys.stderr)
        elif args.command == "self-test":
            print(f"合成检查：通过{result['passed']}，失败{result['failed']}，错误{result['errors']}；不代表真实识别准确率。", file=sys.stderr)
        else:
            print("本地操作已完成，详情见stdout JSON；证据记录仍按审核状态处理。", file=sys.stderr)
        for warning in result.get("warnings", []):
            print(warning["message"] + " 下一步：" + warning["next_step"], file=sys.stderr)
    if args.command == "self-test" and (result["failed"] or result["errors"]):
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except (ValidationError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        if "--human" in sys.argv:
            print("下一步：核对输入文件是否存在及读写权限；CSV列名用template生成，检查必填字段、人民币元/份额和含时区时间。"
                  "JSON应为UTF-8；不要把缺失证据补成零或当前时间。未自动重试或安装。", file=sys.stderr)
        sys.exit(2)
