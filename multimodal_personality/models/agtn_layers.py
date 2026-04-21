"""Core layers adapted from the reference AGTN-MTL implementation.

The original public code mixes a few unused third-party imports with the
actual model layers. This module keeps only the components that are required
by the multimodal regression model so the project can run with plain PyTorch.
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F


def cosine_feature_fusion(x: torch.Tensor, y: torch.Tensor, epsilon: float = 1e-8) -> torch.Tensor:
    """Mirror the reference feature interaction used for video-audio fusion."""

    x = x + epsilon
    y = y + epsilon
    return x * y / ((x**0.5) * (y**0.5))


def normalize_digraph(adjacency: torch.Tensor) -> torch.Tensor:
    """Normalize a dense adjacency matrix for message passing."""

    if adjacency.ndim != 3:
        msg = f"Expected a 3D adjacency tensor, received shape={tuple(adjacency.shape)!r}"
        raise ValueError(msg)

    batch_size, num_nodes, _ = adjacency.shape
    node_degrees = adjacency.detach().sum(dim=-1)
    degree_inv_sqrt = node_degrees**-0.5
    degree_inv_sqrt[torch.isinf(degree_inv_sqrt)] = 0

    norm = torch.eye(num_nodes, device=adjacency.device, dtype=adjacency.dtype)
    norm = norm.view(1, num_nodes, num_nodes) * degree_inv_sqrt.view(batch_size, num_nodes, 1)
    return torch.bmm(torch.bmm(norm, adjacency), norm)


class FeedForwardSelfAttention(nn.Module):
    """A small Transformer-style refinement block used after graph updates."""

    def __init__(self, d_model: int, dim_feedforward: int, nhead: int = 8, dropout: float = 0.1) -> None:
        super().__init__()
        self.self_attn = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=nhead,
            dropout=dropout,
            bias=True,
            batch_first=True,
        )
        self.linear1 = nn.Linear(d_model, dim_feedforward)
        self.linear2 = nn.Linear(dim_feedforward, d_model)
        self.activation = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

    def _self_attention(self, x: torch.Tensor) -> torch.Tensor:
        attended, _ = self.self_attn(x, x, x, need_weights=False)
        return self.dropout1(attended)

    def _feed_forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.linear1(x)
        x = self.activation(x)
        x = self.dropout(x)
        x = self.linear2(x)
        return self.dropout2(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.norm1(x + self._self_attention(x))
        x = self.norm2(x + self._feed_forward(x))
        return x


class PositionalEncoding(nn.Module):
    """Learnable sinusoidal positional encoding."""

    def __init__(self, d_model: int, max_seq_len: int) -> None:
        super().__init__()
        pe = torch.zeros(max_seq_len, d_model)
        position = torch.arange(0, max_seq_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.pe = nn.Parameter(pe, requires_grad=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 3:
            msg = f"Expected a 3D tensor, received shape={tuple(x.shape)!r}"
            raise ValueError(msg)

        if x.shape[1] > self.pe.shape[0]:
            msg = f"Sequence length {x.shape[1]} exceeds configured maximum {self.pe.shape[0]}"
            raise ValueError(msg)

        mask = torch.ones_like(x)
        mask[x.sum(dim=-1) == 0, :] = 0
        return self.pe[: x.shape[1]].unsqueeze(0) * mask


class GraphConvBlock(nn.Module):
    """Dense graph convolution block from the reference implementation."""

    def __init__(self, in_channels: int, neighbor_num: int, metric: str = "ones") -> None:
        super().__init__()
        self.in_channels = in_channels
        self.metric = metric
        self.neighbor_num = neighbor_num

        self.update_linear = nn.Linear(in_channels, in_channels)
        self.aggregate_linear = nn.Linear(in_channels, in_channels)
        self.batch_norm = nn.BatchNorm1d(in_channels)
        self.activation = nn.ReLU()
        self.ffn = FeedForwardSelfAttention(d_model=in_channels, dim_feedforward=in_channels)

        self.update_linear.weight.data.normal_(0, math.sqrt(2.0 / in_channels))
        self.aggregate_linear.weight.data.normal_(0, math.sqrt(2.0 / in_channels))
        self.batch_norm.weight.data.fill_(1.0)
        self.batch_norm.bias.data.zero_()

    def _build_graph(self, x: torch.Tensor) -> torch.Tensor:
        batch_size, num_nodes, channels = x.shape
        if self.metric == "dots":
            similarity = torch.einsum("bij,bkj->bik", x.detach(), x.detach())
            threshold = similarity.topk(k=self.neighbor_num, dim=-1, largest=True)[0][:, :, -1].view(
                batch_size,
                num_nodes,
                1,
            )
            return (similarity >= threshold).float()

        if self.metric == "cosine":
            similarity = F.normalize(x.detach(), p=2, dim=-1)
            similarity = torch.einsum("bij,bkj->bik", similarity, similarity)
            threshold = similarity.topk(k=self.neighbor_num, dim=-1, largest=True)[0][:, :, -1].view(
                batch_size,
                num_nodes,
                1,
            )
            return (similarity >= threshold).float()

        if self.metric == "l1":
            tiled = x.detach().repeat(1, num_nodes, 1).view(batch_size, num_nodes, num_nodes, channels)
            distance = torch.abs(tiled.transpose(1, 2) - tiled).sum(dim=-1)
            threshold = distance.topk(k=self.neighbor_num, dim=-1, largest=False)[0][:, :, -1].view(
                batch_size,
                num_nodes,
                1,
            )
            return (distance <= threshold).float()

        if self.metric == "ones":
            return torch.ones(batch_size, num_nodes, num_nodes, device=x.device, dtype=x.dtype)

        raise ValueError(f"Unsupported graph metric: {self.metric}")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        adjacency = self._build_graph(x.detach())
        norm_adjacency = normalize_digraph(adjacency)
        aggregated = torch.einsum("bij,bjk->bik", norm_adjacency, self.aggregate_linear(x))
        updated = aggregated + self.update_linear(x)
        updated = self.batch_norm(updated.transpose(1, 2)).transpose(1, 2)
        x = self.activation(x + updated)
        return self.ffn(x)


class ResidualChannelAttention(nn.Module):
    """Feature-level channel attention used for multimodal fusion."""

    def __init__(self, dim: int, heads: int = 8) -> None:
        super().__init__()
        self.attentions = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(dim, dim),
                    nn.Tanh(),
                    nn.Linear(dim, dim),
                    nn.Tanh(),
                )
                for _ in range(heads)
            ]
        )

    def forward(self, *inputs: torch.Tensor) -> torch.Tensor:
        parts = [tensor for tensor in inputs if tensor is not None]
        if not parts:
            raise ValueError("At least one modality tensor is required for fusion")

        fused = torch.cat(parts, dim=-1)
        outputs = []
        for attention in self.attentions:
            weights = attention(fused)
            outputs.append(weights * fused + fused)
        return torch.cat(outputs, dim=-1)


class TemporalAttention(nn.Module):
    """Attention pooling over the transcript sequence."""

    def __init__(self, in_dim: int, max_seq_len: int) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.rand(in_dim, 1))
        self.bias = nn.Parameter(torch.zeros(max_seq_len, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 3:
            msg = f"Expected a 3D transcript tensor, received shape={tuple(x.shape)!r}"
            raise ValueError(msg)

        time_steps = x.shape[1]
        if time_steps > self.bias.shape[0]:
            msg = f"Transcript length {time_steps} exceeds configured maximum {self.bias.shape[0]}"
            raise ValueError(msg)

        score = torch.matmul(x, self.weight) + self.bias[:time_steps]
        score = torch.softmax(score, dim=1)
        attended = x + x * score
        return torch.mean(attended, dim=1, keepdim=False)


class SequenceEncoder(nn.Module):
    """Bidirectional GRU encoder for transcript embeddings."""

    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        num_layers: int,
        dropout: float,
        bidirectional: bool = True,
    ) -> None:
        super().__init__()
        self.rnn = nn.GRU(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=bidirectional,
            dropout=dropout,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        output, _ = self.rnn(x)
        return output
