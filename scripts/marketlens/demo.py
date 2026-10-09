"""Deterministic synthetic examples, isolated from imported real data."""
import csv
import io
import math
from datetime import date, timedelta
from .engine import SCHEMAS


def csv_text(kind, rows):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=SCHEMAS[kind])
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def install(store):
    trading_days = []
    d = date(2025, 1, 2)
    while len(trading_days) < 180:
        if d.weekday() < 5:
            trading_days.append(d)
        d += timedelta(days=1)
    market, funds, finance, breadth, sector, calendar = [], [], [], [], [], []
    instruments = [("SSE:510300", "沪深300ETF 示例", "CSI300", "宽基"), ("SSE:510050", "上证50ETF 示例", "SSE50", "宽基"), ("SSE:588000", "科创50ETF 示例", "STAR50", "宽基"), ("SZSE:159915", "创业板ETF 示例", "CHINEXT", "主题")]
    for i, day in enumerate(trading_days):
        day = day.isoformat()
        available = day + "T18:00:00+08:00"
        for exchange in ["SSE", "SZSE"]:
            calendar.append(dict(date=day, available_at=day+"T08:00:00+08:00", market=exchange, is_open="1"))
        for n, (instrument, name, index, category) in enumerate(instruments):
            price = 3 + n*.6 + .0005*i + .012*math.sin(i*.23+n)
            amount = (9e8+n*2e8)*(1+.08*math.sin(i*.51+n))
            if i == 179 and n == 0:
                amount *= 8
            market.append(dict(date=day, available_at=available, instrument=instrument, name=name, index_id=index, category=category, open=f"{price-.003:.5f}", high=f"{price+.012:.5f}", low=f"{price-.015:.5f}", close=f"{price:.5f}", volume_shares=f"{amount/price:.0f}", amount_cny=f"{amount:.2f}", price_factor="1"))
            shares = 2e9 + i*1e6*(1 if n==3 else -1)
            funds.append(dict(date=day, available_at=day+"T20:00:00+08:00", instrument=instrument, shares=f"{shares:.0f}", nav_cny=f"{price-.005:.5f}", share_factor="1"))
            if n == 0:
                for stock in range(10):
                    r = .04 if stock == 0 else -.002 if stock < 8 else .001
                    weight = .4 if stock == 0 else .6/9
                    breadth.append(dict(date=day, available_at=available, index_id=index, stock=f"DEMO:{stock:03}", return_decimal=str(r), weight=str(weight), eligible="1"))
        finance.append(dict(date=day, available_at=day+"T21:00:00+08:00", universe="合成融资观察池", buy_cny="8000000000", repay_cny="7000000000", balance_cny="100000000000"))
        ratio = .3 + .05*math.sin(i*.2) if i < 179 else .65
        sector.append(dict(date=day, available_at=available, theme="合成科技主题", amount_cny=str(1e11*ratio), market_amount_cny="100000000000", up_count="20" if i==179 else "50", total_count="100", market_scope="合成股票市场"))
    result = []
    for kind, rows in [("market", market), ("fund", funds), ("financing", finance), ("breadth", breadth), ("sector", sector), ("calendar", calendar)]:
        result.append(store.import_csv(kind, csv_text(kind, rows), "MarketLens合成示例；虚构交易日历，非历史行情", True))
    return {"imports": result, "last_date": trading_days[-1].isoformat(), "note": "示例不包含真实公告，不生成具名主体确认"}
