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
- Case sensitivity issue for proper nouns in translation pipeline
- Missing paradigm definition for proper nouns (`np__np`)

