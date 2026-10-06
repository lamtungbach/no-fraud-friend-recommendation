"""
Kiến trúc Mạng nơ-ron Đồ thị Đa quan hệ (R-GCN) phát hiện gian lận / Bot trên MGTAB.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class NormalizedRGCNLayer(nn.Module):
    """
    Lớp Tích chập Đồ thị Đa quan hệ có chuẩn hóa bậc (Normalized R-GCN Layer).
    Tích hợp ma trận biến đổi riêng cho từng quan hệ và self-loop transformation.
    """

    def __init__(self, in_dim: int, out_dim: int, num_relations: int = 7):
        super().__init__()
        self.num_relations = num_relations
        self.rel_linear = nn.Parameter(torch.Tensor(num_relations, in_dim, out_dim))
        self.self_linear = nn.Linear(in_dim, out_dim)
        nn.init.xavier_uniform_(self.rel_linear)

    def forward(self, x: torch.Tensor, pre_edges: list, pre_weights: list) -> torch.Tensor:
        """
        Lan truyền thông điệp qua các cạnh theo từng loại quan hệ.
        """
        out = self.self_linear(x)
        for r in range(self.num_relations):
            src, dst = pre_edges[r]
            w_norm = pre_weights[r]
            h = torch.matmul(x, self.rel_linear[r])
            msg = h[src] * w_norm
            out.index_add_(0, dst, msg)
        return out


class FraudDetectionRGCN(nn.Module):
    """
    Mô hình phân loại nhị phân (Human vs Bot) 2 tầng R-GCN với BatchNorm và Dropout.
    Input: Đặc trưng thuộc tính + cấu trúc 7 quan hệ MGTAB.
    Output: Logits 2 lớp (0: Human, 1: Bot).
    """

    def __init__(self, in_dim: int = 788, hidden_dim: int = 64, out_dim: int = 2, dropout: float = 0.3):
        super().__init__()
        self.conv1 = NormalizedRGCNLayer(in_dim, hidden_dim)
        self.bn1 = nn.BatchNorm1d(hidden_dim)
        self.conv2 = NormalizedRGCNLayer(hidden_dim, out_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, pre_edges: list, pre_weights: list) -> torch.Tensor:
        x = self.conv1(x, pre_edges, pre_weights)
        x = self.bn1(x)
        x = F.relu(x)
        x = self.dropout(x)
        x = self.conv2(x, pre_edges, pre_weights)
        return x


def save_checkpoint(model: nn.Module, path: str = "weights/rgcn_mgtab_best.pt") -> str:
    """
    Lưu state_dict trọng số của mô hình ra file .pt.
    Mặc định: weights/rgcn_mgtab_best.pt
    """
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    torch.save(model.state_dict(), path)
    return path


def load_checkpoint(
    model: nn.Module | None = None,
    path: str = "weights/rgcn_mgtab_best.pt",
    device: str = "cpu"
) -> FraudDetectionRGCN:
    """
    Tải trọng số đã huấn luyện từ file checkpoint vào mô hình.
    """
    if model is None:
        model = FraudDetectionRGCN()
    state_dict = torch.load(path, map_location=device, weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    return model
