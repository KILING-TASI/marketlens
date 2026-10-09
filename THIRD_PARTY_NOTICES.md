# Third-party notices and data rights

## Original project material

The MIT license applies to original MarketLens code, Skill instructions,
schemas, explanatory structure, synthetic examples and original documentation
that KILING-TASI is authorized to license. Third-party quotations or materials
embedded in a document retain their own rights; original analysis does not
relicense the cited source.

## Source and dependency review

The initial repository commit and source imports were reviewed. The Python
scripts were developed for this project and use the Python standard library
and local MarketLens modules. No vendored third-party Python implementation,
copied research-report corpus, real market dataset or third-party visual asset
was identified in the reviewed source tree. Synthetic examples are labeled
as such and are not historical market data.

Python is an external runtime, not distributed in the Skill package; it retains
the PSF license and any applicable runtime notices. GitHub Actions checkout and
setup-python are referenced, not bundled; their respective MIT licenses and
copyright notices remain with those upstream projects:

- https://github.com/python/cpython/blob/main/LICENSE
- https://github.com/actions/checkout/blob/main/LICENSE
- https://github.com/actions/setup-python/blob/main/LICENSE

If third-party implementations or assets are added later, preserve their
licenses and notices and update this inventory before redistribution. This
review does not claim authorship or grant rights over any third-party material.

## Announcements, reports, datasets and user imports

Official announcements and source documents, research reports, paywalled or
licensed data, user-imported files, source excerpts, images, logos, names and
other third-party materials are not relicensed under MIT. Public accessibility,
an attribution, a URL or analysis performed by MarketLens is not itself a
redistribution permission. Use, storage, quotation and redistribution remain
subject to each material's rights, applicable license, contract and access terms.

Generated reports and snapshots can contain imported data or quotations.
Their original layout and analytical structure may be MIT-licensed, while
embedded third-party content retains its own restrictions. Confirm the rights
before sharing such outputs. MIT does not grant trademark rights, endorsement
or permission to redistribute proprietary data.

## Packages and historical releases

New packages built with scripts/build_package.py include LICENSE and this
notice. The previously published v0.1.0 asset predates these files and does not
contain them; it has not been rebuilt or replaced by this change. These repository
notices do not rewrite that historical archive or remove third-party restrictions.
