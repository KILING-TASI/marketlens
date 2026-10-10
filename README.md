# 市场明镜 MarketLens

**市场噪音识别与证据分析系统**  
Market Noise Detection and Evidence Analysis System（MNDEAS）

市场明镜是一个Codex研究Skill：用自然语言分析中国股票、ETF、政策及公告相关叙事，区分市场事实、竞争解释、主体证据与未知信息。需要数字时调用本地计算脚本；无需启动网站。

首版：**v0.1.0**。Python 3.10以上，计算脚本只使用标准库。

## 能用来做什么

- 判断指数上涨是否由少数股票贡献，限定导入成分样本范围。
- 观察ETF成交异常、净份额变化与融资活动的分歧。
- 核查热门概念是否有业务、订单、收入或利润依据。
- 区分回购/增持计划、实际执行、累计进展与正式更正。
- 按指定截止时刻回放资料，分别处理当时已审核结论与事后核验的公开信息。
- 保留来源、时间、单位、版本和缺失项，减少重复叙事造成的误判。

“ETF放量、份额下降、融资增加”不能直接证明“国家队撤退、散户接盘”。系统把这些事实分别分析，确认主体与交易需要范围明确的原始披露。

## 作为Skill使用

将本仓库的`SKILL.md`、`agents/`、`references/`、`scripts/`安装到Codex用户Skill目录中的`marketlens/`。常规Windows路径为用户目录下的`.codex/skills/marketlens`；自定义CODEX_HOME时使用其`skills/marketlens`。已有同名Skill时先比较版本和保留个人修改。

也可以从[发布页](https://github.com/KILING-TASI/marketlens/releases)下载安装包，其顶层目录已经叫`marketlens`。在能够识别新Skill的对话中调用：

```text
$marketlens 分析这段市场消息，区分事实、推断和缺失证据。
```

其他例子：

```text
用市场明镜核对这份回购公告：哪些只是计划，哪些已经执行？
以昨天18点为截止，分析当时公开信息可以支持什么，今日披露另讲。
读取我提供的ETF数据，计算净申赎规模估值和融资活动分歧。
```

## 本地计算与试用

在仓库根目录运行。数据和结果写工作目录，不写Skill安装目录：

```text
python scripts/run.py demo --db work/demo.sqlite3 --out-dir work/demo-results
python scripts/run.py template --kind market --output work/market.csv
python scripts/run.py import --db work/research.sqlite3 --kind market --input work/market.csv --source "稳定来源名称及口径"
python scripts/run.py assess --db work/research.sqlite3 --as-of 2026-10-09T22:00:00+08:00 --out-dir work/results
python scripts/run.py self-test --out-dir work/tests
```

demo数据和交易日历均为合成，不能当作真实行情。示例与真实导入分区隔离。命令示例中的时间仅用于演示，应改为实际研究截止时刻。

六种CSV与计算口径见[数据契约](references/data-contract.md)。只有文字消息时可以直接使用Skill，无需准备CSV。结构化叙事脚本检查已整理的时点、范围和阶段，不自动理解或认证原文。

职责边界、实际入口目录、来源与时间缺口、版本和本批交付状态统一见[数据契约与状态](references/data-contract.md#数据入口目录与职责2026-10-10盘点)。目前独立运行、不依赖其他仓库；跨仓共同样本尚未验证，旁路来源记录头仅为设计。PR #1中的许可与文档变化待审，main、旧Release和既有安装版未随之更新。

## 验证

教学情景短入口：`python scripts/run_scenarios.py --output work/scenarios-new`（使用新的目录，不覆盖旧结果）。它复用44项现有检查，并实际生成6类CLI报告：样本多数下跌/贡献代理上涨、成交份额融资背离、回购计划与执行及累计更正、计划伪标执行失败、未知可得时点、冲突来源与旧结果冻结。输出`scenario-index.md`和`scenario-manifest.json`保存输入、独立预期、实际、完整命令与方法版本；全部为合成教学。[情景范围与独立验收](docs/validation.md)

首版完成三轮独立自然语言情景复查，覆盖9个复合请求；优化后的44项计算及证据约束检查通过，另完成9步实际命令调用。[测试与边界说明](docs/validation.md)

GitHub Actions在Windows/Linux及Python 3.10/3.12上运行本地检查，不需要行情API、账户或密钥。模拟测试不代表真实市场识别准确率、预测能力或收益。

## 已实现与边界

已有：CSV导入、成交分位、样本宽度与贡献代理、净申赎估值、融资并列、池内类别汇总、主题成交占比、证据记录与审核、更正、结果回放和中文报告。

未接通自动行情，也未自动实现完整全市场历史池、分钟IOPV、财务/一致预期、IPO/组合或收益预测模型。现实研究需要取得原始材料并核对真实性、可用时间与口径。

成交额不是净现金流，份额不是账户身份，持仓存量不等于具体交易。95/99分位不是概率；期初权重贡献是代理；观察池不完整时不能外推全市场。系统不执行交易、不默认联网、不启动后台任务、不把用户文件上传第三方接口。

## 许可与数据权利

有权许可的原创代码、Skill说明、结构定义与合成示例采用[MIT许可证](LICENSE)，版权主体为KILING-TASI。第三方内容保留原许可，详见[第三方与数据权利说明](THIRD_PARTY_NOTICES.md)。公告、研报、付费数据、用户导入、引用原文、标识和第三方素材不会因MIT取得再分发权；生成报告的原创结构与其中第三方内容分别处理。

新安装包通过`python scripts/build_package.py --output work/marketlens-skill.zip`生成，包含两份许可文件，不覆盖已有压缩包。已发布v0.1.0安装包不包含新增许可文件，本次不替换该资产、不发布新版本。

## 仓库结构

```text
SKILL.md                 自然语言研究入口
agents/openai.yaml       Skill展示元数据
references/              证据、数据、能力与验证细则
scripts/run.py           本地命令入口
scripts/marketlens/      计算、叙事约束、示例与测试
docs/validation.md       压力测试与优化说明
```
