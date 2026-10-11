# 市场明镜 MarketLens

核对市场消息的依据、推断和证据缺口，说明哪些判断有支持、适用到哪里，以及什么新资料会改变判断。

[原创代码 MIT](LICENSE) · [发行说明](https://github.com/KILING-TASI/marketlens/releases/tag/v0.5.2) · [运行检查](https://github.com/KILING-TASI/marketlens/actions) · [English](README.en.md)

当前发布：**v0.5.2 · 普通发行版**。Python **3.10+**；基础功能只需 Python，无第三方运行依赖。

[快速开始](#快速开始) · [使用自己的资料](#使用自己的资料) · [能力与边界](#能力与边界) · [文档与维护](#文档与维护)

## 能解决什么问题

**这消息可信吗？回购兑现了吗？指数涨，为什么多数股票没涨？**

市场明镜独立维护消息、市场观察和证据分析；工作台组织研究并按需调用。先给证据能够支持的限定结论，再解释支持、反对、局部支持、背景和未知；软件状态不替代原文核验。

| 需要准备 | 会得到什么 |
|---|---|
| 具体主张、选定原文与来源日期；行情分析另需明确的数据记录。 | 限定判断、证据与上下文、未核事项、版本变化及下一步核查问题。 |

## 快速开始

1. 安装 Python 3.10 或以上版本。
2. 下载[完整源码 ZIP](https://github.com/KILING-TASI/marketlens/releases/download/v0.5.2/marketlens-v0.5.2-source.zip)并解压，进入包含 `try_demo.py` 的目录。
3. 在该目录打开终端，运行：

```console
python try_demo.py --no-open --out-dir reports/first-demo
```

按终端给出的路径打开 HTML。也可以在源码目录双击 `Start-Demo.cmd`（Windows），或运行 `sh Start-Demo.sh`（Linux/macOS）。教学使用原创模拟资料，不自动取得真实数据。

使用 Git 时，先运行 `git clone https://github.com/KILING-TASI/marketlens.git`，再运行 `cd marketlens`，随后执行上面的教学命令。重复运行请指定新目录，历史结果会保留。

[报告示例源码](examples/teaching-report.html)：GitHub 会展示 HTML 源码，请下载完整源码后在浏览器中打开。

![教学报告截图](examples/teaching-report.jpg)

截图对应历史教学样本，具体日期、参数和缺口以该报告为准。

## 使用自己的资料

先按[资料准备与排错](BEGINNER.md)整理来源、日期、单位和必要字段，再按[使用说明](USAGE.md)选择对应入口。以下两种使用方式分别配置。

**命令行（CLI）**：在源码目录安装本仓，然后查看可用命令：

```console
python -m pip install .
marketlens --help
```

可选组件按需要安装：`pdf`。例如 `python -m pip install ".[pdf]"`；依赖范围见 [使用说明](USAGE.md)。安装时下载构建工具或可选依赖可能需要联网。

**助手 Skill**：按 [SKILL.md](SKILL.md) 配置，保留完整目录及其引用资源。安装 CLI 不会自动注册 Skill，也不表示已在第三方技能市场上架。

| 身份 | 名称 |
|---|---|
| GitHub 仓库 / Python 发行包 | `marketlens` |
| 主要命令 | `marketlens` |
| SKILL.md 中的名称 | `marketlens` |

本仓可单独使用。需要跨工具功能时，再按说明安装并明确配置对应工具的位置。

## 能力与边界

公告计划不等于执行，成交放量不证明买方身份；限定样本不能外推全市场。

报告中的来源、日期、假设和未知事项需一起阅读。程序运行成功不等于来源已经认证、资料完整或投资判断有效。原创代码采用MIT，第三方代码、公告、研报和数据仍按各自权利范围处理。

[消息论证与竞争解释](references/argument-structure.md) · [原文取得与核对](references/source-verification.md) · [深入证据核对](references/evidence-depth.md) · [附件与指标关联](references/evidence-expansion.md)

原文下载使用显式的 `marketlens sources fetch`；默认原文核对读取本地文件，`--verify-urls` 才访问声明来源。下载成功、逐字匹配和复核声明均不等于真实性认证。

## 文档与维护

- [详细命令与方法](USAGE.md)
- [资料准备与排错](BEGINNER.md)
- [Skill 调用指引](SKILL.md)
- [版本记录](CHANGELOG.md)
- [许可与第三方范围](THIRD_PARTY_NOTICES.md)
- [审计范围](AUDIT_SCOPE.md)
- [扩展专题](EXPANSION.md)

[贡献说明](CONTRIBUTING.md) · [安全反馈](SECURITY.md) · [更新与清理](LIFECYCLE.md)

[按问题选择其他工具](https://github.com/KILING-TASI/research-workbench/blob/main/references/tool-navigation.md)；资料契约校验已并入[数据仓](https://github.com/KILING-TASI/cn-data-adapters/blob/main/CONTRACT_MIGRATION.md)。默认分支的文档整理不改写已发布的源码包和历史结果；版本变化见 [CHANGELOG.md](CHANGELOG.md)。
