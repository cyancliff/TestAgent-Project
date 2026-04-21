from __future__ import annotations

import json

import numpy as np

from multimodal_personality.feature_extractors.clip_extractor import ClipFeatureExtractor
from multimodal_personality.feature_extractors.wav2clip_extractor import Wav2ClipFeatureExtractor
from multimodal_personality.models import MultimodalFeatureBundle


def test_clip_feature_extractor_writes_sentence_level_text_features(tmp_path, monkeypatch) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for index in range(2):
        (frames_dir / f"frame_{index:03d}.jpg").write_bytes(b"frame")

    extractor = ClipFeatureExtractor(max_sentences=4)
    monkeypatch.setattr(
        extractor,
        "availability",
        lambda: {"transformers": True, "torch": True, "pil": True},
    )
    monkeypatch.setattr(extractor, "_encode_images", lambda frame_paths: [[0.1] * 768 for _ in frame_paths])
    monkeypatch.setattr(extractor, "_encode_texts", lambda texts: [[float(i + 1)] * 768 for i, _ in enumerate(texts)])

    result = extractor.extract_sample(
        sample={
            "video_name": "demo.mp4",
            "transcript": "First sentence. Second sentence!\nThird sentence?",
        },
        frames_dir=frames_dir,
        output_dir=tmp_path / "clip_out",
    )

    payload = json.loads((tmp_path / "clip_out" / "demo.mp4.json").read_text(encoding="utf-8"))
    assert result.success is True
    assert payload["text_sentences"] == ["First sentence.", "Second sentence!", "Third sentence?"]
    assert payload["text_sequence_count"] == 3
    assert len(payload["text_sequence_features"]) == 3
    assert len(payload["text_sequence_features"][0]) == 768
    assert len(payload["text_features"]) == 768


def test_wav2clip_feature_extractor_pads_to_target_segment_count(tmp_path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio")

    extractor = Wav2ClipFeatureExtractor(segment_count=15, feature_dim=512)
    monkeypatch.setattr(
        extractor,
        "availability",
        lambda: {"wav2clip": True, "librosa": True, "numpy": True},
    )
    monkeypatch.setattr(extractor, "_load_audio", lambda _: (np.arange(160, dtype=np.float32), 16000))
    monkeypatch.setattr(extractor, "_embed_audio", lambda _: np.ones((1, 512, 14), dtype=np.float32))

    result = extractor.extract_sample(
        video_name="demo.mp4",
        audio_path=audio_path,
        output_dir=tmp_path / "wav_out",
    )

    payload = json.loads((tmp_path / "wav_out" / "demo.mp4.json").read_text(encoding="utf-8"))
    assert result.success is True
    assert payload["segment_count"] == 15
    assert payload["original_segment_count"] == 14
    assert len(payload["wav2clip_features"]) == 15
    assert len(payload["wav2clip_features"][0]) == 512
    assert payload["wav2clip_features"][-1] == [0.0] * 512


def test_feature_bundle_prefers_sentence_level_text_features() -> None:
    sample = {
        "video_name": "demo.mp4",
        "video_path": "demo.mp4",
        "labels": {
            "openness": 0.1,
            "conscientiousness": 0.2,
            "extraversion": 0.3,
            "agreeableness": 0.4,
            "neuroticism": 0.5,
        },
    }
    clip_payload = {
        "success": True,
        "image_features": [[0.1] * 768 for _ in range(15)],
        "text_features": [0.9] * 768,
        "text_sequence_features": [[0.2] * 768, [0.3] * 768],
    }

    bundle = MultimodalFeatureBundle.from_current_artifacts(sample=sample, clip_payload=clip_payload)

    assert len(bundle.clip_text) == 2
    assert bundle.clip_text[0][0] == 0.2
    assert bundle.clip_text[1][0] == 0.3
