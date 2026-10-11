# 市场明镜 MarketLens

核查市场消息、公告执行与样本观察，区分事实、推断和证据缺口。

[![原创代码 MIT](https://img.shields.io/badge/原创代码-MIT-green)](LICENSE) · [当前发行版 v0.3.4](https://github.com/KILING-TASI/marketlens/releases/tag/v0.3.4) · [运行检查](https://github.com/KILING-TASI/marketlens/actions)

## 能解决什么问题

**这消息可信吗？回购兑现了吗？指数涨，为什么多数股票没涨？**

独立维护市场叙事与证据核查；工作台提供问题导航，导航不代表已经集成全部调用。

## 快速开始

从[发行页](https://github.com/KILING-TASI/marketlens/releases/tag/v0.3.4)下载完整源码并解压，需要 Python 3.10 或以上。在源码目录执行：

```text
python try_demo.py --no-open --out-dir reports/first-demo
```

按提示打开新生成的 HTML。Windows 也可双击 `Start-Demo.cmd`，Linux/macOS 可用 `sh Start-Demo.sh`。教学使用原创模拟资料，不自动取真实数据；重复运行使用新目录，历史结果保留。

[查看已保存的报告示例](examples/teaching-report.html)。HTML请随完整源码下载后打开；示例按自身生成日期和口径阅读。

![已保存的报告示例](examples/teaching-report.jpg)

图片是历史示例，不能推定全部新报告已完成视觉验收。

## 使用自己的资料

先按[资料准备](BEGINNER.md)填写输入，再看[详细命令与方法](USAGE.md)。需要安装CLI时，在自己的Python环境运行：

```text
python -m pip install .
marketlens --help
```

仓库、Python发行包、安装命令及Skill注册名均为 `marketlens`。CLI安装和Skill注册是两个步骤：自然语言调用按[SKILL.md](SKILL.md)配置，保留完整资源；不必安装全部仓库。安装普通构建依赖可能联网，教学流程不需要作者缓存。

## 结果范围

公告计划不等于执行，成交放量不证明买方身份；限定样本不能外推全市场。

报告中的来源、日期、假设和未知事项需一起阅读。程序运行成功不等于来源已经认证、资料完整或投资判断有效。原创代码采用MIT，第三方代码、公告、研报和数据仍按各自权利范围处理。

## 文档与维护

- [详细命令与方法](USAGE.md)
- [资料准备与排错](BEGINNER.md)
- [Skill调用指引](SKILL.md)
- [版本记录](CHANGELOG.md)
- [许可与第三方范围](THIRD_PARTY_NOTICES.md)
- [审计范围](AUDIT_SCOPE.md)
- [扩展专题](EXPANSION.md)

[贡献说明](CONTRIBUTING.md) · [安全反馈](SECURITY.md) · [更新与清理](LIFECYCLE.md) · [English](README.en.md)

[按问题选择其他工具](https://github.com/KILING-TASI/research-workbench/blob/main/references/tool-navigation.md)。共12个活跃仓，资料契约校验已并入[数据仓](https://github.com/KILING-TASI/cn-data-adapters/blob/main/CONTRACT_MIGRATION.md)。各仓分别发布；main的后续文档整理不改写旧发行包和冻结结果。

## v0.3.4 本轮补强

独立消息主张与证据对照，支持、反对、背景和局部支持分开；工作台通过薄接口调用。具体参数与边界见[使用说明](USAGE.md)。
