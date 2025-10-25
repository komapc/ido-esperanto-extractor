# Pipeline Manager

## Overview

The Pipeline Manager provides stage-based resumability for the Ido-Esperanto extractor pipeline. It tracks the completion status of each stage, allows resuming from failures, and provides visual progress tracking.

## Features

- **Resumability**: Resume from any stage after interruption
- **State Tracking**: Tracks completion status, errors, and timestamps
- **Error Handling**: Stops on failure and shows how to resume
- **Progress Visualization**: Status command shows pipeline progress
- **Force Regeneration**: Option to regenerate all stages regardless of completion

## Usage

### Basic Usage

Run the complete pipeline:
```bash
make all              # Uses pipeline manager by default
# or
make regenerate-managed
```

### Show Status

Check current pipeline status:
```bash
make pipeline-status
# or
python3 scripts/pipeline_manager.py --status
```

### Resume from Failure

If a stage fails, you can resume from that stage:
```bash
make STAGE=wiktionary_en_io
# or
python3 scripts/pipeline_manager.py --stage wiktionary_en_io
```

### Force Regeneration

Force regeneration of all stages (ignore completed):
```bash
make FORCE=1
# or
python3 scripts/pipeline_manager.py --force
```

### Combine Options

Resume from a specific stage with force flag:
```bash
make FORCE=1 STAGE=normalize
# or
python3 scripts/pipeline_manager.py --force --stage normalize
```

## Pipeline Stages

The pipeline consists of 25 stages:

1. **download_dumps** - Download Wikimedia dumps
2. **wiktionary_io** - Process Ido Wiktionary (two-stage)
3. **wiktionary_eo** - Process Esperanto Wiktionary (two-stage)
4. **copy_for_alignment** - Copy processed files for alignment
5. **wiktionary_fr** - Parse French Wiktionary
6. **wikipedia** - Process Wikipedia dump (two-stage)
7. **wikipedia_frequency** - Build Wikipedia frequency data
8. **wiktionary_en_io** - Parse English Wiktionary (IO)
9. **wiktionary_en_eo** - Parse English Wiktionary (EO)
10. **via_english** - Extract via English translations
11. **align_bilingual** - Align bilingual entries
12. **via_french** - Extract via French translations
13. **normalize** - Normalize entries
14. **infer_morphology** - Infer morphology
15. **filter** - Filter and validate entries
16. **final_preparation** - Final preparation
17. **build_monolingual** - Build monolingual dictionaries
18. **build_big_bidix** - Build one big bilingual dictionary
19. **report_coverage** - Report coverage statistics
20. **export_apertium** - Export to Apertium XML
21. **report_stats** - Report general statistics
22. **report_dump_coverage** - Report dump coverage
23. **report_conflicts** - Report conflicts
24. **report_big_bidix_stats** - Report big bidix statistics
25. **build_web_index** - Build web index

## State File

The pipeline state is stored in `work/pipeline_state.json`:

```json
{
  "stages": {
    "wiktionary_io": {
      "name": "wiktionary_io",
      "status": "completed",
      "output": null,
      "error": null,
      "start_time": "2025-10-25T10:00:00",
      "end_time": "2025-10-25T10:05:00"
    }
  },
  "last_update": "2025-10-25T10:05:00"
}
```

### Stage Statuses

- **pending** - Not yet executed
- **running** - Currently executing
- **completed** - Successfully completed
- **failed** - Failed with error
- **skipped** - Skipped due to missing prerequisites

## Error Handling

When a stage fails:
1. The pipeline stops immediately
2. The failed stage is marked with error details
3. State is saved to `work/pipeline_state.json`
4. Instructions are shown for resuming

Example error message:
```
Stage 'wiktionary_en_io' failed: Command failed
Pipeline stopped at stage 'wiktionary_en_io'
To resume, run: python3 scripts/pipeline_manager.py --stage wiktionary_en_io
```

## Migration from Legacy Pipeline

The legacy `make regenerate` command still works but doesn't use the pipeline manager. New code should use `make all` or `make regenerate-managed`.

### Comparison

| Feature | Legacy `regenerate` | New `regenerate-managed` |
|---------|-------------------|-------------------------|
| Resumability | No | Yes |
| Error recovery | No | Yes |
| Progress tracking | No | Yes |
| State persistence | No | Yes |
| Skip completed | No | Yes |

## Integration with Skip Flags

The pipeline manager doesn't directly support the old skip flags (`SKIP_DOWNLOAD`, `SKIP_EN_WIKT`, etc.). If you need to skip stages, you can:

1. Use the legacy `make regenerate mode` with skip flags
2. Manually delete the completed stage from `work/pipeline_state.json`
3. Add conditional stage execution to the pipeline manager

## Examples

### Full Pipeline Run
```bash
make all
```

### Resume After Failure
```bash
# Check status
make pipeline-status

# Resume from failed stage
make STAGE=wiktionary_en_io
```

### Force Regeneration
```bash
make FORCE=1
```

### Run Specific Stages Only
```bash
# Run from stage X to stage Y
make STAGE=normalize           # Runs normalize and all subsequent stages
```

## Troubleshooting

### State File Corrupted
If the state file becomes corrupted:
```bash
rm work/pipeline_state.json
make all  # Start fresh
```

### Stage Shows "Completed" But Needs Re-running
```bash
make FORCE=1  # Regenerate all stages
# or
make STAGE=<stage_name> FORCE=1  # Regenerate specific stage
```

### Want to Skip Certain Stages
Use the legacy pipeline with skip flags:
```bash
make regenerate SKIP_EN_WIKT=1 SKIP_FR_WIKT=1
```

## Future Enhancements

Potential improvements:
- Parallel stage execution where possible
- Graph-based dependency resolution
- Better error reporting and recovery suggestions
- Web UI for monitoring pipeline progress
- Metrics and timing statistics per stage

