import argparse
import os
import re
from pathlib import Path

import torch

import dataset as mol_dataset


CONFIGS = {
    ("SAMM", 3): {
        "video_list": [
            "./data/SAMM_data_3/surprise/",
            "./data/SAMM_data_3/positive/",
            "./data/SAMM_data_3/negative/",
        ],
        "subjects": [
            "006", "007", "009", "010", "011", "012", "013", "014", "015",
            "016", "017", "018", "019", "020", "021", "022", "023", "024",
            "026", "028", "030", "031", "032", "033", "034", "035", "036", "037",
        ],
    },
    ("CASME2", 3): {
        "video_list": [
            "./data/CASME2_data_3/surprise/",
            "./data/CASME2_data_3/positive/",
            "./data/CASME2_data_3/negative/",
        ],
        "subjects": [
            "17", "26", "16", "09", "05", "24", "02", "13", "04", "23",
            "11", "12", "08", "14", "03", "19", "01", "10", "20", "21",
            "22", "15", "06", "25", "07",
        ],
    },
    ("SMIC", 3): {
        "video_list": [
            "./data/SMIC_data_3/surprise/",
            "./data/SMIC_data_3/positive/",
            "./data/SMIC_data_3/negative/",
        ],
        "subjects": [
            "s1", "s2", "s3", "s4", "s5", "s6", "s8", "s9",
            "s11", "s12", "s13", "s14", "s15", "s18", "s19", "s20",
        ],
    },
}


def subjects_with_data(video_lists, subjects):
    videos = [os.listdir(path) for path in video_lists]
    present = []
    for subject in subjects:
        for class_video in videos:
            if any(v.split("_")[0] == subject for v in class_video):
                present.append(subject)
                break
    return present, videos


def is_numeric_subject(name):
    return re.fullmatch(r"\d+|s\d+", name) is not None


def build_dataset_list(videos, subject, cls_num):
    dataset_list = [[] for _ in range(cls_num)]
    for cla, class_video in enumerate(videos):
        for v in class_video:
            if v.split("_")[0] == subject:
                dataset_list[cla].append(v)
    return dataset_list


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="SAMM", choices=["SAMM", "CASME2", "SMIC"])
    parser.add_argument("--cls", default=3, type=int, choices=[3])
    parser.add_argument("--mode", default="both", choices=["train", "test", "both"])
    parser.add_argument("--subjects", nargs="*")
    parser.add_argument("--all-present", action="store_true")
    parser.add_argument("--net-test", action="store_true")
    args = parser.parse_args()

    cfg = CONFIGS[(args.dataset, args.cls)]
    mol_dataset.VIDEO_LIST = cfg["video_list"]

    present_subjects, videos = subjects_with_data(cfg["video_list"], cfg["subjects"])
    present_subjects = [s for s in present_subjects if is_numeric_subject(s)]
    subjects = args.subjects or (present_subjects if args.all_present or not args.subjects else [])
    subjects = [s for s in subjects if s in present_subjects]
    subjects = sorted(subjects, key=lambda x: int(x[1:] if x.startswith("s") else x))
    print("subjects:", subjects)

    out_root = Path("data_processed") / args.dataset
    out_root.mkdir(parents=True, exist_ok=True)
    modes = ["train", "test"] if args.mode == "both" else [args.mode]

    for subject in subjects:
        dataset_list = build_dataset_list(videos, subject, args.cls)
        if args.net_test:
            dataset_list = [c[:1] for c in dataset_list]
        for mode in modes:
            mode_train = mode == "train"
            save_path = out_root / f"sub{subject}_{args.cls}cls_{mode}.pth"
            print("saving", save_path)
            ds = mol_dataset.videoDataset(dataset_list, mode_train=mode_train)
            torch.save(ds, save_path)


if __name__ == "__main__":
    main()
