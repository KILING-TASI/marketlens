from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import sqlite3
import statistics
import uuid
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

VERSION = "v3-pilot-0.1"
SCHEMAS = {
    "market": ["date", "available_at", "instrument", "name", "index_id", "category", "open", "high", "low", "close", "volume_shares", "amount_cny", "price_factor"],
    "fund": ["date", "available_at", "instrument", "shares", "nav_cny", "share_factor"],
    "financing": ["date", "available_at", "universe", "buy_cny", "repay_cny", "balance_cny"],
    "breadth": ["date", "available_at", "index_id", "stock", "return_decimal", "weight", "eligible"],
    "sector": ["date", "available_at", "theme", "amount_cny", "market_amount_cny", "up_count", "total_count", "market_scope"],
    "calendar": ["date", "available_at", "market", "is_open"],
}
REQUIRED_NUMBERS = {
    "market": ["open", "high", "low", "close", "amount_cny", "price_factor"],
    "fund": ["shares", "nav_cny", "share_factor"],
    "financing": ["buy_cny", "repay_cny"],
    "breadth": ["return_decimal"],
    "sector": ["amount_cny", "market_amount_cny", "up_count", "total_count"],
    "calendar": [],
}
OPTIONAL_NUMBERS = {"market": ["volume_shares"], "fund": [], "financing": ["balance_cny"], "breadth": ["weight"], "sector": [], "calendar": []}
CATEGORIES = {"宽基", "行业", "主题", "跨境", "其他"}
STAGES = {"计划", "获批", "首次执行", "进展", "完成", "终止", "到期", "持仓披露", "澄清", "生效"}


class ValidationError(ValueError):
    pass


def timestamp(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError()
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, AttributeError):
        raise ValidationError("时间必须包含时区，例如 2026-10-09T18:00:00+08:00")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def finite(value: str, field: str, required: bool = True):
    if value.strip() == "":
        if required:
            raise ValidationError(f"{field}缺失，不能补零")
        return None
    try:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError()
        return number
    except ValueError:
        raise ValidationError(f"{field}须为有限数字，金额单位是人民币元")


def percentile(value, history):
    if value is None or not history:
        return None
    return 100 * (sum(x < value for x in history) + .5 * sum(x == value for x in history)) / len(history)


def direction(value):
    return "未知" if value is None else "增加" if value > 0 else "减少" if value < 0 else "零变化"


def identity_key(kind, row):
    keys = {"market": ["instrument"], "fund": ["instrument"], "financing": ["universe"], "breadth": ["index_id", "stock"], "sector": ["theme", "market_scope"], "calendar": ["market"]}[kind]
    return "|".join([row["date"]] + [row[k] for k in keys])


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS batch(id TEXT PRIMARY KEY,kind TEXT,source TEXT,demo INTEGER,created TEXT,hash TEXT,raw TEXT,row_count INTEGER);
                CREATE UNIQUE INDEX IF NOT EXISTS batch_identity ON batch(kind,source,demo,hash);
                CREATE TABLE IF NOT EXISTS observation(id INTEGER PRIMARY KEY AUTOINCREMENT,batch_id TEXT,kind TEXT,record_key TEXT,date TEXT,available TEXT,data TEXT);
                CREATE INDEX IF NOT EXISTS observation_lookup ON observation(kind,available,date);
                CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT,available TEXT,demo INTEGER,data TEXT);
                CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,created TEXT,action TEXT,target TEXT,data TEXT);
                CREATE TABLE IF NOT EXISTS run(id TEXT PRIMARY KEY,created TEXT,as_of TEXT,demo INTEGER,data TEXT);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def import_csv(self, kind: str, text: str, source: str, demo=False):
        if kind not in SCHEMAS:
            raise ValidationError("未知数据类型")
        if not source.strip():
            raise ValidationError("须填写来源和口径，例如供应商名称、导出时间、人民币元")
        if len(text) > 8_000_000:
            raise ValidationError("单次文件不得超过8MB，请分批导入")
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
        if not reader.fieldnames or set(reader.fieldnames) != set(SCHEMAS[kind]):
            raise ValidationError("列名须与下载模板一致：" + ",".join(SCHEMAS[kind]))
        rows, keys = [], set()
        for line, raw in enumerate(reader, 2):
            try:
                if None in raw or any(v is None for v in raw.values()):
                    raise ValidationError("列数不一致")
                row = {k: v.strip() for k, v in raw.items()}
                date.fromisoformat(row["date"])
                row["available_at"] = timestamp(row["available_at"])
                if datetime.fromisoformat(row["available_at"]).astimezone(timezone.utc).date() < date.fromisoformat(row["date"]) and kind not in {"calendar"}:
                    # Asia/Shanghai 的凌晨允许落在前一个UTC日。
                    local_day = datetime.fromisoformat(row["available_at"]).astimezone(timezone(timedelta(hours=8))).date()
                    if local_day < date.fromisoformat(row["date"]):
                        raise ValidationError("可用时间早于数据所属日期")
                for field in REQUIRED_NUMBERS[kind]:
                    row[field] = finite(row[field], field)
                for field in OPTIONAL_NUMBERS[kind]:
                    row[field] = finite(row[field], field, False)
                if kind == "market":
                    if not row["instrument"] or not row["name"] or row["category"] not in CATEGORIES:
                        raise ValidationError("证券身份、名称或互斥主分类无效")
                    if min(row[x] for x in ["open", "high", "low", "close", "price_factor"]) <= 0:
                        raise ValidationError("价格和复权因子须为正")
                    if row["low"] > min(row["open"], row["close"]) or row["high"] < max(row["open"], row["close"]) or row["high"] < row["low"]:
                        raise ValidationError("OHLC关系不合法")
                    if row["amount_cny"] < 0 or (row["volume_shares"] is not None and row["volume_shares"] < 0):
                        raise ValidationError("成交量额不能为负")
                if kind == "fund" and (row["shares"] < 0 or row["nav_cny"] <= 0 or row["share_factor"] <= 0):
                    raise ValidationError("份额非负，净值和折算因子须为正")
                if kind == "financing" and (not row["universe"] or min(row["buy_cny"], row["repay_cny"]) < 0 or (row["balance_cny"] is not None and row["balance_cny"] < 0)):
                    raise ValidationError("融资范围必填，金额不能为负")
                if kind == "breadth":
                    if not row["stock"] or not row["index_id"] or row["eligible"] not in {"0", "1"} or row["return_decimal"] < -1 or (row["weight"] is not None and not 0 <= row["weight"] <= 1):
                        raise ValidationError("宽度记录无效，收益采用小数，权重0至1，eligible为0或1")
                if kind == "sector":
                    if not row["theme"] or not row["market_scope"] or row["market_amount_cny"] <= 0 or not 0 <= row["amount_cny"] <= row["market_amount_cny"] or not 0 <= row["up_count"] <= row["total_count"] or row["total_count"] <= 0 or any(row[x] != int(row[x]) for x in ["up_count", "total_count"]):
                        raise ValidationError("主题成交分母、范围及上涨数量无效")
                if kind == "calendar" and (not row["market"] or row["is_open"] not in {"0", "1"}):
                    raise ValidationError("交易日历market必填，is_open为0或1")
                for field in {"fund": ["instrument"]}.get(kind, []):
                    if not row[field]:
                        raise ValidationError("证券身份缺失")
                key = identity_key(kind, row)
                if key in keys:
                    raise ValidationError("同批次包含重复证券/日期；修订请用另一个批次和真实修订可用时间")
                keys.add(key)
                rows.append(row)
            except (ValidationError, ValueError) as error:
                raise ValidationError(f"第{line}行：{error}")
        if not rows:
            raise ValidationError("文件只有标题，没有数据")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        bid = uuid.uuid4().hex
        with self.connect() as db:
            old = db.execute("SELECT id,row_count FROM batch WHERE kind=? AND source=? AND demo=? AND hash=?", (kind, source.strip(), int(demo), digest)).fetchone()
            if old:
                return {"id": old["id"], "rows": old["row_count"], "duplicate": True}
            db.execute("INSERT INTO batch VALUES(?,?,?,?,?,?,?,?)", (bid, kind, source.strip(), int(demo), now(), digest, text, len(rows)))
            for row in rows:
                db.execute("INSERT INTO observation(batch_id,kind,record_key,date,available,data) VALUES(?,?,?,?,?,?)", (bid, kind, identity_key(kind, row), row["date"], row["available_at"], json.dumps(row, ensure_ascii=False)))
            db.execute("INSERT INTO audit(created,action,target,data) VALUES(?,?,?,?)", (now(), "import", bid, json.dumps({"rows": len(rows), "hash": digest})))
        return {"id": bid, "rows": len(rows), "duplicate": False}

    def snapshot(self, as_of: str, demo=False):
        as_of = timestamp(as_of)
        chosen = {}
        per_source = defaultdict(dict)
        with self.connect() as db:
            records = db.execute("SELECT o.*,b.source,b.hash FROM observation o JOIN batch b ON b.id=o.batch_id WHERE b.demo=? AND o.available<=? ORDER BY o.available,o.id", (int(demo), as_of)).fetchall()
        for item in records:
            row = json.loads(item["data"])
            row.update({"_id": item["id"], "_batch": item["batch_id"], "_source": item["source"], "_hash": item["hash"]})
            chosen[(item["kind"], item["record_key"])] = row
            per_source[(item["kind"], item["record_key"])][item["source"]] = row
        result = defaultdict(list)
        for key, row in chosen.items():
            kind, _ = key
            alternatives = list(per_source[key].values())
            def semantic(r):
                return {k:v for k,v in r.items() if not k.startswith("_") and k != "available_at"}
            row["_conflicts"] = [{"id": r["_id"], "source": r["_source"], "batch": r["_batch"], "hash": r["_hash"], "data": semantic(r)} for r in alternatives if semantic(r) != semantic(row)]
            result[kind].append(row)
        for rows in result.values():
            rows.sort(key=lambda r: (r["date"], r["_id"]))
        return result

    def add_evidence(self, data: dict, demo=False):
        data = dict(data)
        required = ["event_id", "actor", "scope", "kind", "stage", "level", "published_at", "period_start", "period_end", "quote", "source", "location"]
        if any(not str(data.get(k, "")).strip() for k in required):
            raise ValidationError("请填写主体、范围、日期、原句、来源和定位信息")
        if data["level"] not in {"E1", "E2", "E3", "E4"} or data["stage"] not in STAGES:
            raise ValidationError("证据等级或事件状态无效")
        if data["level"] == "E3" and data["stage"] not in {"首次执行", "进展", "完成"}:
            raise ValidationError("E3必须对应已执行状态；计划不能确认执行")
        if data["level"] == "E4" and data["stage"] != "持仓披露":
            raise ValidationError("E4只记录持仓披露，不替代执行披露")
        try:
            start, end = date.fromisoformat(data["period_start"]), date.fromisoformat(data["period_end"])
            if end < start:
                raise ValueError()
        except ValueError:
            raise ValidationError("发生期间无效，起止日期须为YYYY-MM-DD")
        data["published_at"] = timestamp(data["published_at"])
        if datetime.fromisoformat(data["published_at"]).astimezone(timezone(timedelta(hours=8))).date() < end:
            raise ValidationError("披露不能早于已发生期间；未来计划请以公告日为发生期，计划期限写入原句")
        if len(data["quote"]) > 20000:
            raise ValidationError("证据原句过长")
        for field in ["cumulative_amount_cny", "plan_min_cny", "plan_max_cny"]:
            value = data.get(field)
            data[field] = None if value in (None, "") else finite(str(value), field)
            if data[field] is not None and data[field] < 0:
                raise ValidationError("金额不能为负，未知留空")
        if data["plan_min_cny"] is not None and data["plan_max_cny"] is not None and data["plan_min_cny"] > data["plan_max_cny"]:
            raise ValidationError("计划金额下限不能大于上限")
        data["review_status"] = "pending"
        data["created_at"] = now()
        data["reviewed_at"] = None
        data["reviewer"] = None
        with self.connect() as db:
            previous = db.execute("SELECT id,data FROM evidence WHERE event_id=? AND demo=? ORDER BY id DESC LIMIT 1", (data["event_id"], int(demo))).fetchone()
            if previous:
                prev = json.loads(previous["data"])
                if any(prev[k] != data[k] for k in ["actor", "scope", "kind"]):
                    raise ValidationError("同事件主体、范围和类型须一致；不同事件请使用新ID")
                if data["published_at"] < prev["published_at"]:
                    raise ValidationError("事件修订披露时间不能倒退")
                before, after = prev.get("cumulative_amount_cny"), data["cumulative_amount_cny"]
                correction = data.get("corrects_evidence_id")
                if correction is not None and correction != previous["id"]:
                    raise ValidationError("更正须引用同事件的紧前版本，避免混淆并行事件")
                if correction is not None:
                    data["increment_amount_cny"] = None
                    data["revision_adjustment_cny"] = None if before is None or after is None else after - before
                    data["amount_conflict"] = False
                else:
                    data["increment_amount_cny"] = None if before is None or after is None else after - before
                    data["revision_adjustment_cny"] = None
                    data["amount_conflict"] = before is not None and after is not None and after < before
            else:
                if data.get("corrects_evidence_id") is not None:
                    raise ValidationError("更正引用的旧版本不存在")
                data["increment_amount_cny"] = data["cumulative_amount_cny"]
                data["revision_adjustment_cny"] = None
                data["amount_conflict"] = False
            cursor = db.execute("INSERT INTO evidence(event_id,available,demo,data) VALUES(?,?,?,?)", (data["event_id"], data["published_at"], int(demo), json.dumps(data, ensure_ascii=False)))
            db.execute("INSERT INTO audit(created,action,target,data) VALUES(?,?,?,?)", (now(), "evidence_create", str(cursor.lastrowid), "{}"))
            return {"id": cursor.lastrowid, "status": "pending"}

    def review(self, evidence_id, reviewer, approved, demo=False):
        if not reviewer.strip():
            raise ValidationError("须填写审核人")
        with self.connect() as db:
            item = db.execute("SELECT * FROM evidence WHERE id=? AND demo=?", (evidence_id, int(demo))).fetchone()
            if not item:
                raise ValidationError("证据不存在")
            data = json.loads(item["data"])
            if data["review_status"] != "pending":
                raise ValidationError("审核记录不可覆盖；更正请新增版本")
            if approved and data.get("amount_conflict"):
                raise ValidationError("累计金额倒退存在冲突，不能通过审核；请补充更正版本")
            data.update(review_status="approved" if approved else "rejected", reviewer=reviewer.strip(), reviewed_at=now())
            db.execute("UPDATE evidence SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), evidence_id))
            db.execute("INSERT INTO audit(created,action,target,data) VALUES(?,?,?,?)", (now(), "evidence_review", str(evidence_id), json.dumps({"reviewer": reviewer, "approved": approved}, ensure_ascii=False)))
        return {"id": evidence_id, "status": data["review_status"]}

    def evidence_at(self, as_of, demo=False):
        as_of = timestamp(as_of)
        with self.connect() as db:
            records = db.execute("SELECT * FROM evidence WHERE demo=? AND available<=? ORDER BY available,id", (int(demo), as_of)).fetchall()
        result = []
        for item in records:
            row = json.loads(item["data"])
            row["id"] = item["id"]
            # 回放不能使用之后才完成的审核。
            row["review_visible"] = row["review_status"] == "approved" and row.get("reviewed_at") <= as_of
            result.append(row)
        return result

    def status(self, demo=False):
        with self.connect() as db:
            batches = [dict(r) for r in db.execute("SELECT id,kind,source,created,hash,row_count FROM batch WHERE demo=? ORDER BY created DESC", (int(demo),))]
            runs = [dict(r) for r in db.execute("SELECT id,created,as_of FROM run WHERE demo=? ORDER BY created DESC LIMIT 30", (int(demo),))]
        return {"batches": batches, "runs": runs}

    def get_run(self, run_id, demo=False):
        with self.connect() as db:
            item = db.execute("SELECT data FROM run WHERE id=? AND demo=?", (run_id, int(demo))).fetchone()
        if not item:
            raise ValidationError("回放结果不存在")
        return json.loads(item["data"])

    def assess(self, as_of, demo=False):
        as_of = timestamp(as_of)
        snapshot = self.snapshot(as_of, demo)
        all_rows = [r for rows in snapshot.values() for r in rows]
        issues = []
        for kind, rows in list(snapshot.items()):
            for r in rows:
                if r["_conflicts"]:
                    issues.append({"code": "G01", "kind": kind, "record_id": r["_id"], "message": "不同来源同记录存在冲突，阻断依赖值；需核对来源与口径", "alternatives": r["_conflicts"]})
            snapshot[kind] = [r for r in rows if not r["_conflicts"]]
        groups = defaultdict(list)
        for row in snapshot["market"]:
            groups[row["instrument"]].append(row)
        cards = []
        for instrument, series in sorted(groups.items()):
            current = series[-1]
            previous = series[-2] if len(series) > 1 else None
            history = series[:-1][-252:]
            amounts = [r["amount_cny"] for r in history]
            count = len(history)
            amount_p = percentile(current["amount_cny"], amounts) if count >= 120 else None
            median60 = statistics.median(amounts[-60:]) if count >= 60 else None
            multiplier = current["amount_cny"] / median60 if median60 and median60 > 0 else None
            def adjusted(r):
                return r["close"] * r["price_factor"]
            ret = adjusted(current) / adjusted(previous) - 1 if previous else None
            impact = abs(math.log1p(ret)) / (current["amount_cny"] / 1e8) if ret is not None and current["amount_cny"] > 0 else None
            amplitude = (current["high"] - current["low"]) * current["price_factor"] / adjusted(previous) if previous else None
            impacts = []
            for j in range(max(1, len(series)-253), len(series)-1):
                r, prev = series[j], series[j-1]
                if r["amount_cny"] > 0:
                    impacts.append(abs(math.log(adjusted(r) / adjusted(prev))) / (r["amount_cny"] / 1e8))
            impact_p = percentile(impact, impacts) if len(impacts) >= 120 else None
            day = current["date"]
            cal_market = "SSE" if instrument.startswith("SSE:") else "SZSE" if instrument.startswith("SZSE:") else None
            calendar = [r for r in snapshot["calendar"] if r["market"] == cal_market and r["date"] <= day]
            closed_dates = {r["date"] for r in calendar if r["is_open"] == "0"}
            if day in closed_dates:
                issues.append({"code": "G02", "instrument": instrument, "message": "行情日期被已知日历标记为休市，阻断该卡"})
                continue
            opens = sorted({r["date"] for r in calendar if r["is_open"] == "1"})
            preceding = max((d for d in opens if d < day), default=None)
            consecutive = bool(previous and preceding == previous["date"])
            gap = previous is not None and not consecutive
            if gap:
                ret, impact, amplitude, impact_p = None, None, None, None
            fund = [r for r in snapshot["fund"] if r["instrument"] == instrument]
            fund_by_date = {r["date"]: r for r in fund}
            fcur = fund_by_date.get(day)
            fprev = fund_by_date.get(previous["date"]) if previous and consecutive else None
            change = (fcur["shares"]*fcur["share_factor"] - fprev["shares"]*fprev["share_factor"]) if fcur and fprev else None
            value = change * fcur["nav_cny"] / fcur["share_factor"] if change is not None else None
            members = [r for r in snapshot["breadth"] if r["date"] == day and r["index_id"] == current["index_id"] and r["eligible"] == "1"]
            returns = [r["return_decimal"] for r in members]
            med = statistics.median(returns) if returns else None
            breadth = sum(r > 0 for r in returns) / len(returns) if returns else None
            weighted = members and all(r["weight"] is not None for r in members) and abs(sum(r["weight"] for r in members)-1) < .01
            contributions = [r["weight"] * r["return_decimal"] for r in members] if weighted else []
            positives = sorted([c for c in contributions if c > 0], reverse=True)
            concentration = sum(positives[:5]) / sum(positives) if positives else None
            index_return_proxy = sum(contributions) if weighted else None
            divergence = index_return_proxy - med if index_return_proxy is not None and med is not None else None
            if index_return_proxy is not None and index_return_proxy > 0 and med <= 0:
                structure = "指数收益代理与多数成分股分化"
            else:
                structure = "已取得成分样本" if returns else "成分数据缺失"
            missing = []
            if amount_p is None:
                missing.append("成交分位至少需要120个有效历史样本")
            if gap:
                missing.append("前一交易日未获日历确认或行情缺日，日收益/冲击/净申赎暂不计算")
            if value is None:
                missing.append("本日和经日历确认的前一交易日份额/净值不齐全")
            if not returns:
                missing.append("同日成分股收益与历史池未导入")
            if not weighted:
                missing.append("完整权重缺失，指数收益与贡献代理不可计算")
            level = "数据不足" if amount_p is None else "显著异常" if amount_p >= 99 else "值得观察" if amount_p >= 95 else "常态"
            explanations = [{"type": "ETF申赎", "status": "有支持" if value is not None else "不可观测", "detail": f"净份额{direction(change)}，规模是净值估值，不是实际现金" if value is not None else "份额、净值或交易日历不足"}, {"type": "指数调仓/期现套利/执行方式", "status": "不可观测", "detail": "尚未接入对应事件、期货及逐笔数据"}]
            cards.append({"instrument": instrument, "name": current["name"], "date": day, "index_id": current["index_id"], "category": current["category"], "source": current["_source"], "anomaly": level, "amount_cny": current["amount_cny"], "amount_percentile": amount_p, "history_count": count, "amount_multiplier": multiplier, "return_decimal": ret, "impact": impact, "impact_percentile": impact_p, "amplitude": amplitude, "high_volume_low_impact": bool(amount_p is not None and impact_p is not None and amount_p >= 95 and impact_p <= 20), "net_share_change": change, "net_creation_value_estimate": value, "fund_direction": direction(change), "fund_last_date": fund[-1]["date"] if fund else None, "breadth": breadth, "median_return": med, "equal_return": statistics.mean(returns) if returns else None, "member_count": len(members), "index_return_proxy": index_return_proxy, "divergence_proxy": divergence, "top5_positive_contribution_proxy": concentration, "structure": structure, "identity": "未知：不得从行情推断主体", "missing": missing, "explanations": explanations})
        current_day = max((c["date"] for c in cards), default=None)
        same_day = [c for c in cards if c["date"] == current_day]
        fund_values = [c for c in same_day if c["net_creation_value_estimate"] is not None]
        fund_sum = sum(c["net_creation_value_estimate"] for c in fund_values) if fund_values else None
        financing = [r for r in snapshot["financing"] if r["date"] == current_day]
        # 多个统计池不相加，可能重叠。
        financing_result = [{"universe": r["universe"], "date": r["date"], "value": r["buy_cny"] - r["repay_cny"], "balance": r["balance_cny"], "source": r["_source"]} for r in financing]
        for r in financing_result:
            m = r["value"]
            r["regime"] = "数据不足" if fund_sum is None else "含零变化，分别观察" if fund_sum == 0 or m == 0 else "同向扩张" if fund_sum > 0 and m > 0 else "同向收缩" if fund_sum < 0 and m < 0 else "ETF扩张、融资收缩" if fund_sum > 0 else "ETF收缩、融资扩张"
            r["scope_note"] = "ETF导入池与融资统计池可能不同；仅并列观察，不作资金互减或身份归因"
        category = defaultdict(list)
        for c in fund_values:
            category[c["category"]].append(c)
        categories = [{"category": k, "value": sum(c["net_creation_value_estimate"] for c in v), "count": len(v), "instruments": [c["instrument"] for c in v]} for k, v in sorted(category.items())]
        sectors = []
        by_sector = defaultdict(list)
        for r in snapshot["sector"]:
            by_sector[(r["theme"], r["market_scope"])].append(r)
        for (theme, scope), rows in by_sector.items():
            last, old = rows[-1], rows[:-1][-252:]
            fraction = last["amount_cny"] / last["market_amount_cny"]
            p = percentile(fraction, [r["amount_cny"] / r["market_amount_cny"] for r in old]) if len(old) >= 120 else None
            sectors.append({"theme": theme, "market_scope": scope, "date": last["date"], "fraction": fraction, "breadth": last["up_count"]/last["total_count"], "percentile": p, "samples": len(old), "status": "高交易占比，非下跌概率" if p is not None and p >= 95 else "历史不足" if p is None else "普通观察"})
        evidence = self.evidence_at(as_of, demo)
        latest = {}
        for e in evidence:
            latest[e["event_id"]] = e
        for e in latest.values():
            e["execution_confirmed"] = bool(e["review_visible"] and e["level"] == "E3" and not e.get("amount_conflict"))
            e["holdings_confirmed"] = bool(e["review_visible"] and e["level"] == "E4")
            e["identity_note"] = "只确认原文主体、范围和期间，未披露金额保持未知"
        selected_ids = sorted(r["_id"] for r in all_rows)
        manifest = {r["_batch"]: {"source": r["_source"], "sha256": r["_hash"]} for r in all_rows}
        for r in all_rows:
            for alternative in r["_conflicts"]:
                selected_ids.append(alternative["id"])
                manifest[alternative["batch"]] = {"source": alternative["source"], "sha256": alternative["hash"]}
        selected_ids = sorted(set(selected_ids))
        result = {"version": VERSION, "as_of": as_of, "demo": bool(demo), "data_day": current_day, "mode_note": "全部为合成示例，不能作为行情或投资依据" if demo else "仅使用本地导入数据；不是全市场覆盖", "cards": cards, "fund_aggregate": {"value": fund_sum, "usable": len(fund_values), "observed": len(same_day), "coverage": len(fund_values)/len(same_day) if same_day else None, "scope": "当日已导入ETF池（未知目标总体，不能称全市场覆盖率）"}, "financing": financing_result, "categories": categories, "sectors": sectors, "evidence": list(latest.values()), "quality_issues": issues, "manifest": manifest, "observation_ids": selected_ids, "evidence_ids": [e["id"] for e in evidence], "limitations": ["指数收益与贡献采用期初权重近似，不是官方精确贡献", "每日字段可用时间由导入者声明，须自行核对原始发布时间", "尚无在线行情接入、自动主体识别或交易执行", "叙事核验首版使用人工证据原句，尚未自动匹配新闻主张"]}
        digest = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        run_id = digest[:24]
        result["run_id"] = run_id
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO run VALUES(?,?,?,?,?)", (run_id, now(), as_of, int(demo), json.dumps(result, ensure_ascii=False)))
        return result
