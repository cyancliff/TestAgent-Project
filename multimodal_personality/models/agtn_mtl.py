"""AGTN-MTL multimodal personality regression model."""

from __future__ import annotations

import torch
import torch.nn as nn

from multimodal_personality.models.feature_bundle import MICRO_EXPRESSION_DIM
from multimodal_personality.models.agtn_layers import (
    GraphConvBlock,
    PositionalEncoding,
    ResidualChannelAttention,
    SequenceEncoder,
    TemporalAttention,
    cosine_feature_fusion,
)


class AGTNMTLModel(nn.Module):
    """Reference-style multimodal model adapted to this repository."""

    def __init__(
        self,
        hidden_dim: int = 128,
        attention_heads: int = 1,
        graph_metric: str = "ones",
        dropout: float = 0.2,
        text_seq_len: int = 13,
        frame_count: int = 15,
        clip_video_dim: int = 768,
        wav2clip_dim: int = 512,
        clip_text_dim: int = 768,
        bg_dim: int = 256,
        use_micro_expression_features: bool = False,
        micro_expression_dim: int = MICRO_EXPRESSION_DIM,
        output_dim: int = 5,
    ) -> None:
        super().__init__()
        activation = nn.ReLU()
        text_feature_dim = 128
        self.use_micro_expression_features = use_micro_expression_features
        self.micro_expression_dim = micro_expression_dim

        self.text_encoder = SequenceEncoder(
            input_size=clip_text_dim,
            hidden_size=64,
            num_layers=2,
            dropout=dropout,
        )
        self.text_attention = TemporalAttention(in_dim=text_feature_dim, max_seq_len=text_seq_len)

        self.bg_projection = nn.Sequential(nn.Dropout(dropout), nn.Linear(bg_dim, hidden_dim), activation)

        self.video_position = PositionalEncoding(clip_video_dim, frame_count)
        self.video_graph = nn.Sequential(
            GraphConvBlock(clip_video_dim, neighbor_num=3, metric=graph_metric),
            GraphConvBlock(clip_video_dim, neighbor_num=3, metric=graph_metric),
        )
        self.video_projection = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(clip_video_dim, hidden_dim),
            activation,
        )

        self.audio_position = PositionalEncoding(wav2clip_dim, frame_count)
        self.audio_graph = nn.Sequential(
            GraphConvBlock(wav2clip_dim, neighbor_num=3, metric=graph_metric),
            GraphConvBlock(wav2clip_dim, neighbor_num=3, metric=graph_metric),
        )
        self.audio_projection = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(wav2clip_dim, hidden_dim),
            activation,
        )

        self.micro_projection = None
        if self.use_micro_expression_features:
            self.micro_projection = nn.Sequential(
                nn.Dropout(dropout),
                nn.Linear(micro_expression_dim, hidden_dim),
                activation,
            )

        self.temporal_pool = nn.AdaptiveMaxPool1d(1)
        fused_dim = hidden_dim * 2 + text_feature_dim
        if self.use_micro_expression_features:
            fused_dim += hidden_dim
        self.fusion = ResidualChannelAttention(dim=fused_dim, heads=attention_heads)

        self.main_head = nn.Sequential(
            nn.Linear(fused_dim * attention_heads, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.main_output = nn.Sequential(nn.Linear(hidden_dim, output_dim), nn.Sigmoid())

        self.bg_output = nn.Sequential(nn.Linear(hidden_dim, output_dim), nn.Sigmoid())
        self.audio_output = nn.Sequential(nn.Linear(hidden_dim, output_dim), nn.Sigmoid())
        self.text_output = nn.Sequential(nn.Linear(text_feature_dim, output_dim), nn.Sigmoid())
        self.micro_output = None
        if self.use_micro_expression_features:
            self.micro_output = nn.Sequential(nn.Linear(hidden_dim, output_dim), nn.Sigmoid())

    def _pool_temporal_features(self, x: torch.Tensor) -> torch.Tensor:
        return self.temporal_pool(x.permute(0, 2, 1)).squeeze(2)

    def forward(
        self,
        clip_video: torch.Tensor,
        wav2clip: torch.Tensor,
        clip_text: torch.Tensor,
        bg: torch.Tensor,
        micro_expression: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        bg_feature = self.bg_projection(bg)

        video = clip_video + self.video_position(clip_video)
        video = self.video_graph(video)
        video = self.video_projection(video)
        video = self._pool_temporal_features(video)

        audio = wav2clip + self.audio_position(wav2clip)
        audio = self.audio_graph(audio)
        audio = self.audio_projection(audio)
        audio = self._pool_temporal_features(audio)

        video_audio = cosine_feature_fusion(video, audio)

        text = self.text_encoder(clip_text)
        text = self.text_attention(text)

        micro_feature = None
        if self.use_micro_expression_features:
            if micro_expression is None:
                micro_expression = bg.new_zeros((bg.shape[0], self.micro_expression_dim))
            if micro_expression.ndim == 1:
                micro_expression = micro_expression.unsqueeze(0)
            if micro_expression.shape[-1] != self.micro_expression_dim:
                msg = (
                    f"micro_expression expected {self.micro_expression_dim} values, "
                    f"received {micro_expression.shape[-1]}"
                )
                raise ValueError(msg)
            micro_feature = self.micro_projection(micro_expression)

        fused = self.fusion(bg_feature, video_audio, text, micro_feature)
        fusion_hidden = self.main_head(fused)

        prediction = self.main_output(fusion_hidden)
        bg_prediction = self.bg_output(bg_feature)
        audio_prediction = self.audio_output(video_audio)
        text_prediction = self.text_output(text)

        outputs = {
            "m": prediction,
            "Feature_m": fusion_hidden,
            "clip_clip": bg_prediction,
            "Feature_clip_clip": bg_feature,
            "clip_wav": audio_prediction,
            "Feature_clip_wav": video_audio,
            "clip_t": text_prediction,
            "Feature_clip_t": text,
        }
        if self.use_micro_expression_features and micro_feature is not None and self.micro_output is not None:
            outputs["micro_expression"] = self.micro_output(micro_feature)
            outputs["Feature_micro_expression"] = micro_feature
        return outputs
