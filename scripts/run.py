#!/usr/bin/env python3
"""
Orthogonal Pipeline - Master Control Script

Orchestrates the entire extraction pipeline with smart caching:
1. Download dumps (if needed)
2. Parse sources (if dumps are newer than sources)
3. Merge sources (always run, fast)
4. Export Apertium files (if needed)

Usage:
  ./run.py                          # Full pipeline with smart caching
  ./run.py --force                  # Force full rebuild
  ./run.py --skip-download          # Skip downloading dumps
  ./run.py --parse-only io_wiktionary  # Parse only one source
  ./run.py --merge-only             # Just merge existing sources
  ./run.py --dry-run                # Show what would be executed
"""

import argparse
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.json_utils import load_json, get_file_mtime


# Configuration
CONFIG_FILE = Path(__file__).parent.parent / "config.json"


def load_config():
    """Load configuration from config.json."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}


def run_command(cmd, dry_run=False):
    """Run a shell command."""
    cmd_str = ' '.join(str(c) for c in cmd)
    print(f"\n🚀 Running: {cmd_str}")
    
    if dry_run:
        print("   [DRY RUN - Not actually executing]")
        return 0
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    return result.returncode


def should_parse_source(source_name, dump_file, source_file, force=False):
    """
    Determine if we need to re-parse a source.
    
    Parse if:
    - force is True
    - source file doesn't exist
    - dump file is newer than source file
    - parser script has changed (future enhancement)
    """
    if force:
        return True, "Force rebuild requested"
    
    if not source_file.exists():
        return True, "Source file doesn't exist"
    
    if not dump_file.exists():
        return False, f"Dump file not found: {dump_file}"
    
    dump_mtime = get_file_mtime(dump_file)
    source_mtime = get_file_mtime(source_file)
    
    if dump_mtime > source_mtime:
        age = (datetime.now() - dump_mtime).days
        return True, f"Dump is newer (dump: {age} days old)"
    
    return False, f"Source is up-to-date"


def main(argv):
    ap = argparse.ArgumentParser(
        description="Orthogonal Pipeline Master Control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    ap.add_argument("--force", action="store_true", help="Force full rebuild")
    ap.add_argument("--skip-download", action="store_true", help="Skip downloading dumps")
    ap.add_argument("--skip-parse", action="store_true", help="Skip parsing sources")
    ap.add_argument("--skip-merge", action="store_true", help="Skip merging (useful for testing parsers)")
    ap.add_argument("--skip-export", action="store_true", help="Skip Apertium export")
    ap.add_argument(
        "--parse-only", 
        choices=['io_wiktionary', 'eo_wiktionary', 'fr_wiktionary', 'io_wikipedia'],
        help="Parse only one source"
    )
    ap.add_argument("--merge-only", action="store_true", help="Only run merge step")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be executed")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))
    
    # Load configuration
    config = load_config()
    paths = config.get('paths', {})
    sources_config = config.get('sources', {})
    
    # Setup paths
    base_dir = Path(__file__).parent.parent
    dumps_dir = base_dir / paths.get('dumps_dir', 'dumps')
    sources_dir = base_dir / paths.get('sources_dir', 'sources')
    output_dir = base_dir / paths.get('output_dir', 'output')
    dist_dir = base_dir / paths.get('dist_dir', 'dist')
    
    print("=" * 70)
    print("🎮 ORTHOGONAL PIPELINE - Master Control")
    print("=" * 70)
    print(f"   Config: {CONFIG_FILE}")
    print(f"   Base: {base_dir}")
    print(f"   Dumps: {dumps_dir}")
    print(f"   Sources: {sources_dir}")
    print(f"   Output: {output_dir}")
    
    if args.dry_run:
        print("\n   🔍 DRY RUN MODE - No changes will be made")
    
    # Create directories
    if not args.dry_run:
        dumps_dir.mkdir(exist_ok=True)
        sources_dir.mkdir(exist_ok=True)
        output_dir.mkdir(exist_ok=True)
    
    # Stage 0: Download dumps (if needed)
    if args.merge_only:
        print("\n⏭️  Skipping download and parse (merge-only mode)")
    elif not args.skip_download:
        print("\n" + "=" * 70)
        print("📥 STAGE 0: Download dumps")
        print("=" * 70)
        
        download_script = base_dir / "scripts" / "download_dumps.sh"
        if download_script.exists():
            retcode = run_command(["bash", str(download_script)], args.dry_run)
            if retcode != 0 and not args.dry_run:
                print(f"⚠️  Warning: Download script returned {retcode}")
        else:
            print(f"⚠️  Download script not found: {download_script}")
            print(f"   Continuing with existing dumps...")
    else:
        print("\n⏭️  Skipping download (--skip-download)")
    
    # Stage 1: Parse sources (if needed)
    if args.merge_only:
        pass  # Skip parsing
    elif not args.skip_parse:
        print("\n" + "=" * 70)
        print("📖 STAGE 1: Parse sources")
        print("=" * 70)
        
        # Define parsers
        parsers = {
            'io_wiktionary': {
                'script': 'scripts/01_parse_io_wiktionary.py',
                'dump': 'data/iowiktionary-latest-pages-articles.xml.bz2',
                'output': sources_dir / 'source_io_wiktionary.json',
                'enabled': sources_config.get('io_wiktionary', {}).get('enabled', True)
            },
            'eo_wiktionary': {
                'script': 'scripts/02_parse_eo_wiktionary.py',
                'dump': 'eowiktionary-latest-pages-articles.xml.bz2',
                'output': sources_dir / 'source_eo_wiktionary.json',
                'enabled': sources_config.get('eo_wiktionary', {}).get('enabled', True)
            },
            'fr_wiktionary': {
                'script': 'scripts/03_parse_fr_wiktionary.py',
                'dump': 'data/raw/frwiktionary-latest-pages-articles.xml.bz2',
                'output': sources_dir / 'source_fr_wiktionary.json',
                'enabled': sources_config.get('fr_wiktionary', {}).get('enabled', False)
            },
            'io_wikipedia': {
                'script': 'scripts/04_parse_io_wikipedia.py',
                'dump': 'iowiki-latest-langlinks.sql.gz',
                'output': sources_dir / 'source_io_wikipedia.json',
                'enabled': sources_config.get('io_wikipedia', {}).get('enabled', True)
            }
        }
        
        # Filter by --parse-only
        if args.parse_only:
            parsers = {k: v for k, v in parsers.items() if k == args.parse_only}
        
        # Run parsers
        for source_name, parser_info in parsers.items():
            if not parser_info['enabled']:
                print(f"\n⏭️  Skipping {source_name} (disabled in config)")
                continue
            
            script = base_dir / parser_info['script']
            dump_file = base_dir / parser_info['dump']
            source_file = parser_info['output']
            
            # Check if we need to parse
            should_parse, reason = should_parse_source(
                source_name, dump_file, source_file, args.force
            )
            
            print(f"\n📖 {source_name}:")
            print(f"   Script: {script.name}")
            print(f"   Dump: {dump_file.name}")
            print(f"   Output: {source_file.name}")
            print(f"   Status: {reason}")
            
            if should_parse:
                verbose_flag = ["-v"] * args.verbose if args.verbose else []
                retcode = run_command(
                    ["python3", str(script)] + verbose_flag,
                    args.dry_run
                )
                if retcode != 0 and not args.dry_run:
                    print(f"❌ Error: Parser failed with return code {retcode}")
                    return retcode
            else:
                print(f"   ✅ Up-to-date, skipping")
    else:
        print("\n⏭️  Skipping parse (--skip-parse)")
    
    # Stage 2: Merge sources (always run, fast)
    if not args.skip_merge:
        print("\n" + "=" * 70)
        print("🔄 STAGE 2: Merge sources")
        print("=" * 70)
        
        merge_script = base_dir / "scripts" / "10_merge.py"
        verbose_flag = ["-v"] * args.verbose if args.verbose else []
        retcode = run_command(
            ["python3", str(merge_script)] + verbose_flag,
            args.dry_run
        )
        if retcode != 0 and not args.dry_run:
            print(f"❌ Error: Merge failed with return code {retcode}")
            return retcode
    else:
        print("\n⏭️  Skipping merge (--skip-merge)")
    
    # Stage 3: Export Apertium (if needed)
    if not args.skip_export and not args.merge_only:
        print("\n" + "=" * 70)
        print("📦 STAGE 3: Export Apertium files")
        print("=" * 70)
        
        export_script = base_dir / "scripts" / "export_apertium.py"
        if export_script.exists():
            verbose_flag = ["-v"] * args.verbose if args.verbose else []
            retcode = run_command(
                ["python3", str(export_script)] + verbose_flag,
                args.dry_run
            )
            if retcode != 0 and not args.dry_run:
                print(f"⚠️  Warning: Export script returned {retcode}")
        else:
            print(f"⚠️  Export script not found: {export_script}")
    else:
        print("\n⏭️  Skipping export (--skip-export or --merge-only)")
    
    # Final summary
    print("\n" + "=" * 70)
    print("✅ PIPELINE COMPLETE!")
    print("=" * 70)
    
    # Show output files
    if output_dir.exists():
        output_files = list(output_dir.glob('*.json'))
        if output_files:
            print(f"\n📂 Output files ({output_dir}):")
            for file in sorted(output_files):
                size_kb = file.stat().st_size / 1024
                print(f"   {file.name:20s} ({size_kb:,.0f} KB)")
    
    print(f"\n💡 Next steps:")
    print(f"   - Review output files in {output_dir}/")
    print(f"   - Copy vortaro.json to vortaro repo for website")
    print(f"   - Test translation quality with Apertium")
    
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

