#!/usr/bin/env python3
"""
Pipeline Manager for Ido-Esperanto Extractor

Implements stage-based resumability with state tracking, error handling,
and progress visualization.

Usage:
    python3 scripts/pipeline_manager.py [--force] [--stage STAGE_NAME]
    python3 scripts/pipeline_manager.py --status
"""

import argparse
import json
import logging
import sys
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from _common import configure_logging


@dataclass
class StageState:
    """State for a single pipeline stage."""
    name: str
    status: str  # pending, running, completed, failed, skipped
    output: Optional[str] = None
    error: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StageState':
        return cls(**data)


@dataclass
class PipelineState:
    """Complete pipeline state."""
    stages: Dict[str, StageState]
    last_update: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'stages': {name: stage.to_dict() for name, stage in self.stages.items()},
            'last_update': self.last_update
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PipelineState':
        stages = {name: StageState.from_dict(stage_data) 
                  for name, stage_data in data['stages'].items()}
        return cls(stages=stages, last_update=data['last_update'])


class PipelineManager:
    """Manages pipeline execution with resumability."""
    
    def __init__(self, state_file: Path, force: bool = False):
        self.state_file = state_file
        self.force = force
        self.state = self._load_state()
        
    def _load_state(self) -> PipelineState:
        """Load pipeline state from file."""
        if self.state_file.exists() and not self.force:
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                return PipelineState.from_dict(data)
            except Exception as e:
                logging.warning("Failed to load state file: %s", e)
        
        # Return fresh state
        return PipelineState(stages={}, last_update=datetime.now().isoformat())
    
    def _save_state(self):
        """Save pipeline state to file."""
        self.state.last_update = datetime.now().isoformat()
        with open(self.state_file, 'w') as f:
            json.dump(self.state.to_dict(), f, indent=2)
    
    def _get_stage_status(self, stage_name: str) -> str:
        """Get current status of a stage."""
        if stage_name in self.state.stages:
            return self.state.stages[stage_name].status
        return 'pending'
    
    def _run_stage(self, stage_name: str, command: List[str], 
                   description: str, skip_conditions: Optional[List[str]] = None) -> bool:
        """Run a single pipeline stage with resumability.
        
        Returns:
            True if stage completed successfully, False otherwise
        """
        # Check skip conditions
        if skip_conditions:
            for condition_file in skip_conditions:
                if not Path(condition_file).exists():
                    logging.info("Skipping stage '%s': condition file missing: %s", 
                                stage_name, condition_file)
                    self.state.stages[stage_name] = StageState(
                        name=stage_name,
                        status='skipped',
                        start_time=datetime.now().isoformat(),
                        end_time=datetime.now().isoformat()
                    )
                    self._save_state()
                    return True
        
        # Check if already completed
        if self._get_stage_status(stage_name) == 'completed' and not self.force:
            logging.info("Stage '%s' already completed, skipping", stage_name)
            return True
        
        # Mark as running
        self.state.stages[stage_name] = StageState(
            name=stage_name,
            status='running',
            start_time=datetime.now().isoformat()
        )
        self._save_state()
        
        # Run the command
        logging.info("=" * 60)
        logging.info("Running stage: %s", stage_name)
        logging.info("Description: %s", description)
        logging.info("=" * 60)
        
        try:
            result = subprocess.run(command, check=True, capture_output=False)
            # Mark as completed
            self.state.stages[stage_name] = StageState(
                name=stage_name,
                status='completed',
                start_time=self.state.stages[stage_name].start_time,
                end_time=datetime.now().isoformat()
            )
            self._save_state()
            logging.info("Stage '%s' completed successfully", stage_name)
            return True
            
        except subprocess.CalledProcessError as e:
            # Mark as failed
            self.state.stages[stage_name] = StageState(
                name=stage_name,
                status='failed',
                error=str(e),
                start_time=self.state.stages[stage_name].start_time,
                end_time=datetime.now().isoformat()
            )
            self._save_state()
            logging.error("Stage '%s' failed: %s", stage_name, e)
            return False
    
    def run_pipeline(self, stages: List[Tuple[str, List[str], str, Optional[List[str]]]], 
                     start_from: Optional[str] = None):
        """Run the complete pipeline or resume from a specific stage.
        
        Args:
            stages: List of (stage_name, command, description, skip_conditions)
            start_from: Stage name to resume from (None = start from beginning)
        """
        found_start = start_from is None
        
        for stage_name, command, description, skip_conditions in stages:
            # Skip until we reach the starting stage
            if not found_start:
                if stage_name == start_from:
                    found_start = True
                else:
                    logging.info("Skipping stage '%s' (before start point)", stage_name)
                    continue
            
            # Run the stage
            success = self._run_stage(stage_name, command, description, skip_conditions)
            
            if not success:
                logging.error("Pipeline stopped at stage '%s'", stage_name)
                logging.error("To resume, run: python3 scripts/pipeline_manager.py --stage %s", stage_name)
                sys.exit(1)
        
        logging.info("=" * 60)
        logging.info("Pipeline completed successfully!")
        logging.info("=" * 60)
    
    def show_status(self):
        """Display current pipeline status."""
        if not self.state.stages:
            print("No pipeline stages executed yet.")
            return
        
        print("\n" + "=" * 60)
        print("Pipeline Status")
        print("=" * 60)
        print(f"Last update: {self.state.last_update}\n")
        
        for stage_name, stage_state in self.state.stages.items():
            status_symbol = {
                'pending': '⏳',
                'running': '🔄',
                'completed': '✅',
                'failed': '❌',
                'skipped': '⏭️'
            }.get(stage_state.status, '❓')
            
            print(f"{status_symbol} {stage_name}: {stage_state.status}")
            if stage_state.start_time:
                print(f"   Started: {stage_state.start_time}")
            if stage_state.end_time:
                print(f"   Ended: {stage_state.end_time}")
            if stage_state.error:
                print(f"   Error: {stage_state.error}")
            print()


def main(argv):
    ap = argparse.ArgumentParser(
        description="Pipeline Manager for Ido-Esperanto Extractor"
    )
    ap.add_argument("--state-file", type=Path, 
                   default=Path(__file__).resolve().parents[1] / "work" / "pipeline_state.json",
                   help="Path to pipeline state file")
    ap.add_argument("--force", action="store_true",
                   help="Force regeneration of all stages (ignore completed)")
    ap.add_argument("--stage", type=str,
                   help="Resume from specific stage")
    ap.add_argument("--status", action="store_true",
                   help="Show pipeline status only")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    
    args = ap.parse_args(argv)
    configure_logging(args.verbose)
    
    manager = PipelineManager(args.state_file, force=args.force)
    
    if args.status:
        manager.show_status()
        return 0
    
    # Define pipeline stages
    stages = [
        # Stage 1: Download dumps
        ("download_dumps", 
         ["./scripts/download_dumps.sh"],
         "Download Wikimedia dumps",
         None),
        
        # Stage 2: Ido Wiktionary
        ("wiktionary_io",
         ["python3", "scripts/process_wiktionary_two_stage.py", "--source", "io", "--target", "eo"],
         "Process Ido Wiktionary (two-stage)",
         None),
        
        # Stage 3: Esperanto Wiktionary
        ("wiktionary_eo",
         ["python3", "scripts/process_wiktionary_two_stage.py", "--source", "eo", "--target", "io"],
         "Process Esperanto Wiktionary (two-stage)",
         None),
        
        # Stage 4: Copy files for alignment (handled by Python to avoid bash dependency)
        ("copy_for_alignment",
         ["python3", "-c", "import shutil; shutil.copy('work/io_wiktionary_processed.json', 'work/io_wikt_io_eo.json'); shutil.copy('work/eo_wiktionary_processed.json', 'work/eo_wikt_eo_io.json')"],
         "Copy processed files for alignment",
         ["work/io_wiktionary_processed.json", "work/eo_wiktionary_processed.json"]),
        
        # Stage 5: French Wiktionary
        ("wiktionary_fr",
         ["python3", "scripts/parse_wiktionary_fr.py"],
         "Parse French Wiktionary",
         None),
        
        # Stage 6: Wikipedia processing
        ("wikipedia",
         ["python3", "scripts/process_wikipedia_two_stage.py"],
         "Process Wikipedia dump (two-stage)",
         None),
        
        # Stage 7: Wikipedia frequency
        ("wikipedia_frequency",
         ["python3", "scripts/build_frequency_io_wiki.py"],
         "Build Wikipedia frequency data",
         None),
        
        # Stage 8: English Wiktionary (both IO and EO in one pass)
        ("wiktionary_en",
         ["python3", "scripts/parse_wiktionary_en.py", 
          "--input", "data/raw/enwiktionary-latest-pages-articles.xml.bz2",
          "--out", "work/en_wikt_en_both.json",
          "--target", "both",
          "--progress-every", "10000", "-v"],
         "Parse English Wiktionary (IO + EO)",
         None),
        
        # Stage 9: Via English
        ("via_english",
         ["python3", "scripts/parse_wiktionary_via.py",
          "--source", "en",
          "--io-input", "work/en_wikt_en_both.json",
          "--eo-input", "work/en_wikt_en_both.json",
          "--out", "work/bilingual_via_en.json",
          "--progress-every", "1000"],
         "Extract via English translations",
         ["work/en_wikt_en_both.json"]),
        
        # Stage 10: Align bilingual
        ("align_bilingual",
         ["python3", "scripts/align_bilingual.py"],
         "Align bilingual entries",
         None),
        
        # Stage 11: Via French
        ("via_french",
         ["python3", "scripts/parse_wiktionary_via.py",
          "--source", "fr",
          "--progress-every", "1000"],
         "Extract via French translations",
         None),
        
        # Stage 12: Normalize
        ("normalize",
         ["python3", "scripts/normalize_entries.py"],
         "Normalize entries",
         None),
        
        # Stage 13: Infer morphology
        ("infer_morphology",
         ["python3", "scripts/infer_morphology.py"],
         "Infer morphology",
         None),
        
        # Stage 14: Filter and validate
        ("filter",
         ["python3", "scripts/filter_and_validate.py", "--wiki-top-n", "1000"],
         "Filter and validate entries",
         None),
        
        # Stage 15: Final preparation
        ("final_preparation",
         ["python3", "scripts/final_preparation.py"],
         "Final preparation",
         None),
        
        # Stage 16: Build monolingual
        ("build_monolingual",
         ["python3", "scripts/build_monolingual.py"],
         "Build monolingual dictionaries",
         None),
        
        # Stage 17: Build big bidix
        ("build_big_bidix",
         ["python3", "scripts/build_one_big_bidix_json.py"],
         "Build one big bilingual dictionary",
         None),
        
        # Stage 18: Report coverage
        ("report_coverage",
         ["python3", "scripts/report_coverage.py", "--top", "5000"],
         "Report coverage statistics",
         None),
        
        # Stage 19: Export Apertium
        ("export_apertium",
         ["python3", "scripts/export_apertium.py"],
         "Export to Apertium XML",
         None),
        
        # Stage 20: Report stats
        ("report_stats",
         ["python3", "scripts/report_stats.py"],
         "Report general statistics",
         None),
        
        # Stage 21: Report dump coverage
        ("report_dump_coverage",
         ["python3", "scripts/report_io_dump_coverage.py"],
         "Report dump coverage",
         None),
        
        # Stage 22: Report conflicts
        ("report_conflicts",
         ["python3", "scripts/report_conflicts.py"],
         "Report conflicts",
         None),
        
        # Stage 23: Report big bidix stats
        ("report_big_bidix_stats",
         ["python3", "scripts/report_big_bidix_stats.py"],
         "Report big bidix statistics",
         None),
        
        # Stage 24: Build web index
        ("build_web_index",
         ["python3", "scripts/build_web_index.py"],
         "Build web index",
         None),
    ]
    
    manager.run_pipeline(stages, start_from=args.stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

