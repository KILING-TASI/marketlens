# 数据与计算

脚本只用Python标准库，Python 3.10以上。数据库放本次工作目录，例如work/marketlens.sqlite3；结果放本次任务允许的交付目录。默认无联网适配器，UTF-8 CSV，金额人民币元，股/份，收益率用小数。

用`run.py template --kind market --output 目标.csv`生成列名。按模块导入，不要求六种文件齐全。

- market：date, available_at, instrument, name, index_id, category, open, high, low, close, volume_shares, amount_cny, price_factor。
- fund：date, available_at, instrument, shares, nav_cny, share_factor。
- financing：date, available_at, universe, buy_cny, repay_cny, balance_cny。
- breadth：date, available_at, index_id, stock, return_decimal, weight, eligible。
- sector：date, available_at, theme, amount_cny, market_amount_cny, up_count, total_count, market_scope。
- calendar：date, available_at, market, is_open。

date所属日；available_at含时区，例如2026-10-09T20:00:00+08:00，为实际可用时间。修订值写修订可用时间，不回填原日。source使用稳定来源标识，抓取时间不拼入标识；不同来源同一记录值冲突会阻断，保留两边依据供核查。证券ID例如SSE:510300；日历market为SSE/SZSE。category只选宽基、行业、主题、跨境、其他之一，不重复分类汇总。

price_factor将OHLC转为可比价格；share_factor将实际份额转为可比份额，计算shares×factor、nav/factor。无企业行动且口径已核实填1，不知道不猜。volume_shares、balance_cny、weight可空；关键价格、份额、净值、时点不能补零，缺份额可继续行情分析。breadth是一行一个时点成分的当日收益，eligible为0/1，权重不齐只算样本宽度。日历来自真实交易日，不能用工作日代替；缺日历，日收益、冲击、单日申赎降级。

```text
python scripts/run.py import --db work/marketlens.sqlite3 --kind market --input 行情.csv --source "来源及口径"
python scripts/run.py assess --db work/marketlens.sqlite3 --as-of 2026-10-09T22:00:00+08:00 --out-dir outputs/市场观察
python scripts/run.py demo --db work/demo.sqlite3 --out-dir outputs/示例观察
python scripts/run.py narrative --input work/主张证据.json --out-dir outputs/叙事分析
```

按当前环境解析路径和Python，用户无需执行命令或填写JSON。demo读独立示例分区；真实模式不读示例。导入幂等，原始CSV和哈希留存；修订新批次。结果保存中文报告和JSON审计底稿，回放旧run不被新修订覆盖。

成交倍数前60记录中位数；分位前252记录，至少120样本，排除当前日，等值用中间秩。95/99是试验阈值不是概率。高量低冲击只筛模式。份额估值需要当日和日历确认的前一交易日，缺日/滞后NULL。

宽度限定导入样本；期初权重×收益为代理，不冒充官方收益与精确贡献。权重不齐不算代理，正贡献集中用正贡献分母。融资池不相加，ETF与融资池不同明示。类别首版只汇总本地ETF，未实现全市场历史指数池、连续周数和规模归一化。主题统计保持相同market_scope，重叠主题不相加。

脚本不验证来源真实性、全集覆盖或企业行动因子，分析者负责核对。可用时间未知不伪造精准历史时刻。

事件金额回退默认标为冲突。正式更正可在record-evidence输入中指定corrects_evidence_id为同事件紧前版本；更正仍待人工审核，记录revision_adjustment_cny，increment_amount_cny留空，负更正不解释为卖出。没有明确更正引用时不能强行通过。累计金额不是当日金额，需核对发生期间。
