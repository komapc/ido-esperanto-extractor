#!/bin/bash
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║          IDO WIKIPEDIA VOCABULARY EXTRACTION - RESULTS             ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo
echo "📊 SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Total vocabulary extracted:     12,587 NEW words"
echo "  Already in dictionary:           2,717 words"
echo "  Categorized for review:          4,669 common vocabulary"
echo "                                     124 geographic names"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
echo "📁 OUTPUT FILES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ls -lh ido_wiki_vocab_*.csv | awk '{printf "  %-40s %8s\n", $9, $5}'
echo
echo "🎯 RECOMMENDED REVIEW ORDER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  1. ido_wiki_vocab_vocabulary.csv   (4,669 entries) ← START HERE"
echo "  2. ido_wiki_vocab_geographic.csv   (  124 entries)"
echo "  3. ido_wiki_vocab_other.csv        (2,211 entries)"
echo "  4. ido_wiki_vocab_person.csv       (5,583 entries) ← Skip/low priority"
echo
echo "📚 SAMPLE VOCABULARY (Common Nouns/Terms)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
head -31 ido_wiki_vocab_vocabulary.csv | tail -30 | awk -F',' '{printf "  %-30s → %-30s\n", $1, $2}' | head -20
echo
