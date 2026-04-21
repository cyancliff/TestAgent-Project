from __future__ import annotations

import torch

from multimodal_personality.models import AGTNMTLModel, MultimodalFeatureBundle


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
