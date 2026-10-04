# Quality detail — 2026-10-04

- Gold set: `data/gold/epo_ido.tsv` (162 sentences)
- Coverage: **99.0%** (622/628 word tokens analysed)
- Mean chrF: **94.8**

## By phenomenon

| Tag | N | Mean chrF |
|-----|---|-----------|
| quantifier | 3 | 74.6 |
| elision | 3 | 79.5 |
| article | 3 | 79.5 |
| wikipedia | 4 | 85.1 |
| number | 7 | 85.6 |
| possessive | 13 | 88.5 |
| derivation | 5 | 88.6 |
| plural | 22 | 89.4 |
| comparative | 4 | 91.0 |
| reflexive | 5 | 91.9 |
| accusative | 30 | 92.1 |
| preposition | 20 | 93.0 |
| conjunction | 4 | 94.0 |
| agreement | 22 | 95.1 |
| pronoun | 40 | 95.4 |
| relative | 5 | 95.5 |
| question | 10 | 95.7 |
| negation | 5 | 97.0 |
| tense | 21 | 97.5 |
| participle | 8 | 97.9 |
| correlative | 29 | 98.3 |
| function | 14 | 98.7 |
| predicate | 8 | 98.7 |
| basic | 7 | 100.0 |
| mood | 6 | 100.0 |
| passive | 4 | 100.0 |
| adverb | 3 | 100.0 |
| copula | 3 | 100.0 |

## Flagged sentences (10) — chrF < 70 or unknown words

- chrF 50 [number,plural]
    - in : Tri infanoj ludas.
    - got: Tri infanti ludas.
    - ref: Tri pueri ludas.
- chrF 57 [question]
    - in : Ĉu vi venas?
    - got: Ka tu venas?
    - ref: Kad vu venas?
- chrF 58 [agreement,plural,quantifier]
    - in : Multaj infanoj kantas.
    - got: Multa infanti kantas.
    - ref: Multa pueri kantas.
- chrF 58 [possessive]
    - in : Via infano estas juna.
    - got: Via infanto esas yuna.
    - ref: Vua filio esas yuna.
- chrF 66 [agreement,plural,quantifier]
    - in : Kelkaj junaj infanoj ludas.
    - got: Kelka yuna infanti ludas.
    - ref: Kelka yuna pueri ludas.
- chrF 72 [wikipedia,preposition]  unknown=['troviĝas']
    - in : Stepo troviĝas en Centra Azio.
    - got: Stepo *troviĝas en Centra Azia.
    - ref: Stepo trovesas en Central Azia.
- chrF 77 [wikipedia,plural,preposition]  unknown=['Franklin']
    - in : Franklin estis unu el la fondintoj de Usono.
    - got: *Franklin esis un ek la fonderi de Usa.
    - ref: Franklin esis un ek la fondinti di Usa.
- chrF 86 [preposition,function]  unknown=['Maria']
    - in : La libro de Maria estas ĉi tie.
    - got: La libro de *Maria esas hike.
    - ref: La libro di Maria esas hike.
- chrF 99 [possessive]  unknown=['Mario']
    - in : Lia nomo estas Mario.
    - got: Ilua nomo esas *Mario.
    - ref: Lua nomo esas Mario.
- chrF 100 [wikipedia,tense,conjunction]  unknown=['Benjamin', 'Franklin']
    - in : Benjamin Franklin estis usona politikisto kaj inventisto.
    - got: *Benjamin *Franklin esis usana politikisto ed inventisto.
    - ref: Benjamin Franklin esis Usana politikisto ed inventisto.
