# 从自己的问题开始

教学入口只验证软件能运行，不代表已经分析你的标的。先用已有资料回答能确定的部分：金额表说明钱放在哪里；披露持仓说明已知重合；公告和报表字段需区分期间、单位及版本。

## 首次试用

完整源码解压后，需要 Python。Windows 可运行 Start-Demo.cmd；也可在源码目录执行 `python try_demo.py`。Linux/macOS 可执行 `sh Start-Demo.sh`，自动打开浏览器依系统能力而定。运行前可用 `python try_demo.py --check`。不联网、不自动安装组件，新输出目录保留旧报告。不能把教学数值替代真实资料。

## 准备资料确认卡

先确认：你问什么；标的身份；研究截止日；来源及资料日期；金额还是份额；币种与单位；权重相对什么。已有会话信息无需重复追问。日期和单位无法确定时只做不依赖它们的解释，不补造。

## 看懂结果与失败

报告生成、输入通过、计算完成和来源核验分别判断。未知比例不是错误率，也不代表未知部分没有风险；说明它可能影响哪个问题。缺来源时提供原表或原文，缺组件时按README按需安装，输出已存在时换新目录。完整技术错误和原始警告留底稿，正文解释影响与下一步。

## 更新与追问

先明确沿用资料还是取得新资料。保存输入、参数和结果，另存新情景；不覆盖历史冻结结果。只有明确登记的资料才能复用，不能默选最新文件。受控取数和专题能力按各自README提供，不把本指南当作任意数据的自动采集器。


本轮新增可引用市场证据摘要。独立入口、底稿与限制见 [EXPANSION.md](EXPANSION.md)。

## 独立原文核对（v0.4.0）

先取得原文，再核对摘要、完整摘录、定位、版本和反证。支持带符号的公告指标与预告偏离提示，仅读取和核查不代表认证真伪。

| 要解决的问题 | 入口 |
|---|---|
| 只有公开原文链接 | `marketlens sources fetch --url HTTPS地址 --out-dir 新目录` |
| 已有原文件，需要准备输入 | `marketlens sources scaffold --source 原文件.md --out input.json` |
| 核对原文与公告指标 | `marketlens sources review --input input.json --out-dir 新目录` |
| 查看独立教学流程 | `python scripts/run.py sources review --input references/examples/source-announcement.json --out-dir 新目录` |

完整说明见[原始资料核对](references/source-verification.md)。PDF可选组件、失败原因、相对路径及未核事项分别说明；不要求其他仓库。
