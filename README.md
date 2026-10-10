# 市场明镜 MarketLens

看市场消息有哪些证据：指数上涨是否只是少数股票带动，ETF放量能否说明谁在买，回购公告到底兑现了多少。

[![原创代码 MIT](https://img.shields.io/badge/原创代码-MIT-blue)](LICENSE)

## 安装和首次试用

本轮对应[发布页](https://github.com/KILING-TASI/marketlens/releases/tag/v0.2.1)；下载时以实际上传的完整源码、wheel、sdist 与校验清单为准。源码按下面步骤安装；下载 wheel 后，将安装命令末尾的 `.` 换成该 wheel 文件路径。pip 安装不会自动注册 AI 工具中的 Skill。

本轮源码版本为 `0.2.1`。统一安装入口需要 Python 3.10 或以上。在完整源码目录新建自己的 Python 环境，下面的 Windows 命令不需要激活脚本：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\marketlens.exe --help
.\.venv\Scripts\marketlens.exe demo --out-dir reports/demo --auto-name
```

工具名与仓库名相同；在已激活的环境中可以直接输入工具名。Linux/macOS 使用 `.venv/bin/python` 和 `.venv/bin/marketlens`。教学结果写入当前工作目录；`--auto-name` 自动另选新名字，旧结果保留。不加该参数时，教学入口拒绝已有目录。`marketlens run --help` 查看原生参数，原来的命令继续兼容。其他专题可用 `marketlens script --help` 查看入口，以脚本名调用，不需要记住源码路径。pip 安装提供 CLI；作为 Skill 使用仍须保留完整源码及许可资源，不能只复制 SKILL.md。安装可能需要联网获取普通构建依赖；教学离线。下面保留原生入口及此前发行记录，本轮安装和版本以本节为准。

## 最短试用

需要 **Python 3.10 或以上**，只用标准库，无需安装其他仓库、行情接口或密钥。下面使用当前 `main` 源码，离线生成教学报告。

下载本仓源码后，在 `marketlens` 目录打开 Windows PowerShell：

```powershell
python --version
python scripts/run.py demo --db work/demo.sqlite3 --out-dir work/demo-results --human
```

提示会给出结果目录和要打开的 **Markdown 报告**，同目录另有 JSON 底稿。示例行情与交易日历均为合成数据。

想看完整情景实例：

```powershell
python scripts/run_scenarios.py --output work/scenarios-new --human
```

打开生成的 `work/scenarios-new/scenario-index.md`。情景目录必须尚不存在；再次运行时换个名字，例如 `work/scenarios-next`，保留旧结果。`--human` 把中文提示写到 stderr，stdout 仍是可供程序读取的 JSON。

## 导入真实数据前：先核对样本数量

以下门槛按相同证券身份和可比口径分别计算，只使用研究截止时刻已可得的数据；“先前”不包含当前观察日，也不是自然日天数。

| 想查看的结果 | 最少需要什么 |
|---|---|
| 成交倍数 | 当前行情加60条先前成交额；前60条中位数须大于零 |
| 成交分位 | 当前行情加120条先前有效行情；历史最多取252条 |
| 冲击分位 | 120个先前有效冲击值，排除当前冲击；每个历史值需要相邻可比价格及正成交额，全部有效时至少需122条行情 |
| 主题成交占比的历史分位 | 当前占比加120条先前同主题、同市场范围的有效占比；历史最多取252条 |

只导入30天行情时，历史分位保持“未知”是预期结果，不代表安装或联网失败。不同证券的记录不能合并凑数，也不要复制记录或降低门槛。当前占比、样本上涨比例等结果不受同一个120条门槛限制。报告中的输入诊断会列出实际有效数量和补充方向。

计算日收益、当前冲击和单日ETF净申赎估值，还需核对真实交易日历、前一交易日和相应字段；行情条数足够不代表日历、企业行动或来源已核验。完整条件见[数据契约](references/data-contract.md#输入诊断与兼容说明)。统计分位是历史位置，不是涨跌概率。

## 结果示例

**样本多数下跌，但少数大权重股票使贡献代理为正。** 教学数据中，10只股票有3只上涨、7只下跌，中位收益为−0.2%；按期初权重手算的贡献代理为+1.52%。这是导入样本的观察，不能当作官方指数收益或全市场结论。

**ETF放量、份额减少、融资活动增加，仍无法确认谁在买卖。** 另一组教学结果显示份额减少100万份，融资买入减偿还为10亿元；两者覆盖范围不同，也不能合并成某类投资者的资金流。

这些实例通过上述情景入口实际生成报告。北向季度持仓、回购累计更正和主题业务进展的例子也在同一索引中，输入、预期与实际结果另存 JSON。

## 能做什么，暂不支持什么

| 可以做 | 使用时的边界 |
|---|---|
| 计算成交分位、样本上涨比例和权重贡献代理 | 限定导入样本；统计分位不是概率 |
| 对照ETF份额、净值和融资活动 | 净申赎规模是估值，成交额不是净现金，不能识别账户 |
| 核对回购计划、执行、累计进展与正式更正 | 原文与审核状态分开，未披露或未审核的部分保留未知 |
| 检查季度持仓和主题业务说法 | 持仓不等于当天买入，技术进展不自动证明收入或利润 |
| 按截止时间生成、冻结和回放中文报告 | 历史可得时间须有依据，晚披露不能倒填 |

目前没有自动行情采集、完整全市场历史池、分钟IOPV、自动原文认证、收益预测或交易执行。也没有PDF解析器；业务、合同和原句含义需人工核对。需要实际研究时，使用自己已合法取得的资料；本地脚本不把输入上传第三方，也不启动后台服务。

证券身份明确写成 `SSE:510300` 或 `SZSE:159919`；日频日历的 `market` 对应写 `SSE` 或 `SZSE`。`CN` 不是交易所别名，不能替代它们；不确定交易所时保留未知，不按代码猜测。字段、单位和缺口处理见[数据契约](references/data-contract.md)，开发范围见[能力说明](references/capabilities.md)。

需要完整教学CSV与叙事JSON时，运行`python scripts/export_examples.py --output work/teaching-inputs-new`；新目录内有六类CSV、未核原文/已核教学两份JSON和中文说明。导入时使用独立数据库与`--demo`，具体步骤和每项计算的最低数据见[输入诊断说明](references/data-contract.md#输入诊断与兼容说明)。空模板仍只有表头；裸证券代码与不匹配日历会明确警告，不自动猜交易所。

## 独立使用与 Skill 安装

**可以直接运行本地CLI，也可以作为Codex Skill使用。** 两种入口都不依赖研究工作台或其他自家仓库；MarketLens负责市场叙事与证据检查，公司经营和综合判断不由这里包办。

仓库名、Skill名称和安装目录均为 `marketlens`；[SKILL.md](SKILL.md)里的真实名称是 `name: marketlens`。安装 Skill 时复制完整源码目录或解压完整 Skill ZIP，保留说明、代码、参考及许可；不要按零散文件清单裁剪：

```text
marketlens/
  SKILL.md
  agents/
  references/
  scripts/
  README.md
  docs/
  LICENSE
  THIRD_PARTY_NOTICES.md
```

Windows常规目录为 `%USERPROFILE%\.codex\skills\marketlens`；自定义 `CODEX_HOME` 时放在其 `skills\marketlens` 下。已有同名Skill时先保留个人修改、比较版本。可以从当前源码生成完整包：

```powershell
python scripts/build_package.py --output work/marketlens-skill.zip
```

包文件已存在时换新名字，打包器不会覆盖。安装后，在能识别该Skill的Codex对话中使用：

```text
$marketlens 核对这份回购公告：哪些只是计划，哪些已经执行？
$marketlens 这段消息说ETF放量就是国家队买入，现有证据能支持吗？
```

本地CLI的计算、叙事检查与打包已验收；自然语言Skill发现和视觉效果没有纳入独立安装验收。

## 当前源码与旧安装包

此前发行安装包为 **v0.2.0**，包含许可、独立安装验收、9类报告情景、`--human` 中文提示和输入诊断。可从[v0.2.0发布页](https://github.com/KILING-TASI/marketlens/releases/tag/v0.2.0)下载[Skill安装包](https://github.com/KILING-TASI/marketlens/releases/download/v0.2.0/marketlens-skill-v0.2.0.zip)与[SHA256校验文件](https://github.com/KILING-TASI/marketlens/releases/download/v0.2.0/SHA256SUMS.txt)，或克隆当前源码使用上面的命令。计算标识仍为`v3-pilot-0.1`，诊断说明为`input-diagnostics-1`，接口与历史结果不随软件版本升级重写。[发布与构建说明](docs/release-v0.2.0.md)

[旧Release v0.1.0](https://github.com/KILING-TASI/marketlens/releases/tag/v0.1.0)保留原样：它能运行原有demo，但不含新增情景入口、`--human`、打包脚本及新增许可文件。使用旧包时去掉 `--human`：

```powershell
python scripts/run.py demo --db work/demo.sqlite3 --out-dir work/demo-results
```

用户已安装的Skill不会因仓库更新而自动变化。源码、Release和本地安装分别确认，详细版本含义见[数据契约](references/data-contract.md)。

## 验证、许可与来源

- 验证：44项计算与证据约束检查、9类实际CLI报告情景，独立源码包在标准库虚拟环境中运行；CI覆盖Windows/Linux和Python 3.10/3.12。[验证范围与复现方法](docs/validation.md)
- 来源：CN情景的官方规则版本、核验日期和适用条件见[官方口径说明](references/cn-scenarios.md)；主体、时点和原句的核查方法见[叙事与证据](references/narrative-evidence.md)。教学检查通过不代表真实识别准确率或收益。
- 许可：有权许可的原创代码、Skill说明与合成示例采用[MIT](LICENSE)，版权主体KILING-TASI。公告、研报、数据和标识保留各自权利，详见[第三方与数据权利说明](THIRD_PARTY_NOTICES.md)。
