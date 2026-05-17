import argparse
import random
from pathlib import Path

import numpy as np
import torch

from MOL_model import MOL
from train import train
from utils.metrics import calculate_metrics


def set_random_seed(seed=2024):
    random.seed(seed)
    np.random.seed(np.int64(seed))
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.enabled = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--num_steps", type=int, default=20)
    parser.add_argument("--batch_size", type=int, default=2)
    parser.add_argument("--wdecay", type=float, default=0.001)
    parser.add_argument("--momentum", type=float, default=0.9)
    parser.add_argument("--ldm_weight", type=float, default=0.1)
    parser.add_argument("--of_weight", type=float, default=10)
    parser.add_argument("--mer_weight", type=float, default=1)
    parser.add_argument("--gamma", type=float, default=0.8)
    parser.add_argument("--save_path", default=None)
    parser.add_argument("--pretrained_path", default=None)
    parser.add_argument("--version", default="MOL_selected_baseline")
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--neighbor_num", type=int, default=4)
    parser.add_argument("--dataset", default="SAMM")
    parser.add_argument("--cls", type=int, default=3)
    parser.add_argument("--subjects", nargs="+", required=True)
    args = parser.parse_args()

    set_random_seed(args.seed)
    Path("logs").mkdir(exist_ok=True)
    Path("saved_models").mkdir(exist_ok=True)

    confusion_matrix = [[0 for _ in range(args.cls)] for _ in range(args.cls)]
    train_log_path = Path("logs") / f"{args.version}_train_log.txt"
    test_log_path = Path("logs") / f"{args.version}_test_log.txt"
    with train_log_path.open("w") as train_log_file, test_log_path.open("w") as test_log_file:
        train_log_file.write("----------args----------\n")
        test_log_file.write("----------args----------\n")
        for key, value in vars(args).items():
            print(f"{key}: {value}")
            train_log_file.write(f"{key}: {value}\n")
            test_log_file.write(f"{key}: {value}\n")

        subject_list = args.subjects
        for subject in subject_list:
            test_dataset = torch.load(f"data_processed/{args.dataset}/sub{subject}_{args.cls}cls_test.pth")
            train_subjects = [item for item in subject_list if item != subject]
            train_dataset = None
            for train_subject in train_subjects:
                part = torch.load(f"data_processed/{args.dataset}/sub{train_subject}_{args.cls}cls_train.pth")
                train_dataset = part if train_dataset is None else train_dataset + part
            if train_dataset is None:
                print(f"Skipping subject {subject}: no training subjects")
                continue

            model = MOL(args)
            args.save_path = f"saved_models/{args.version}_{args.dataset}_{subject}_{args.cls}cls.pth"
            train_log_file.write(f"LOSO {subject}\n")
            test_log_file.write(f"LOSO {subject}\n")
            final_acc, subject_confusion_matrix = train(
                args=args,
                model=model,
                train_dataset=train_dataset,
                test_dataset=test_dataset,
                train_log_file=train_log_file,
                test_log_file=test_log_file,
            )
            test_log_file.write(f"LOSO {subject} best_acc:{final_acc}\n")
            for i in range(args.cls):
                for j in range(args.cls):
                    confusion_matrix[i][j] += subject_confusion_matrix[i][j]

        acc, war, uar, wf1, uf1 = calculate_metrics(confusion_matrix)
        final_line = f"acc:{acc}\nwar:{war}\nuar:{uar}\nwf1:{wf1}\nuf1:{uf1}\nconfusion_matrix:{confusion_matrix}\n"
        print(final_line)
        test_log_file.write("----------final_results----------\n")
        test_log_file.write(final_line)


if __name__ == "__main__":
    main()
