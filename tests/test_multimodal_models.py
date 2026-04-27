from __future__ import annotations

import torch

from multimodal_personality.feature_extractors.bg_extractor import BackgroundFeatureExtractor
from multimodal_personality.models import AGTNMTLModel, MultimodalFeatureBundle
from multimodal_personality.models.feature_bundle import BG_DIM


def test_feature_bundle_accepts_current_single_transcript_embedding() -> None:
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
        "text_features": [0.2] * 768,
    }

    bundle = MultimodalFeatureBundle.from_current_artifacts(sample=sample, clip_payload=clip_payload)
    tensors = bundle.to_tensors(text_seq_len=13)

    assert tensors["labels"].shape == (5,)
    assert tensors["clip_video"].shape == (15, 768)
    assert tensors["clip_text"].shape == (13, 768)
    assert tensors["wav2clip"].shape == (15, 512)
    assert tensors["bg_features"].shape == (256,)
    assert torch.count_nonzero(tensors["wav2clip"]) == 0
    assert torch.count_nonzero(tensors["bg_features"]) == 0


def test_background_feature_extractor_builds_nonzero_descriptor() -> None:
    clip_payload = {
        "success": True,
        "image_features": [[0.1 + frame_index * 0.01] * 768 for frame_index in range(15)],
        "text_sequence_features": [[0.2 + sentence_index * 0.01] * 768 for sentence_index in range(3)],
    }
    wav_payload = {
        "success": True,
        "wav2clip_features": [[0.3 + frame_index * 0.01] * 512 for frame_index in range(15)],
    }

    features = BackgroundFeatureExtractor().build_features(
        clip_payload=clip_payload,
        wav2clip_payload=wav_payload,
        transcript="A short test transcript. It describes a calm indoor background.",
    )

    assert len(features) == BG_DIM
    assert any(value != 0.0 for value in features)


def test_feature_bundle_accepts_derived_background_payload() -> None:
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
        "text_sequence_features": [[0.2] * 768 for _ in range(4)],
    }
    bg_payload = {
        "success": True,
        "bg_features": BackgroundFeatureExtractor().build_features(
            clip_payload=clip_payload,
            transcript="A speaker talks in front of a simple room background.",
        ),
    }

    bundle = MultimodalFeatureBundle.from_current_artifacts(
        sample=sample,
        clip_payload=clip_payload,
        bg_payload=bg_payload,
    )
    tensors = bundle.to_tensors(text_seq_len=13)

    assert tensors["bg_features"].shape == (BG_DIM,)
    assert torch.count_nonzero(tensors["bg_features"]) > 0


def test_agtn_mtl_model_forward_shapes() -> None:
    model = AGTNMTLModel(text_seq_len=13)
    outputs = model(
        clip_video=torch.rand(2, 15, 768),
        wav2clip=torch.rand(2, 15, 512),
        clip_text=torch.rand(2, 13, 768),
        bg=torch.rand(2, 256),
    )

    assert outputs["m"].shape == (2, 5)
    assert outputs["clip_clip"].shape == (2, 5)
    assert outputs["clip_wav"].shape == (2, 5)
    assert outputs["clip_t"].shape == (2, 5)
    assert outputs["Feature_m"].shape == (2, 128)
