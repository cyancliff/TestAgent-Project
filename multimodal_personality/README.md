# Multimodal Personality Module

## Purpose

This directory contains the standalone reproduction workspace for the paper-based
multimodal personality prediction pipeline.

The module is intentionally separated from the main ATMR questionnaire flow.
Its first goal is offline reproducibility:

1. preprocess a video input
2. extract multimodal features
3. load a trained checkpoint
4. predict Big Five personality scores

## Planned structure

```text
multimodal_personality/
  configs/
  data/
  checkpoints/
  preprocessing/
  feature_extractors/
  models/
  inference/
  evaluation/
```

## Dataset bootstrap

For the CFI-V2 dataset, use the example config:

`multimodal_personality/configs/cfi_v2.example.yaml`

After placing the dataset files, generate normalized manifests with:

```powershell
python scripts/build_cfi_v2_manifest.py --config multimodal_personality/configs/cfi_v2.example.yaml --phase all
```

This step will:

1. load pickled labels and transcripts
2. align them with the available video files
3. output `train_manifest.json`, `val_manifest.json`, and `test_manifest.json`

The generated manifests will become the stable input for later feature extraction and model training.

## Feature extraction bootstrap

After preprocessing produces frame artifacts, build feature jobs with:

```powershell
python scripts/build_clip_feature_jobs.py --manifest multimodal_personality/data/cfi_v2/manifests/train_manifest.json
```

Then run CLIP extraction with:

```powershell
python scripts/extract_clip_features.py --jobs multimodal_personality/data/cfi_v2/feature_jobs.json --device cpu
```

If CLIP dependencies are missing, the extractor will emit per-sample JSON files with explicit errors instead of failing silently.

## Current status

Current repository state only provides the scaffold and integration points.
The actual training and inference implementation will be added incrementally.

## Integration contract

The FastAPI application will call this module through a stable service boundary.
Target service input:

1. local video file path
2. optional session or user metadata

Target service output:

1. Big Five scores
2. model version
3. task status
4. optional artifact paths
