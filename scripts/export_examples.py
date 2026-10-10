"""Export complete synthetic CSVs and clearly labelled narrative inputs."""
import argparse
import json
from pathlib import Path
import tempfile
from marketlens.demo import install
from marketlens.engine import Store


def export(output):
    out = Path(output).resolve()
    if out.exists():
        raise FileExistsError("输出目录已存在，请换新名字；不覆盖旧输入")
    out.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as directory:
        store = Store(Path(directory) / "synthetic.sqlite3")
        install(store)
        with store.connect() as db:
            for row in db.execute("SELECT kind,raw FROM batch"):
                (out / (row["kind"] + ".csv")).write_text(row["raw"], encoding="utf-8")
    claim = {"id": "c1", "summary": "教学公司是否已经回购？", "type": "actor_execution", "actor": "教学公司", "scope": "教学公司股份", "action": "buy"}
    base = {"simulation": True, "scenario": "全部为构造教学，不是真实公告", "as_of": "2026-10-09T18:00:00+08:00", "claims": [claim]}
    for name, evidence in [
        ("unverified", {"id": "media", "source": "教学媒体转述，原文未取得", "quote": "据称已回购", "verified": False, "available_at": None}),
        ("verified-teaching", {"id": "teaching", "source": "合成教学原句", "quote": "教学：公司于10月8日已回购本公司股份。", "actor": "教学公司", "scope": "教学公司股份", "action": "buy", "source_type": "execution", "stage": "executed", "period_start": "2026-10-08", "period_end": "2026-10-08", "available_at": "2026-10-08T17:00:00+08:00", "verified_at": "2026-10-08T17:10:00+08:00", "verified": True})]:
        (out / (name + ".json")).write_text(json.dumps({**base, "evidence": [evidence]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "说明.md").write_text("# 独立教学输入\n\n六个CSV复用原合成demo，人民币元/份额/收益小数、北京时间+08:00；日历为虚构教学日，不是真实市场日历。份额为构造，不能当真实资金流。请导入独立数据库并使用--demo，勿混入自己的真实资料。unverified.json为未核原文，必须unknown；verified-teaching.json仅是已核教学假设，不能照抄true声明真实材料已核。template仍只生成空表头。\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "simulation": True}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    try:
        export(parser.parse_args().output)
    except FileExistsError as error:
        import sys
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
