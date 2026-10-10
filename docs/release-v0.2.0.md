# 市场明镜 v0.2.0 发布准备

状态：候选待发布，现有Release仍为v0.1.0。本次只整理已集成成果、统一软件版本并构建安装包，不新增研究模型。最终发布须由总调度在审合后的精确main提交打新标签，旧标签和旧资产保持。

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

发布后应从新的v0.2.0发布页下载安装包，解压后保留SKILL.md、agents、references、scripts、README与两份许可文件。候选阶段没有已上线新资产，不展示“已经可以下载”的入口。已有用户安装不会自动变化，替换前保留个人修改。

## 构建与验收

```powershell
python scripts/build_package.py --output work/marketlens-skill-v0.2.0.zip
python scripts/verify_standalone.py --archive work/marketlens-skill-v0.2.0.zip --output work/release-package-check
```

归档包括公开脚本/文档/Skill资源与许可，不包括.git、缓存、数据库、私有输出、PDF或原件。--archive模式验证所给包的demo与旧基础行为；本轮完整候选资源还以独立源码包模式执行现有9情景、44检查、12诊断及教学六CSV/两JSON重导入。所有输出另存新目录，既存情景目录拒绝覆盖、旧run回放字节保持。资产SHA256和本地路径随回执提供；最终合并后应从精确main重新构建，不能将候选包摘要冒充最终main包摘要。

## 发布后的README替换

确认v0.2.0发布与资产可访问之后，才把README候选状态改成“当前源码与最新安装包为v0.2.0”，并添加发布页`https://github.com/KILING-TASI/marketlens/releases/tag/v0.2.0`及包链接`https://github.com/KILING-TASI/marketlens/releases/download/v0.2.0/marketlens-skill-v0.2.0.zip`。确认前保留“待发布”，旧v0.1.0差异说明不删。本准备PR不负责发布、删分支或改用户安装。
