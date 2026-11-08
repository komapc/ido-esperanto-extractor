# Changelog

## [Unreleased]

### Added
- Added `np__np` paradigm to `pardefs.xml` for proper nouns
- Automatic `np__np` paradigm assignment in `merge_sources.py` for all entries with `pos: "np"`
- Proper noun support in `source_io_wikipedia.json` (already had `pos: "np"`, now gets paradigm automatically)

### Changed
- Removed `source_manual.json` - all dictionaries now regenerated from sources only
- `merge_sources.py` now automatically assigns `np__np` paradigm to proper nouns from any source

### Fixed
- io.wiktionary POS from the `Semantiko:` line now reads only its first two links; a POS word inside the definition no longer sets the class (`redaktar`, `recensar`, `revuo` were `det` because of "[[artiklo]]"; `atomo`, `flamo` were `ij` because of "[[partikulo]]"). 99 pages change, all to morphology-based POS.
- A leading `Semantiko:` keyword other than substantivo/pronomo no longer sets the POS of an Ido `-o` word: "Partikulo qua ..." made `artiklo`, `iono`, `prefixo` and 5 other nouns `ij`, "verbo di pasiva formo" made `deponento` a verb.
- Ido euphonic forms: the monodix generates `a`/`e`/`o` (pr/cnjcoo) with a post-generation alarm, and `ad`/`ed`/`od` are analysis-only; apertium-ido-epo's post-generation adds the `d` before a vowel.
- Case sensitivity issue for proper nouns in translation pipeline
- Missing paradigm definition for proper nouns (`np__np`)

