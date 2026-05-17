import argparse
import re
import shutil
from pathlib import Path


CLASS_NAMES = ["surprise", "positive", "negative"]


def clean_sample_name(name):
    if name.startswith("CASME2_Apex_"):
        cleaned = name.replace("CASME2_Apex_", "", 1)
        cleaned = re.sub(r"^(disgust|happiness|repression|surprise|others)_", "", cleaned)
        cleaned = cleaned.replace("sub", "", 1)
        return cleaned
    if name.startswith("SAMM_Apex_"):
        cleaned = name.replace("SAMM_Apex_", "", 1)
        cleaned = re.sub(r"^(Anger|Contempt|Happiness|Surprise|Fear|Other)_", "", cleaned)
        return cleaned
    return name


def is_original_sequence(name):
    aug_tokens = ["_left", "_rotate"]
    return not any(token in name for token in aug_tokens)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default="D:/MER/datasets/picture_all_Apex_TIM20_unEVM_crossdata/CASME2_SAMM_cross_dataset_training",
    )
    parser.add_argument("--casme2-target", default="data/CASME2_data_3")
    parser.add_argument("--samm-target", default="data/SAMM_data_3")
    parser.add_argument("--dataset", choices=["both", "CASME2", "SAMM"], default="both")
    parser.add_argument("--include-augmented", action="store_true")
    parser.add_argument("--max-per-class", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        raise SystemExit(f"Source directory does not exist: {source}")

    copied = {}
    for cls_name in CLASS_NAMES:
        src_cls = source / cls_name
        samples = []
        for sample_dir in sorted(p for p in src_cls.iterdir() if p.is_dir()):
            if not args.include_augmented and not is_original_sequence(sample_dir.name):
                continue
            frames = sorted(sample_dir.glob("*.jpg"))
            if len(frames) < 8:
                continue
            if sample_dir.name.startswith("CASME2_Apex_"):
                dataset = "CASME2"
            elif sample_dir.name.startswith("SAMM_Apex_"):
                dataset = "SAMM"
            else:
                continue
            if args.dataset != "both" and args.dataset != dataset:
                continue
            samples.append((dataset, sample_dir, frames))

        if args.max_per_class is not None:
            samples = samples[: args.max_per_class]

        count = 0
        for dataset, sample_dir, frames in samples:
            target = Path(args.casme2_target if dataset == "CASME2" else args.samm_target)
            dst_cls = target / cls_name
            dst_cls.mkdir(parents=True, exist_ok=True)
            out_dir = dst_cls / clean_sample_name(sample_dir.name)
            if out_dir.exists() and args.overwrite:
                shutil.rmtree(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            for idx, frame in enumerate(frames, start=1):
                frame_name = f"img{idx}.jpg" if dataset == "CASME2" else f"{idx}.jpg"
                shutil.copy2(frame, out_dir / frame_name)
            count += 1
        copied[cls_name] = count

    print("Copied crossdata TIM20 sequences:")
    for cls_name, count in copied.items():
        print(f"{cls_name}: {count}")


if __name__ == "__main__":
    main()
