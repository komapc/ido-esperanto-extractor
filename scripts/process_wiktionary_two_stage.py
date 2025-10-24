#!/usr/bin/env python3
"""
Two-stage Wiktionary processing with resumability.
Stage 1: XML → Filtered JSON
Stage 2: JSON → Final Processing
"""
import argparse
import logging
import subprocess
import sys
from pathlib import Path

from _common import configure_logging


def run_stage(stage_script: str, args: list, description: str) -> bool:
    """Run a processing stage and return success status."""
    logging.info("=" * 60)
    logging.info("Running %s", description)
    logging.info("=" * 60)
    
    try:
        cmd = [sys.executable, stage_script] + args
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logging.info("✓ %s completed successfully", description)
        if result.stdout:
            logging.info("Output: %s", result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        logging.error("✗ %s failed with exit code %d", description, e.returncode)
        if e.stdout:
            logging.error("Stdout: %s", e.stdout)
        if e.stderr:
            logging.error("Stderr: %s", e.stderr)
        return False


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Two-stage Wiktionary processing with resumability")
    ap.add_argument("--source", required=True, choices=['io', 'eo', 'fr', 'en'], 
                   help="Source language code")
    ap.add_argument("--target", default="eo", help="Target language code")
    ap.add_argument("--dump", type=Path, help="Path to Wiktionary dump file")
    ap.add_argument("--stage1-out", type=Path, help="Stage 1 output path")
    ap.add_argument("--stage2-out", type=Path, help="Stage 2 output path")
    ap.add_argument("--skip-stage1", action="store_true", help="Skip Stage 1 (XML → Filtered JSON)")
    ap.add_argument("--skip-stage2", action="store_true", help="Skip Stage 2 (JSON → Final Processing)")
    ap.add_argument("--limit", type=int, help="Limit number of pages to parse (for testing)")
    ap.add_argument("--progress-every", type=int, default=1000)
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(argv)

    configure_logging(args.verbose)
    
    # Get script directory
    script_dir = Path(__file__).parent
    stage1_script = script_dir / "01_parse_wiktionary_filtered.py"
    stage2_script = script_dir / "02_process_wiktionary_final.py"
    
    # Set default paths
    base_dir = Path(__file__).parent.parent
    if not args.stage1_out:
        args.stage1_out = base_dir / "work" / f"{args.source}_wiktionary_filtered.json"
    if not args.stage2_out:
        args.stage2_out = base_dir / "work" / f"{args.source}_wiktionary_processed.json"
    
    logging.info("Two-stage %s Wiktionary processing starting...", args.source.upper())
    logging.info("Source: %s, Target: %s", args.source, args.target)
    logging.info("Stage 1 output: %s", args.stage1_out)
    logging.info("Stage 2 output: %s", args.stage2_out)
    
    # Build common arguments
    common_args = [
        "--source", args.source,
        "--target", args.target,
        "-v" if args.verbose else ""
    ]
    if args.dump:
        common_args.extend(["--dump", str(args.dump)])
    if args.limit:
        common_args.extend(["--limit", str(args.limit)])
    if args.progress_every:
        common_args.extend(["--progress-every", str(args.progress_every)])
    
    # Remove empty strings
    common_args = [arg for arg in common_args if arg]
    
    # Stage 1: XML → Filtered JSON
    if not args.skip_stage1:
        if args.stage1_out.exists():
            logging.info("Stage 1 output already exists, skipping...")
        else:
            stage1_args = common_args + ["--output", str(args.stage1_out)]
            success = run_stage(str(stage1_script), stage1_args, 
                              f"Stage 1: {args.source.upper()} Wiktionary XML → Filtered JSON")
            if not success:
                return 1
    else:
        logging.info("Skipping Stage 1 as requested")
    
    # Stage 2: JSON → Final Processing
    if not args.skip_stage2:
        if args.stage2_out.exists():
            logging.info("Stage 2 output already exists, skipping...")
        else:
            stage2_args = ["--source", args.source, "--input", str(args.stage1_out), 
                          "--output", str(args.stage2_out)]
            if args.verbose:
                stage2_args.append("-v")
            success = run_stage(str(stage2_script), stage2_args, 
                              f"Stage 2: {args.source.upper()} Wiktionary JSON → Final Processing")
            if not success:
                return 1
    else:
        logging.info("Skipping Stage 2 as requested")
    
    logging.info("=" * 60)
    logging.info("Two-stage %s Wiktionary processing completed successfully!", args.source.upper())
    logging.info("=" * 60)
    
    # Show final statistics
    if args.stage2_out.exists():
        from _common import read_json
        final_data = read_json(args.stage2_out)
        entries = final_data.get('entries', [])
        logging.info("Final output: %d %s Wiktionary entries processed", len(entries), args.source.upper())
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
