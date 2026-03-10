import sys
import os
from pathlib import Path

# Add scripts to path for importing
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from wiktionary_parser import clean_translation_text

def test_template_extraction():
    test_cases = [
        # Basic templates
        ("{{t|eo|kultura}}", "kultura"),
        ("{{t+|eo|kultura}}", "kultura"),
        ("{{l|eo|kultura}}", "kultura"),
        
        # Templates with extra parameters (should be stripped)
        ("{{t|eo|kultura|alt=something}}", "kultura"),
        ("{{t+|eo|kultura|tr=pronunciation}}", "kultura"),
        ("{{t|eo|kultura|id=1}}", "kultura"),
        
        # Mixed content
        ("kultura [[something]]", "kultura something"),
        ("* {{eo}}: {{t|eo|kultura}}", "* : kultura"),
        
        # Multiple templates
        ("{{t|eo|kultura}}, {{t|eo|civilizo}}", "kultura, civilizo"),
        
        # Nesting or technical artifacts (should be handled gracefully)
        ("{{t|eo|kultura|sc=Latn}}", "kultura"),
    ]
    
    print("Running Parser Regression Tests...")
    passed = 0
    for i, (input_text, expected) in enumerate(test_cases, 1):
        result = clean_translation_text(input_text)
        if result == expected:
            print(f"  [✓] Test {i} passed")
            passed += 1
        else:
            print(f"  [✗] Test {i} failed!")
            print(f"      Input:    {input_text}")
            print(f"      Expected: {expected}")
            print(f"      Got:      {result}")
            
    print(f"\nSummary: {passed}/{len(test_cases)} tests passed.")
    return passed == len(test_cases)

if __name__ == "__main__":
    success = test_template_extraction()
    sys.exit(0 if success else 1)
