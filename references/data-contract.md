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

## 数据入口目录与职责（2026-10-10盘点）

本节是数据入口、契约差异和交付状态的单一详细说明。MarketLens负责市场异常、活动分歧和限定范围的叙事证据检查；公司经营与综合判断留给研究工作台，不承担全部公司事件库、财报估值审计或基金全评价。独立运行仅需Python标准库，不依赖工作台或其他仓库。上游是用户取得并核对的资料，下游是中文报告与冻结JSON；当前没有跨仓自动调用。维护者维护代码和契约，导入者负责来源、范围、权利与可得时间，审核者负责限定语义判断；实际数据负责人未指定。

| 实际入口 / 模块 | 身份、专业字段与频率 | 覆盖、获取与更新 |
|---|---|---|
| `import --kind market` / `Store.import_csv` | 交易所:代码；OHLC人民币元、成交股/份与人民币元、价格因子；日频 | 用户UTF-8 CSV；本地导入池，非全市场；手动新批次 |
| `import --kind fund` / 同上 | ETF身份；份额、单位净值人民币元、份额折算因子；日频 | 手动CSV；无独立分红表、净值类型/币种扩展或公司行动来源链 |
| `import --kind financing` / 同上 | universe融资池；买入、偿还、余额人民币元；日频 | 手动CSV；不同池不相加；余额差不能替代买入减偿还 |
| `import --kind breadth` / 同上 | index_id+stock；收益小数、期初权重、纳入标记；日频 | 用户成分样本；历史成分全集和调整来源未接入 |
| `import --kind sector` / 同上 | theme+market_scope；成交额人民币元、同范围分母、上涨/总数量；日频 | 用户主题池；分类重叠不能汇总为全市场 |
| `import --kind calendar` / 同上 | 市场+日期、是否交易；日频 | 用户真实市场日历；无官方日历下载器；demo工作日仅为合成教学 |
| `record-evidence` / `Store.add_evidence`、`review-evidence` | event_id、主体、范围、类型、阶段、E1–E4、期间、人民币累计/计划金额、原句与定位 | 人工结构化JSON和审核；没有原文下载、PDF解析或法律语义认证 |
| `narrative` / `narrative.analyze` | 主张和证据ID、主体/范围/行为期间、source_type、stage、原句、verified | 人工JSON；独立于数据库证据格式，不是两套自动采集 |
| `demo` / `demo.install` | 上述六类和示例证据 | 程序生成合成数据；不代表真实发布者或覆盖；不联网 |

所有真实入口的原发布者、获取渠道、接口库目前未分列：`source`是调用者提供的自由文本，不能证明发布者身份。当前无已验证的数据商或在线接口；源文档可访问、下载成功、字面解析、语义核验是不同事项。原件与私有数据不提交仓库；公开来源也需独立确认使用权。

## 时间、原始版本与契约差异

CSV的date是观察日，available_at是调用者声明的历史可得时刻（时区必填、解析保存到秒）；时间只有日精度或未知时，不得填一个假定时刻用于精准回放。原始文本保留于batch.raw，SHA256针对去除BOM后的UTF-8文本，不是原文件字节摘要；batch.created是导入时刻，不是取得原件或历史可得时刻。修订以新批次和新available_at表示，同来源同键取最新可得记录；没有显式CSV更正父版本ID。跨来源语义冲突保留并阻断相关计算。

数据库证据保留JSON和人工审核时刻、累计更正父ID，未保存原件字节摘要。published_at同时用于数据库可得筛选，不能表达“发布后延迟取得/可得”；公告日期只有日精度、发布时间与可得时间不同、未来生效计划等场景无法无损映射，必须拒绝映射或保留为待核验资料。未来计划现有入口以公告日为期间、期限在原句中，这只是旧兼容约束，不能称真实生效日。叙事入口独立具有available_at/verified_at，支持事后核验模式，但不自动认证原页。两入口的状态枚举不同，不强行互换。

尚缺：五类时间（观察/发布/生效/取得/可得）及精度完整分离、原件字节摘要、结构化发布者/渠道/接口链、数据权利声明、解析版本和核验层级。未知不填零，不用取得时间回填历史可得时间，不替换数据商或净值口径兜底。

## 最小旁路记录头（设计，尚未实现）

保持旧payload和冻结结果原样；拟以独立sidecar关联原始材料，不扩旧CSV列、不自动导入为已认证事实。字段建议：record_id、publisher、channel、interface_library、subject_identity；observed/published/effective/acquired/available各自value、precision、timezone、basis；raw_snapshot字节sha256与私有定位、revision_of；parser名称与版本；download/page_found/literal_match/semantic_review各自结果与核验时间；coverage、rights、owner；software/interface/rule/data/method各自版本；payload及其原schema标识。未知用null与原因，第三方状态原样保留，派生结果另存并引用输入，不覆盖事实。此头尚不是跨仓稳定接口。

可复用的只是同一原始快照及其摘要，不能继承另仓库的语义认证。已有合成CSV可一对一放入payload；公告合成JSON可保留原字段，但不得据此声称PDF链已联调。反例：只有公告日的材料不能填18点可得；拆分因子不能代替现金分红；港币净值不能塞nav_cny；宏观修订序列没有当前入口，不能强塞market；后下载的正文不能倒填当时已审核。无损适配不足时明确拒绝或另立可审迁移，不静默升级旧数据。

## 四链与重复入口检查

公告链只有人工原句和定位，原件链未接通；基金链有份额/净值/折算，无独立分红事件；行情+日历链已有本地组合计算，真实日期来源由导入者核对；宏观修订链无入口。跨仓同样本验证尚未完成，没有真实共同样本，本批不宣称九仓统一。数据库证据和叙事证据是存储审核与无数据库约束检查两个用途；重复原句可共用私有原始快照，但当前不自动去重或同步审核状态。

## 版本、验证与本批结案

软件发布版本为v0.1.0；计算结果VERSION为v3-pilot-0.1，仅是现有计算标识，未独立区分规则与方法版本。CSV接口为本文件六种精确列集、叙事/证据为各自现有JSON；没有新接口版本或跨仓支持区间。数据版本为批次哈希/记录ID和证据更正链，不是软件版本。后续若改计算/规则须明确独立版本与支持范围，不能靠修改文档追溯升级。Python支持声明为3.10以上，实际CI覆盖3.10/3.12及Windows/Linux。

main与Release v0.1.0为初始发布；本批变化在PR #1的开发分支，尚未合并。既有安装版和旧Release不自动更新；旧ZIP没有新增许可文件。许可与打包变更见README和THIRD_PARTY_NOTICES.md，数据权利独立于MIT。

| 状态维度 | 已知范围 |
|---|---|
| 实现 | 本地导入/计算/审核/回放已有；本批仅文档规范，无sidecar运行实现 |
| 教学验证 | 44项合成检查、9步CLI流程、三轮9个叙事情景；不是投资有效性或资料认证 |
| 真实样本 | 未完成真实市场入口验证，原研究文档不是已认证数据接入样本 |
| 跨仓联调 | 已沟通公告契约差异；没有同样本联调成功证据 |
| 视觉 | 中文Markdown可阅读报告；无已交付网页或视觉界面验收 |
| 待审/发布 | PR #1待审；不合并、不发新版、不替换资产、不自动安装 |

本批结案点：入口与差异、职责/版本/验证界限登记在本文件并提交PR #1；没有采集或迁移完成声明。取得真实同样本、sidecar实现及跨仓无损适配、分红事件和宏观修订接口均为后置批次，需另定范围。idle不代表任务已完成，CI只验证程序行为。冻结run和原始导入保持不变，历史回放不重新计算覆盖。
