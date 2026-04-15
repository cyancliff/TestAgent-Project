# CFI-V2 Data Layout

Recommended directory layout:

```text
multimodal_personality/data/cfi_v2/
  train/
    videos/
    annotation.pkl
    transcription.pkl
  val/
    videos/
    annotation.pkl
    transcription.pkl
  test/
    videos/
    annotation.pkl
    transcription.pkl
  manifests/
```

Notes:

1. `annotation.pkl` is expected to be a pickled dictionary-of-dictionaries.
2. `transcription.pkl` is expected to be a pickled dictionary mapping video name to transcript.
3. Video files are expected to use the same base names as the annotation keys.
4. The manifest generator will normalize trait names into:
   `extraversion`, `agreeableness`, `conscientiousness`, `neuroticism`, `openness`.

Practical mapping from the downloaded website structure:

1. `Training` -> `multimodal_personality/data/cfi_v2/train/`
2. `Validation` -> `multimodal_personality/data/cfi_v2/val/`
3. `Test` -> `multimodal_personality/data/cfi_v2/test/`

Required filenames inside each phase:

1. videos go into `videos/`
2. annotation file must be named `annotation.pkl`
3. transcription file must be named `transcription.pkl`
