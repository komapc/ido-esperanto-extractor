#!/usr/bin/env bash
set -euo pipefail

# Compare translations between old and new dictionaries
# Usage: ./compare_dictionaries.sh [test_file.txt]

PAIR_DIR="/home/mark/apertium-ido-epo/apertium/apertium-ido-epo"
EXTRACTOR_DIR="/home/mark/apertium-ido-epo/tools/extractor/ido-esperanto-extractor"
BACKUP_DIR="$EXTRACTOR_DIR/backup_old_dix"
TEST_FILE="${1:-$EXTRACTOR_DIR/test_sentences.txt}"

echo "🔄 Dictionary Comparison Tool"
echo "=============================="

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Step 1: Test with OLD dictionaries
echo ""
echo "📊 Step 1: Testing with OLD dictionaries..."
echo "-------------------------------------------"
cd "$PAIR_DIR"
if [ ! -f "ido-epo.automorf.bin" ]; then
    echo "Building old dictionaries..."
    make
fi
if [ ! -d "modes" ]; then
    echo "Building modes..."
    make modes
fi

echo ""
echo "Translating test sentences with OLD dictionary:"
if [ -f "$TEST_FILE" ]; then
    > /tmp/old_translations.txt
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            echo "IDO: $line" | tee -a /tmp/old_translations.txt
            result=$(echo "$line" | apertium -d . ido-epo 2>&1 || echo "[TRANSLATION ERROR]")
            echo "EPO: $result" | tee -a /tmp/old_translations.txt
            echo "" | tee -a /tmp/old_translations.txt
        fi
    done < "$TEST_FILE"
else
    echo "Test file not found: $TEST_FILE"
    exit 1
fi

# Step 2: Backup old dictionaries and install new ones
echo ""
echo "💾 Step 2: Backing up old dictionaries and installing new ones..."
echo "----------------------------------------------------------------"
cp "$PAIR_DIR/apertium-ido.ido.dix" "$BACKUP_DIR/apertium-ido.ido.dix.old"
cp "$PAIR_DIR/apertium-ido-epo.ido-epo.dix" "$BACKUP_DIR/apertium-ido-epo.ido-epo.dix.old"

# Install new dictionaries
cp "$EXTRACTOR_DIR/dist/apertium-ido.ido.dix" "$PAIR_DIR/apertium-ido.ido.dix"
cp "$EXTRACTOR_DIR/dist/apertium-ido-epo.ido-epo.dix" "$PAIR_DIR/apertium-ido-epo.ido-epo.dix"

echo "Rebuilding with NEW dictionaries..."
cd "$PAIR_DIR"
make clean
make
make modes

# Step 3: Test with NEW dictionaries
echo ""
echo "📊 Step 3: Testing with NEW dictionaries..."
echo "-------------------------------------------"
echo "Translating test sentences with NEW dictionary:"
> /tmp/new_translations.txt
while IFS= read -r line; do
    if [ -n "$line" ]; then
        echo "IDO: $line" | tee -a /tmp/new_translations.txt
        result=$(echo "$line" | apertium -d . ido-epo 2>&1 || echo "[TRANSLATION ERROR]")
        echo "EPO: $result" | tee -a /tmp/new_translations.txt
        echo "" | tee -a /tmp/new_translations.txt
    fi
done < "$TEST_FILE"

# Step 4: Generate comparison report
echo ""
echo "📋 Step 4: Generating comparison report..."
echo "------------------------------------------"
python3 << 'PYEOF'
import sys

print("=" * 70)
print("TRANSLATION COMPARISON REPORT")
print("=" * 70)
print()

with open('/tmp/old_translations.txt', 'r') as f:
    old_lines = f.readlines()

with open('/tmp/new_translations.txt', 'r') as f:
    new_lines = f.readlines()

i = 0
sentence_num = 0
same_count = 0
changed_count = 0
old_errors = 0
new_errors = 0

while i < len(old_lines):
    if old_lines[i].startswith("IDO:"):
        sentence_num += 1
        ido_text = old_lines[i].replace("IDO:", "").strip()
        old_epo = old_lines[i+1].replace("EPO:", "").strip() if i+1 < len(old_lines) else ""
        new_epo = new_lines[i+1].replace("EPO:", "").strip() if i+1 < len(new_lines) else ""
        
        print(f"Sentence {sentence_num}:")
        print(f"  IDO: {ido_text}")
        print(f"  OLD: {old_epo}")
        print(f"  NEW: {new_epo}")
        
        if "[ERROR]" in old_epo or "[TRANSLATION ERROR]" in old_epo:
            old_errors += 1
        if "[ERROR]" in new_epo or "[TRANSLATION ERROR]" in new_epo:
            new_errors += 1
            
        if old_epo == new_epo:
            print(f"  ✅ SAME")
            same_count += 1
        else:
            print(f"  🔄 CHANGED")
            changed_count += 1
        print()
        i += 3
    else:
        i += 1

print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total sentences: {sentence_num}")
print(f"Same: {same_count}")
print(f"Changed: {changed_count}")
print(f"OLD dictionary errors: {old_errors}")
print(f"NEW dictionary errors: {new_errors}")
if old_errors > new_errors:
    print(f"✅ NEW dictionary fixed {old_errors - new_errors} error(s)!")
elif new_errors > old_errors:
    print(f"⚠️  NEW dictionary introduced {new_errors - old_errors} error(s)")
print("=" * 70)
PYEOF

# Step 5: Ask user what to do
echo ""
echo "🔧 Step 5: Restore old dictionaries or keep new ones?"
echo "-----------------------------------------------------"
read -p "Keep NEW dictionaries? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restoring OLD dictionaries..."
    cp "$BACKUP_DIR/apertium-ido.ido.dix.old" "$PAIR_DIR/apertium-ido.ido.dix"
    cp "$BACKUP_DIR/apertium-ido-epo.ido-epo.dix.old" "$PAIR_DIR/apertium-ido-epo.ido-epo.dix"
    cd "$PAIR_DIR"
    make clean
    make
    make modes
    echo "✅ Old dictionaries restored"
else
    echo "✅ New dictionaries kept"
fi

echo ""
echo "Done! Backup of old dictionaries saved in: $BACKUP_DIR"
echo "Comparison logs saved in: /tmp/old_translations.txt and /tmp/new_translations.txt"
