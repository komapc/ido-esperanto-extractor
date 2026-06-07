# Vortaro Quality

_Generated 2026-06-07 — ranker: `insertion`, recall top-N: 5000_

## precision@1 (ranking)
**93.4%** (1932/2069 eligible entries)

Top-1 of held-out non-Wiktionary candidates vs the io_wiktionary reference.

### Ranking: closed (measured negative result)
Every ranker smarter than insertion *regresses* precision@1 (computed live):
`insertion` 93.4%, `srcrank` 93.2%, `srcrank_corr (corroboration)` 55.7%, `confidence (cognate)` 78.5%.
precision@1 also holds out io_wiktionary, so it is blind to
no-curated-source entries — exactly where ranking picks the user-visible
#1 — and the live export keeps io_wiktionary on top by source rank, so live
ranking is ≥ measured. The export stays on the source-rank order
(`conflict_resolution.confidence_key`); `confidence_score` remains in the
tree as the measured-and-rejected alternative. Do not reopen.

### Sample misranks (chosen → reference)
- `abrogar`: nuligi → aboli
- `acerba`: akra → acerba
- `akra`: acerba → akra/akuta/aspera/pikanta/stridanta
- `akuta`: akra → akuta
- `albo`: padelo → albo
- `alterar`: falsi → aliiĝi
- `amento`: katido → amento
- `analoga`: analogia → analoga
- `angulo`: kojno → angulo
- `antipatio`: abomeno → antipatio
- `aplikar`: administri → apliki
- `arbusto`: arbusto → arbedo
- `atakar`: agresi → ataki
- `atesto`: signo → atesto
- `auroro`: padelo → aŭroro
- `avantajo`: profito → avantaĝo
- `avokado`: advokato → avokado
- `barko`: boato → barko
- `baterio`: pilo → baterio
- `biblioteko`: librejo → biblioteko
- `burso`: stipendio → burso
- `buxo`: skatolo → kesto
- `cilio`: okulharo → cilio
- `disputar`: kvereli → disputi
- `domeno`: limo → bieno

## recall (coverage)
**type 84.1%** (3330/3961 lemmas) · **token-weighted 92.1%**

Top-5000 io.wiki tokens, junk-stripped (shared `lexicon_filters`), then
lemmatized to citation form via the monodix (root + POS ending, since the
analyser emits bare roots); covered = the lemma has any EO translation.

Two effects lift this over the old 61.2% type / 76.0% token baseline:
citation-form reconstruction alone (inflected tokens now map to their
lemma) reaches ~79.7% type, and junk-stripping the denominator — which
drops foreign-script proper nouns (`białystok`, `łódź`) and MediaWiki
artifacts, by design — narrows it to the current figure. This measures
ASCII common-vocabulary coverage, not proper-noun recall.

### Sample misses
- mezvalora, habitanti, sud, hemanari, hemanaro, polona, idala, distas, del, habitis, indijeni, habitesis, latin, hispan, afrikan, aziani, capita, pacifik, alidirekti, nobel, ak, usan, laureato, chef, mezavalora, au, of, us, exloko, uniono, infinita, nacionala, algarismi, pozitiv, seguo, vilajal, estala, astronomial, podlaska, nenomizit, lubelski, and, subkarpati, distis, lor, milion, louis, tenisistino, sovietiana, bielorusa
