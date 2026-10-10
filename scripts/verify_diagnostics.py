"""CLI regressions for input diagnosis; no external sources or model changes."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from marketlens.engine import SCHEMAS


def verify(output):
    out = Path(output).resolve()
    if out.exists():
        raise FileExistsError("Use a new output directory")
    out.mkdir(parents=True)
    commands, cases = [], []
    cli = Path(__file__).with_name("run.py")
    cutoff = "2026-10-09T22:00:00+08:00"

    def call(*args):
        r = subprocess.run([sys.executable, "-X", "utf8", str(cli), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
        commands.append({"args": list(map(str, args)), "exit": r.returncode, "stdout": r.stdout, "stderr": r.stderr})
        assert r.returncode == 0, commands[-1]
        return json.loads(r.stdout)

    days = ["2026-10-07", "2026-10-08", "2026-10-09"]
    def market(identity="SSE:510300", dates=None):
        return [dict(date=d, available_at=d+"T18:00:00+08:00", instrument=identity, name="教学ETF", index_id="教学指数", category="宽基", open=4, high=4, low=4, close=4, volume_shares="", amount_cny=1000000, price_factor=1) for d in (dates or days)]
    def calendar(scope="SSE", late=False, dates=None):
        return [dict(date=d, available_at="2026-10-10T08:00:00+08:00" if late else d+"T08:00:00+08:00", market=scope, is_open=1) for d in (dates or days)]
    def fund(dates=None):
        return [dict(date=d, available_at=d+"T20:00:00+08:00", instrument="SSE:510300", shares=1000000+i*100, nav_cny=4, share_factor=1) for i,d in enumerate(dates or days)]
    def run_case(name, payloads):
        folder = out / name
        folder.mkdir()
        db = folder / "sample.sqlite3"
        imports = []
        for kind, rows in payloads.items():
            path = folder / (kind+".csv")
            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=SCHEMAS[kind]); w.writeheader(); w.writerows(rows)
            imports.append(call("import", "--db", db, "--demo", "--kind", kind, "--input", path, "--source", "合成诊断样本"))
        paths = call("assess", "--db", db, "--demo", "--as-of", cutoff, "--out-dir", folder / "report")
        data = json.loads(Path(paths["snapshot"]).read_text(encoding="utf-8"))
        cases.append({"name": name, "inputs": list(payloads), "actual": data, "imports": imports, "simulation": True})
        return data, paths, db
    normal, paths, db = run_case("valid", {"market": market(), "calendar": calendar(), "fund": fund()})
    c = normal["cards"][0]
    assert c["return_decimal"] == 0 and c["net_creation_value_estimate"] == 400
    assert c["history_count"] == 2 and c["impact_history_count"] == 1 and c["amount_percentile"] is None
    frozen = Path(paths["snapshot"]).read_bytes()
    invalid, _, _ = run_case("legacy-identity", {"market": market("510300"), "calendar": calendar("CN")})
    assert invalid["cards"][0]["instrument"] == "510300"
    assert "IDENTITY_PREFIX" in {d["code"] for d in invalid["cards"][0]["diagnostics"]}
    for name, payload, code in [
        ("wrong-market", {"market": market(), "calendar": calendar("CN")}, "CALENDAR_SCOPE_MISMATCH"),
        ("no-calendar", {"market": market()}, "CALENDAR_NOT_VISIBLE"),
        ("late-calendar", {"market": market(), "calendar": calendar(late=True)}, "CALENDAR_NOT_VISIBLE"),
        ("missing-current-calendar", {"market": market(), "calendar": calendar(dates=days[:2])}, "CALENDAR_CURRENT_MISSING"),
        ("missing-prev-calendar", {"market": market(), "calendar": calendar(dates=[days[2]])}, "CALENDAR_PREVIOUS_MISSING"),
        ("missing-prev-market", {"market": market(dates=[days[0],days[2]]), "calendar": calendar()}, "MARKET_PREVIOUS_MISSING"),
        ("missing-current-fund", {"market": market(), "calendar": calendar(), "fund": fund(days[:2])}, "FUND_CURRENT_MISSING"),
        ("missing-prev-fund", {"market": market(), "calendar": calendar(), "fund": fund([days[0],days[2]])}, "FUND_PREVIOUS_MISSING")]:
        data, _, _ = run_case(name, payload)
        assert code in {d["code"] for d in data["cards"][0]["diagnostics"]}, name
    story = {"simulation": True, "as_of": cutoff, "claims": [{"id": "c", "summary": "<img src=x onerror=alert(1)> | 媒体说已回购", "type": "actor_execution", "actor": "教学公司", "scope": "本公司"}], "evidence": [{"id": "missing", "verified": False}]}
    file = out / "multiple-missing.json"
    file.write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
    result = call("narrative", "--input", file, "--out-dir", out / "narrative")
    data = json.loads(Path(result["snapshot"]).read_text(encoding="utf-8"))
    assert len(data["excluded_evidence"][0]["conditions_not_met"]) >= 7
    assert data["claims"][0]["status"] == "证据不足，不能确认"
    text = Path(result["report"]).read_text(encoding="utf-8")
    assert "&lt;img" in text and "<img" not in text and "\\|" in text
    call("replay", "--db", db, "--demo", "--run-id", normal["run_id"], "--out-dir", Path(paths["report"]).parent)
    assert Path(paths["snapshot"]).read_bytes() == frozen
    summary = {"cases": cases, "narrative": data, "commands": commands, "expected": "3行情→2先前成交额/1先前冲击；恒价收益0，份额差100×净值4=400元；错误身份/市场不自动更正，截止后日历不可见；多缺项与HTML安全；旧run冻结", "frozen_sha256": hashlib.sha256(frozen).hexdigest(), "diagnostics_version": "input-diagnostics-1", "method_version": normal["version"], "simulation": True}
    (out / "diagnostic-checks.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": len(cases)+2, "output": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--output", required=True)
    verify(p.parse_args().output)
