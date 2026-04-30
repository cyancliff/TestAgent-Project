import json

from app.services.multimodal_evidence import (
    build_consistency_summary,
    build_modality_quality_summary,
    build_prediction_confidence_summary,
)


def test_modality_quality_summary_reads_artifacts(tmp_path):
    clip_path = tmp_path / "clip.json"
    wav_path = tmp_path / "wav.json"
    bg_path = tmp_path / "bg.json"
    transcript_path = tmp_path / "transcript.txt"
    clip_path.write_text(
        json.dumps(
            {
                "image_features": [[0.1] * 768 for _ in range(15)],
                "text_sequence_features": [[0.2] * 768 for _ in range(5)],
            }
        ),
        encoding="utf-8",
    )
    wav_path.write_text(json.dumps({"wav2clip_features": [[0.3] * 512 for _ in range(15)]}), encoding="utf-8")
    bg_path.write_text(json.dumps({"success": True, "bg_features": [0.1] * 256}), encoding="utf-8")
    transcript_path.write_text("hello world. this is a useful transcript.", encoding="utf-8")

    summary = build_modality_quality_summary(
        {
            "clip_feature_path": str(clip_path),
            "wav2clip_feature_path": str(wav_path),
            "bg_feature_path": str(bg_path),
            "transcript_path": str(transcript_path),
        }
    )

    assert summary["overall_quality"] > 0.5
    assert summary["modalities"]["visual"] == 1.0
    assert summary["signals"]["has_bg_features"] is True


def test_prediction_confidence_uses_quality_and_real_result():
    scores = {"openness": 0.7, "conscientiousness": 0.6}
    high = build_prediction_confidence_summary(
        scores=scores,
        quality_summary={"overall_quality": 0.9},
        is_real_result=True,
    )
    low = build_prediction_confidence_summary(
        scores=scores,
        quality_summary={"overall_quality": 0.9},
        is_real_result=False,
        used_fallback=True,
    )

    assert high["overall_confidence"] > low["overall_confidence"]


def test_consistency_summary_maps_atmr_to_big_five():
    summary = build_consistency_summary(
        big_five_scores={"openness": 0.8, "agreeableness": 0.75, "conscientiousness": 0.7, "extraversion": 0.6, "neuroticism": 0.2},
        atmr_summary={
            "A": {"normalized": 0.78},
            "T": {"normalized": 0.65},
            "M": {"normalized": 0.72},
            "R": {"normalized": 0.7},
        },
    )

    assert summary["overall_score"] > 0.7
    assert summary["items"][0]["status"] == "互相支持"
