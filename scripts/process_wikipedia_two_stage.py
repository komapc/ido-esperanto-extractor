#!/usr/bin/env python3
"""
Two-stage Wikipedia processing with resumability.
Stage 1: XML → Filtered JSON
Stage 2: JSON → Final Processing
"""
import argparse
import logging
import subprocess
import sys
from pathlib import Path

from _common import configure_logging


def run_stage(stage_script: str, description: str) -> bool:
    """Run a processing stage and return success status."""
    logging.info("=" * 60)
    logging.info("Running %s", description)
    logging.info("=" * 60)
    
    try:
        result = subprocess.run([sys.executable, stage_script], 
                              capture_output=True, text=True, check=True)
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
    ap = argparse.ArgumentParser(description="Two-stage Wikipedia processing with resumability")
    ap.add_argument("--input", type=Path, 
                   default=Path(__file__).resolve().parents[1] / "data/raw/iowiki-latest-pages-articles.xml.bz2")
    ap.add_argument("--stage1-out", type=Path,
                   default=Path(__file__).resolve().parents[1] / "work/io_wikipedia_filtered.json")
    ap.add_argument("--stage2-out", type=Path,
                   default=Path(__file__).resolve().parents[1] / "work/io_wikipedia_processed.json")
    ap.add_argument("--skip-stage1", action="store_true", help="Skip Stage 1 (XML → Filtered JSON)")
    ap.add_argument("--skip-stage2", action="store_true", help="Skip Stage 2 (JSON → Final Processing)")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(argv)

    configure_logging(args.verbose)
    
    # Get script directory
    script_dir = Path(__file__).parent
    stage1_script = script_dir / "01_extract_wikipedia_filtered.py"
    stage2_script = script_dir / "02_process_wikipedia_final.py"
    
    logging.info("Two-stage Wikipedia processing starting...")
    logging.info("Input: %s", args.input)
    logging.info("Stage 1 output: %s", args.stage1_out)
    logging.info("Stage 2 output: %s", args.stage2_out)
    
    # Check input file
    if not args.input.exists():
        logging.error("Input file %s does not exist", args.input)
        return 1
    
    # Stage 1: XML → Filtered JSON
    if not args.skip_stage1:
        if args.stage1_out.exists():
            logging.info("Stage 1 output already exists, skipping...")
        else:
            success = run_stage(str(stage1_script), "Stage 1: XML → Filtered JSON")
            if not success:
                return 1
    else:
        logging.info("Skipping Stage 1 as requested")
    
    # Stage 2: JSON → Final Processing
    if not args.skip_stage2:
        if args.stage2_out.exists():
            logging.info("Stage 2 output already exists, skipping...")
        else:
            success = run_stage(str(stage2_script), "Stage 2: JSON → Final Processing")
            if not success:
                return 1
    else:
        logging.info("Skipping Stage 2 as requested")
    
    logging.info("=" * 60)
    logging.info("Two-stage Wikipedia processing completed successfully!")
    logging.info("=" * 60)
    
    # Show final statistics
    if args.stage2_out.exists():
        from _common import read_json
        final_data = read_json(args.stage2_out)
        logging.info("Final output: %d Wikipedia entries processed", len(final_data))
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
