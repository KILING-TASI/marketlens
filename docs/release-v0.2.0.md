# 市场明镜 v0.2.0 发布与构建说明

状态：v0.2.0已于2026-10-10发布，标签对应提交`5ab6ceb5fb5f7417b86cf3020f1aebb86021a96a`。本次整理已集成成果、统一软件版本并构建安装包，未新增研究模型；旧标签和旧资产保持。以下构建与候选验收过程保留为历史记录。

## 给使用者的更新说明

市场明镜现在能更清楚地告诉你：资料缺在哪里、哪些市场说法有依据、报告生成后去哪里看。

- 增加中文运行提示，给出结果目录和Markdown报告位置；机器读取的JSON保持兼容。
- 提供完整教学CSV与叙事JSON，9类报告情景可独立运行；未核原文保留未知。
- 明确证券代码前缀、日历市场、缺失日期、份额/净值和历史样本不足，不猜交易所、不补假数据。
- 叙事报告一次列出多个缺项，显示主张摘要并转义HTML；回购计划、执行、更正和持仓仍分开判断。
- 安装包包含原创MIT和第三方数据权利说明；无需行情接口、第三方Python包或研究工作台。

教学结果不是实时行情或收益预测；这次没有新数据采集、主体识别、会计审计或交易功能。自然语言Skill发现与视觉仍未独立验收。

## 版本与安装

软件/Skill metadata为0.2.0；原计算标识v3-pilot-0.1、诊断说明input-diagnostics-1、CSV列与历史冻结结果保持。包内根目录marketlens，Skill真实名marketlens，Python3.10以上，只用标准库，无pyproject项目，因此不提供wheel/sdist。

从[v0.2.0发布页](https://github.com/KILING-TASI/marketlens/releases/tag/v0.2.0)下载[安装包](https://github.com/KILING-TASI/marketlens/releases/download/v0.2.0/marketlens-skill-v0.2.0.zip)和[校验文件](https://github.com/KILING-TASI/marketlens/releases/download/v0.2.0/SHA256SUMS.txt)。解压后保留SKILL.md、agents、references、scripts、README与两份许可文件。已有用户安装不会自动变化，替换前保留个人修改。

已发布ZIP的SHA256为`4a9db610b290ffd3ee0ae88a1f7ddf2b95e806dd9c5ad1c91f8219b804363a64`，与最终main重建核验一致。ZIP内文档保留打包时的候选措辞；本次仅更新当前源码文档，不替换已发布资产。

## 构建与验收

```powershell
python scripts/build_package.py --output work/marketlens-skill-v0.2.0.zip
python scripts/verify_standalone.py --archive work/marketlens-skill-v0.2.0.zip --output work/release-package-check
```

归档包括公开脚本/文档/Skill资源与许可，不包括.git、缓存、数据库、私有输出、PDF或原件。--archive模式验证所给包的demo与旧基础行为；本轮完整候选资源还以独立源码包模式执行现有9情景、44检查、12诊断及教学六CSV/两JSON重导入。所有输出另存新目录，既存情景目录拒绝覆盖、旧run回放字节保持。资产SHA256和本地路径随回执提供；最终合并后应从精确main重新构建，不能将候选包摘要冒充最终main包摘要。

## 发布后状态确认

已核对GitHub发布页与两项资产，README改为当前源码与最新安装包v0.2.0，并保留旧v0.1.0差异。此次状态修正只改文档，不重新发布、删除分支或修改用户安装。
