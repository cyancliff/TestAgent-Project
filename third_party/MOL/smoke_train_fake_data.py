import argparse
from pathlib import Path

import torch
from torch.utils.data import Dataset

from MOL_model import MOL
from train import train


class FakeMicroExpressionDataset(Dataset):
    def __init__(self, size=2, cls=3):
        self.size = size
        self.cls = cls

    def __len__(self):
        return self.size

    def __getitem__(self, index):
        video = torch.rand(1, 8, 128, 128)
        flow = torch.rand(2, 7, 128, 128)
        ldm = torch.rand(136, 8) * 128
        label = torch.tensor(index % self.cls, dtype=torch.long)
        return video, flow, ldm, label


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cls", type=int, default=3)
    parser.add_argument("--neighbor_num", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--num_steps", type=int, default=0)
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--wdecay", type=float, default=0.001)
    parser.add_argument("--of_weight", type=float, default=0.0)
    parser.add_argument("--ldm_weight", type=float, default=0.0)
    parser.add_argument("--mer_weight", type=float, default=1.0)
    parser.add_argument("--save_path", default="saved_models/fake_smoke.pth")
    args = parser.parse_args()

    Path("logs").mkdir(exist_ok=True)
    Path("saved_models").mkdir(exist_ok=True)
    model = MOL(args)
    dataset = FakeMicroExpressionDataset(size=2, cls=args.cls)
    with open("logs/fake_smoke_train_log.txt", "w") as train_log, open("logs/fake_smoke_test_log.txt", "w") as test_log:
        train(args, model, dataset, dataset, train_log, test_log)
    print("fake smoke training finished")


if __name__ == "__main__":
    main()
