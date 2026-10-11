# Chinese market narrative evidence

Review supplied market observations and claim evidence without inferring account identity. Online acquisition belongs to data adapters; MarketLens can independently import explicit CSV data.

[中文说明](README.md) · [Skill instructions](SKILL.md) · [First run](BEGINNER.md) · [Changes](CHANGELOG.md)

## Install and run

Clone this repository, enter its directory, and run `python -m pip install .`. Optional PDF or analysis components are documented in the Chinese README. To try the source-only teaching workflow without other repositories, run:

```console
python try_demo.py --no-open --out-dir reports/first-demo
```

Use a new output directory. Teaching data is synthetic; successful software execution does not verify original documents or complete data coverage. Installing the CLI does not automatically register the Skill: retain the complete repository resources when configuring the Skill in your assistant.

## Boundaries and rights

Each repository works independently; optional cross-repository calls need explicit configuration. Missing evidence stays unknown. No trade execution, profit guarantee, or institutional compliance certification is provided. Original code is MIT; third-party licenses and source-data rights remain separate. Do not redistribute source documents or data solely because the software uses MIT.

[Chinese overview](README.md) · [Detailed commands](USAGE.md) · [Input preparation](BEGINNER.md) · [Version history](CHANGELOG.md).

## Message arguments and competing explanations

Use `marketlens arguments review` for claim-evidence/2 and `marketlens hypotheses review` for qualitative competing-hypotheses/1. Proposed and declared-reviewed bindings remain separate. Theory references organize questions; they do not certify sources, establish legal effects, rank explanations, or generate confidence probabilities. Legacy claim-evidence/1 remains supported.

## Original artifact checks (0.4.0)

`sources fetch` explicitly downloads public HTTPS artifacts. `sources scaffold` hashes selected local bytes; `sources review` checks exact excerpts and optional PDF page locations. Signed disclosure metrics remain distinct from cumulative transaction cash. PDF extraction is optional (`marketlens[pdf]`); no OCR or automatic installation. Read, hash, location, declared relationship and semantic review are separate. See [source workflow](references/source-verification.md).

Version 0.5.0 adds explicit URL-to-file byte comparison, context and full extracted-text alerts, declared aspect reviews, search scope, source relationships and frozen-result comparison. See [evidence workflow](references/evidence-depth.md). These checks do not authenticate publishers or certify semantic truth.
