# Chinese market narrative evidence

Review supplied market observations, original documents and declared claim evidence. Explicit HTTPS download is available through `marketlens sources fetch`; downloaded bytes, quote matches and review declarations do not authenticate publishers or certify truth.

[中文说明](README.md) · [Release v0.5.2](https://github.com/KILING-TASI/marketlens/releases/tag/v0.5.2) · [Skill instructions](SKILL.md) · [Input preparation](BEGINNER.md)

Current release: **regular release**. Python **3.10+**. Base runtime dependencies: none. Optional extras: `pdf`. See [USAGE.md](USAGE.md) for scope.

## First run

Download the [complete source ZIP](https://github.com/KILING-TASI/marketlens/releases/download/v0.5.2/marketlens-v0.5.2-source.zip), extract it and enter the directory containing `try_demo.py`:

```console
python try_demo.py --no-open --out-dir reports/first-demo
```

Alternatively, clone `https://github.com/KILING-TASI/marketlens.git`, run `cd marketlens`, then execute the command above. Open the report at the path printed by the command. Teaching data is synthetic; use a new output directory and keep prior reports.

## CLI and Skill

From the source directory:

```console
python -m pip install .
marketlens --help
```

Repository and distribution: `marketlens`. Primary CLI: `marketlens`. Skill name in SKILL.md: `marketlens`. Installing the CLI does not register the Skill; configure the complete resources in an assistant that supports local Skills. Build or optional dependencies may require network access during installation.

## Scope and rights

Read the [Chinese capability boundaries](README.md#能力与边界) and [detailed commands](USAGE.md). Each tool can run independently; cross-tool calls need explicit configuration. Successful execution does not authenticate source documents, fill missing data or establish investment validity. No trade execution or guaranteed returns.

Original code uses MIT. Third-party code and documents/data retain their own licenses and rights. Default-branch documentation edits do not rewrite released archives or frozen results.

[Changes](CHANGELOG.md) · [Third-party rights](THIRD_PARTY_NOTICES.md) · [Contribution](CONTRIBUTING.md) · [Security](SECURITY.md)

[Argument review](references/argument-structure.md) · [Original source checks](references/source-verification.md) · [Depth review](references/evidence-depth.md) · [Attachment and metric bindings](references/evidence-expansion.md).
