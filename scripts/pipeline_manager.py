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
import hashlib
import json
import logging
import re
import sys
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from _common import configure_logging

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_DIR = _SCRIPTS_DIR.parent
_IMPORT_RE = re.compile(r'^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))', re.MULTILINE)
# Scripts invoked as subprocesses are named as string literals (e.g. the two-stage
# wrapper references "parse_wiktionary_stage1.py"); follow those too so the chain
# reaches their imports (wiktionary_parser.py, …).
_PYFILE_RE = re.compile(r'["\']([\w./-]+\.py)["\']')


def _resolve_local_module(mod: str) -> Optional[Path]:
    """Map a dotted module name to a file under scripts/, or None if not local."""
    rel = mod.replace('.', '/')
    for cand in (_SCRIPTS_DIR / f'{rel}.py', _SCRIPTS_DIR / rel / '__init__.py'):
        if cand.exists():
            return cand
    return None


def _collect_code_files(command: List[str]) -> List[Path]:
    """The scripts named in a command plus their transitive local imports.

    Lets a stage's fingerprint capture changes to helper modules it imports
    (e.g. editing wiktionary_parser.py invalidates every parse stage that
    imports it), not just the directly-invoked script.
    """
    seen: set = set()
    out: List[Path] = []
    stack = [(_REPO_DIR / a) for a in command if a.endswith('.py')]
    while stack:
        f = stack.pop()
        f = f if f.exists() else _SCRIPTS_DIR / Path(f).name
        if not f.exists() or f in seen:
            continue
        seen.add(f)
        out.append(f)
        try:
            text = f.read_text(encoding='utf-8')
        except OSError:
            continue
        for m in _IMPORT_RE.finditer(text):
            dep = _resolve_local_module(m.group(1) or m.group(2))
            if dep and dep not in seen:
                stack.append(dep)
        for m in _PYFILE_RE.finditer(text):
            cand = _SCRIPTS_DIR / Path(m.group(1)).name
            if cand.exists() and cand not in seen:
                stack.append(cand)
    return sorted(out)


def stage_fingerprint(command: List[str]) -> str:
    """Short content hash of a stage's code (scripts + transitive local imports).

    For inline (`-c`) or shell commands with no .py file, the command text
    itself is hashed so edits to inline logic still invalidate the stage.
    """
    files = _collect_code_files(command)
    h = hashlib.sha256()
    if not files:
        h.update(repr(command).encode())
    for f in files:
        h.update(f.name.encode())
        h.update(b'\0')
        h.update(f.read_bytes())
        h.update(b'\0')
    return h.hexdigest()[:16]


@dataclass
class StageState:
    """State for a single pipeline stage."""
    name: str
    status: str  # pending, running, completed, failed, skipped
    output: Optional[str] = None
    error: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    code_fingerprint: Optional[str] = None  # hash of stage code at completion
    
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
                   description: str, skip_conditions: Optional[List[str]] = None,
                   force_rerun: bool = False) -> Tuple[bool, bool]:
        """Run a single pipeline stage with resumability.

        Args:
            force_rerun: re-run even if completed/unchanged (an upstream stage re-ran).

        Returns:
            (success, ran) — `ran` is False when the stage was skipped.
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
                    return True, False

        current_fp = stage_fingerprint(command)

        # Check if already completed — content-aware: a stage stays skipped only
        # if its code fingerprint is unchanged and no upstream stage re-ran.
        stored = self.state.stages.get(stage_name)
        if stored and stored.status == 'completed' and not self.force and not force_rerun:
            if stored.code_fingerprint is not None and stored.code_fingerprint == current_fp:
                logging.info("Stage '%s' already completed, skipping", stage_name)
                return True, False
            if stored.code_fingerprint is None:
                # Missing/legacy fingerprint (e.g. state predates the
                # fingerprinting feature, or was written by an older version):
                # treat as STALE, not trusted. We cannot know whether the code
                # changed since this state was recorded, so re-run to be safe
                # and establish a verified baseline fingerprint.
                logging.info("Stage '%s' has no recorded code fingerprint (legacy state) — "
                             "treating as stale and re-running", stage_name)
            else:
                logging.info("Stage '%s' code changed (%s → %s) — re-running",
                             stage_name, stored.code_fingerprint, current_fp)

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
                end_time=datetime.now().isoformat(),
                code_fingerprint=current_fp
            )
            self._save_state()
            logging.info("Stage '%s' completed successfully", stage_name)
            return True, True

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
            return False, True
    
    def run_pipeline(self, stages: List[Tuple[str, List[str], str, Optional[List[str]]]], 
                     start_from: Optional[str] = None):
        """Run the complete pipeline or resume from a specific stage.
        
        Args:
            stages: List of (stage_name, command, description, skip_conditions)
            start_from: Stage name to resume from (None = start from beginning)
        """
        found_start = start_from is None
        # Once any stage re-runs, its outputs change, so every downstream stage
        # must re-run too — even if its own code is unchanged.
        invalidate_rest = False

        for stage_name, command, description, skip_conditions in stages:
            # Skip until we reach the starting stage
            if not found_start:
                if stage_name == start_from:
                    found_start = True
                else:
                    logging.info("Skipping stage '%s' (before start point)", stage_name)
                    continue

            # Run the stage
            success, ran = self._run_stage(stage_name, command, description,
                                           skip_conditions, force_rerun=invalidate_rest)
            if ran:
                invalidate_rest = True

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
         ["python3", "scripts/process_wiktionary_two_stage.py", "--source", "io", "--target", "eo", "--force"],
         "Process Ido Wiktionary (two-stage)",
         None),
        
        # Stage 3: Esperanto Wiktionary
        ("wiktionary_eo",
         ["python3", "scripts/process_wiktionary_two_stage.py", "--source", "eo", "--target", "io", "--force"],
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

        # Stage 11b: Wikipedia interlanguage links (io_title <-> eo_title pairs).
        # Fast (<1 min): joins iowiki XML page table with langlinks SQL dump,
        # filters to vocabulary-shaped pairs. Adds ~14k entries to bidix that
        # have Wikipedia articles in both languages but no Wiktionary entry.
        ("wikipedia_langlinks",
         ["python3", "scripts/parse_wikipedia_langlinks.py"],
         "Extract io↔eo pairs from Wikipedia interlanguage links",
         None),

        # Stage 11c: Wikidata labels (io+eo labeled items → io↔eo pairs).
        # Parses iowiki-latest-page_props.sql.gz (local dump) to get QIDs for
        # all io.wiki pages, then batch-fetches labels+aliases via the Wikidata
        # wbgetentities API (50 QIDs/call, ~23 min for ~70k items). No SPARQL.
        # Requires: data/raw/iowiki-latest-page_props.sql.gz (from download_dumps.sh)
        ("wikidata_labels",
         ["python3", "scripts/parse_wikidata_labels.py", "-v"],
         "Extract io↔eo pairs from Wikidata labels",
         None),

        # Stage 11d: eo.wiki langlinks (eo_title → io_title, eo-perspective).
        # Mirrors stage 11b but from eo.wiki's side. eo.wiki has ~625k pages
        # vs io.wiki's ~70k, but the io↔eo article intersection is fixed so
        # overlap with stage 11b is high (~98%). Adds ~300 novel pairs not
        # captured by the io-side pass.
        # Requires: data/raw/eowiki-latest-langlinks.sql.gz (129 MB)
        #           data/raw/eowiki-latest-page.sql.gz (28 MB)
        ("eowiki_langlinks",
         ["python3", "scripts/parse_wikipedia_langlinks.py", "--source-wiki", "eo"],
         "Extract io↔eo pairs from eo.wiki interlanguage links",
         None),

        # Stage 11e: Morphological expansion (derive forms from known bidix pairs).
        # Generates forms like facado→farado from known facar→fari, validated
        # against the io.wiki frequency corpus. Fast (~3s). Runs after bidix
        # sources are collected but before build_big_bidix.
        # Requires: dist/bidix_big.json, work/io_wiki_frequency.json
        ("morphological_expansion",
         ["python3", "scripts/build_morphological_expansion.py"],
         "Generate morphological derivations from known bidix pairs",
         None),

        # Stage 11f: Closed-class structured tables (roadmap #2).
        # Extracts the pronoun comparison table ("Komparo inter Ido ed
        # Esperanto") and the correlative grid ("Gramatiko di Ido") from the
        # io.wikipedia dump; the EO side of the grid is generated by rule from
        # grid position. Rank-0 source for its small lemma set — fixes
        # correlative conflict winners (omna→ĉiu) and retires curated seeds.
        # Fast (~1 min, early-exit dump scan).
        ("closed_class_tables",
         ["python3", "scripts/parse_closed_class.py", "-v"],
         "Extract closed-class pairs from structured wiki tables",
         None),

        # Stage 12: Prepare vocabulary (normalize + morphology + filter in one pass)
        ("prepare_vocabulary",
         ["python3", "scripts/prepare_vocabulary.py", "--wiki-top-n", "1000"],
         "Prepare vocabulary (normalize + morphology + filter)",
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

        # Stage 25: Export vortaro dictionary
        ("export_vortaro",
         ["python3", "scripts/export_vortaro.py"],
         "Export vortaro dictionary (dist/vortaro_dictionary.json)",
         None),
    ]

    manager.run_pipeline(stages, start_from=args.stage)
    logging.info("")
    logging.info("To deploy generated files to consumer repos, run:")
    logging.info("    cd .. && ./deploy.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

