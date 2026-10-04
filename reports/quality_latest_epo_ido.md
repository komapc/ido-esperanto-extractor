# Quality detail — 2026-10-04

- Gold set: `data/gold/epo_ido.tsv` (162 sentences)
- Coverage: **99.0%** (622/628 word tokens analysed)
- Mean chrF: **92.4**

## By phenomenon

| Tag | N | Mean chrF |
|-----|---|-----------|
| passive | 4 | 70.7 |
| quantifier | 3 | 74.6 |
| elision | 3 | 79.5 |
| article | 3 | 79.5 |
| comparative | 4 | 80.7 |
| participle | 8 | 80.9 |
| wikipedia | 4 | 85.1 |
| number | 7 | 85.6 |
| conjunction | 4 | 86.0 |
| possessive | 13 | 88.5 |
| derivation | 5 | 88.6 |
| tense | 21 | 89.3 |
| plural | 22 | 89.4 |
| preposition | 20 | 89.9 |
| function | 14 | 90.9 |
| reflexive | 5 | 91.9 |
| accusative | 30 | 92.1 |
| pronoun | 40 | 93.5 |
| agreement | 22 | 95.1 |
| relative | 5 | 95.5 |
| question | 10 | 95.7 |
| correlative | 29 | 96.8 |
| negation | 5 | 97.0 |
| predicate | 8 | 98.7 |
| basic | 7 | 100.0 |
| mood | 6 | 100.0 |
| adverb | 3 | 100.0 |
| copula | 3 | 100.0 |

## Flagged sentences (18) — chrF < 70 or unknown words

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
- chrF 58 [correlative]
    - in : Io estas ĉi tie.
    - got: Ulo esas ca ibe.
    - ref: Ulo esas hike.
- chrF 58 [possessive]
    - in : Via infano estas juna.
    - got: Via infanto esas yuna.
    - ref: Vua filio esas yuna.
- chrF 59 [comparative,pronoun]
    - in : Mi estas tiel forta kiel vi.
    - got: Me esas tale forta quale tu.
    - ref: Me esas tam forta kam tu.
- chrF 65 [function]
    - in : Li estas jam ĉi tie.
    - got: Il esas ja ca ibe.
    - ref: Il esas ja hike.
- chrF 65 [passive,participle,tense]
    - in : La pordo estas malfermata.
    - got: La pordo esas apertata.
    - ref: La pordo apertesas.
- chrF 65 [passive,participle,tense]
    - in : La letero estis skribita.
    - got: La letro esis skribita.
    - ref: La letro skribesis.
- chrF 66 [agreement,plural,quantifier]
    - in : Kelkaj junaj infanoj ludas.
    - got: Kelka yuna infanti ludas.
    - ref: Kelka yuna pueri ludas.
- chrF 67 [pronoun]
    - in : Vi venas.
    - got: Tu venas.
    - ref: Vi venas.
- chrF 67 [preposition,function]  unknown=['Maria']
    - in : La libro de Maria estas ĉi tie.
    - got: La libro de *Maria esas ca ibe.
    - ref: La libro di Maria esas hike.
- chrF 68 [conjunction]
    - in : Pano aŭ akvo.
    - got: Pano od aquo.
    - ref: Pano o aquo.
- chrF 70 [preposition,function,tense]
    - in : Mi restos ĉi tie ĝis lundo.
    - got: Me restos ca ibe til lundio.
    - ref: Me restos hike til lundi.
- chrF 72 [wikipedia,preposition]  unknown=['troviĝas']
    - in : Stepo troviĝas en Centra Azio.
    - got: Stepo *troviĝas en Centra Azia.
    - ref: Stepo trovesas en Central Azia.
- chrF 77 [wikipedia,plural,preposition]  unknown=['Franklin']
    - in : Franklin estis unu el la fondintoj de Usono.
    - got: *Franklin esis un ek la fonderi de Usa.
    - ref: Franklin esis un ek la fondinti di Usa.
- chrF 99 [possessive]  unknown=['Mario']
    - in : Lia nomo estas Mario.
    - got: Ilua nomo esas *Mario.
    - ref: Lua nomo esas Mario.
- chrF 100 [wikipedia,tense,conjunction]  unknown=['Benjamin', 'Franklin']
    - in : Benjamin Franklin estis usona politikisto kaj inventisto.
    - got: *Benjamin *Franklin esis usana politikisto ed inventisto.
    - ref: Benjamin Franklin esis Usana politikisto ed inventisto.
