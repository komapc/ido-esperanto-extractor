# Morphological Rules Development Guide

This guide explains how to develop, test, and maintain morphological rules for the Ido-Esperanto translation system.

## 🏗️ Architecture Overview

The dictionary system now uses a **separation of concerns** approach:

```
apertium-ido-epo/
├── rules/
│   └── apertium-ido.ido.dix.rules    # Morphological rules (preserved)
├── scripts/
│   ├── merge_with_extractor.py       # Merge rules + words
│   └── rule_development_workflow.sh  # Development workflow
├── apertium-ido.ido.dix              # Complete dictionary (generated)
└── extractor_output.json             # Word entries from extractor
```

### Key Benefits

- ✅ **Rules preserved** during extractor runs
- ✅ **Clean separation** of rules vs. words
- ✅ **Easy rule development** workflow
- ✅ **Version control** for rule changes
- ✅ **Integration** with Apertium pipeline

## 🚀 Quick Start

### 1. Edit Rules
```bash
./scripts/rule_development_workflow.sh edit-rules
```

### 2. Test Rules
```bash
./scripts/rule_development_workflow.sh test-rules
```

### 3. Full Test Suite
```bash
./scripts/rule_development_workflow.sh full-test
```

## 📋 Complete Workflow

### Phase 1: Rule Development

1. **Edit Rules File**
   ```bash
   ./scripts/rule_development_workflow.sh edit-rules
   ```
   - Opens `rules/apertium-ido.ido.dix.rules` in your editor
   - Contains all morphological paradigms and symbol definitions

2. **Test Rules Syntax**
   ```bash
   ./scripts/rule_development_workflow.sh test-rules
   ```
   - Validates XML syntax
   - Tests with sample data
   - Ensures rules are well-formed

### Phase 2: Integration Testing

3. **Build Complete Dictionary**
   ```bash
   ./scripts/rule_development_workflow.sh build
   ```
   - Merges rules with word entries
   - Creates `apertium-ido.ido.dix`
   - Validates final dictionary

4. **Test Translation**
   ```bash
   ./scripts/rule_development_workflow.sh test-translate
   ```
   - Tests sample sentences
   - Verifies translation quality
   - Checks both directions (Ido→Esperanto, Esperanto→Ido)

### Phase 3: Validation

5. **Validate Dictionary**
   ```bash
   ./scripts/rule_development_workflow.sh validate
   ```
   - XML syntax validation
   - Apertium compatibility check
   - Error detection

6. **Full Test Suite**
   ```bash
   ./scripts/rule_development_workflow.sh full-test
   ```
   - Runs all tests in sequence
   - Comprehensive validation
   - Ready for production

## 🔧 Manual Commands

### Merge Rules with Extractor Output
```bash
python3 scripts/merge_with_extractor.py \
  --rules-file rules/apertium-ido.ido.dix.rules \
  --extractor-file extractor_output.json \
  --output-file apertium-ido.ido.dix \
  --validate
```

### Test with Sample Data
```bash
python3 scripts/merge_with_extractor.py --test-mode --validate
```

### Validate XML Syntax
```bash
xmllint --noout apertium-ido.ido.dix
```

## 📝 Rule Development Guidelines

### Adding New Paradigms

1. **Edit Rules File**
   ```bash
   vim rules/apertium-ido.ido.dix.rules
   ```

2. **Add Paradigm Definition**
   ```xml
   <pardef n="new_paradigm">
     <e>
       <p>
         <l>ending</l>
         <r>
           <s n="pos" />
           <s n="feature" />
         </r>
       </p>
     </e>
   </pardef>
   ```

3. **Test the Paradigm**
   ```bash
   ./scripts/rule_development_workflow.sh test-rules
   ```

### Modifying Existing Paradigms

1. **Backup Current Rules**
   ```bash
   cp rules/apertium-ido.ido.dix.rules rules/apertium-ido.ido.dix.rules.backup
   ```

2. **Edit Rules**
   ```bash
   ./scripts/rule_development_workflow.sh edit-rules
   ```

3. **Test Changes**
   ```bash
   ./scripts/rule_development_workflow.sh full-test
   ```

## 🧪 Testing Strategy

### Unit Testing
- **Rules Syntax**: XML validation
- **Paradigm Logic**: Sample word testing
- **Integration**: Dictionary merging

### Integration Testing
- **Translation Quality**: Sample sentences
- **Bidirectional**: Both language directions
- **Edge Cases**: Special characters, numbers

### Regression Testing
- **Before Changes**: Backup current state
- **After Changes**: Compare with previous
- **Automated**: Use test suite

## 🔄 Extractor Integration

### Automatic Workflow
1. **Extractor runs** and generates `extractor_output.json`
2. **Merge script** combines rules + words
3. **Dictionary updated** with new words
4. **Rules preserved** from previous version

### Manual Override
```bash
# Use specific extractor file
python3 scripts/merge_with_extractor.py \
  --extractor-file custom_extractor_output.json

# Use test data instead
python3 scripts/merge_with_extractor.py --test-mode
```

## 🐛 Troubleshooting

### Common Issues

1. **XML Parse Error**
   ```bash
   # Check syntax
   xmllint --noout rules/apertium-ido.ido.dix.rules
   ```

2. **Missing Paradigm**
   ```bash
   # Test with sample data
   ./scripts/rule_development_workflow.sh test-rules
   ```

3. **Translation Failures**
   ```bash
   # Test specific sentences
   echo "test sentence" | apertium ido-epo
   ```

### Debug Mode
```bash
# Verbose output
python3 scripts/merge_with_extractor.py --test-mode --validate -v

# Check intermediate files
ls -la rules/ scripts/ *.dix
```

## 📚 File Structure

### Rules File (`rules/apertium-ido.ido.dix.rules`)
- **Symbol definitions** (`<sdefs>`)
- **Morphological paradigms** (`<pardefs>`)
- **No word entries** (preserved separately)

### Merge Script (`scripts/merge_with_extractor.py`)
- **Loads rules** from rules file
- **Loads words** from extractor output
- **Combines** into complete dictionary
- **Validates** final result

### Workflow Script (`scripts/rule_development_workflow.sh`)
- **Edit rules** with proper editor
- **Test rules** with sample data
- **Build dictionary** from rules + words
- **Validate** final dictionary
- **Test translation** with sample sentences

## 🎯 Best Practices

### Rule Development
- **Test frequently** during development
- **Use descriptive names** for paradigms
- **Document complex rules** with comments
- **Version control** all changes

### Quality Assurance
- **Run full test suite** before committing
- **Validate XML syntax** after changes
- **Test translation quality** with real sentences
- **Check both directions** (Ido↔Esperanto)

### Maintenance
- **Backup rules** before major changes
- **Keep rules file** in version control
- **Document changes** in commit messages
- **Monitor translation quality** over time

## 🔗 Integration with Apertium

### Build Process
```bash
# Standard Apertium build
make clean && make

# With rule updates
./scripts/rule_development_workflow.sh full-test
make clean && make
```

### Testing Integration
```bash
# Test with Apertium pipeline
echo "Me esas bona" | apertium ido-epo
echo "Mi estas bona" | apertium epo-ido
```

## 📖 Additional Resources

- [Apertium Documentation](https://wiki.apertium.org/)
- [Ido Grammar Reference](https://ido.lingvo.net/)
- [Esperanto Grammar](https://en.wikipedia.org/wiki/Esperanto_grammar)
- [XML Schema Validation](https://www.w3.org/XML/Schema)

---

**Remember**: Always test your changes thoroughly before committing to the main repository!
