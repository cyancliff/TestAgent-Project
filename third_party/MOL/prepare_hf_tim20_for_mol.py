import argparse
import re
import shutil
from pathlib import Path


CLASS_NAMES = ["surprise", "positive", "negative"]


def is_base_smic_sequence(name):
    return name.startswith("SMIC_Apex_") and "_left" not in name and "_rotate" not in name


def sample_name_for_mol(name):
    if name.startswith("SMIC_Apex_"):
        return name.replace("SMIC_Apex_", "", 1)
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


def copy_dataset(src_root, dst_root, max_per_class=None, overwrite=False, base_only=False):
    src_root = Path(src_root)
    dst_root = Path(dst_root)
    if not src_root.exists():
        raise SystemExit(f"Source directory does not exist: {src_root}")

    copied = {}
    for cls_name in CLASS_NAMES:
        src_cls = src_root / cls_name
        dst_cls = dst_root / cls_name
        dst_cls.mkdir(parents=True, exist_ok=True)

        samples = [p for p in src_cls.iterdir() if p.is_dir()]
        if base_only:
            samples = [p for p in samples if is_base_smic_sequence(p.name)]
        samples.sort(key=lambda p: p.name)
        if max_per_class is not None:
            samples = samples[:max_per_class]

        count = 0
        for sample_dir in samples:
            frames = sorted(sample_dir.glob("*.jpg"))
            if len(frames) < 8:
                continue

            out_dir = dst_cls / sample_name_for_mol(sample_dir.name)
            if out_dir.exists() and overwrite:
                shutil.rmtree(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

            for idx, frame in enumerate(frames, start=1):
                shutil.copy2(frame, out_dir / f"image{idx:06d}.jpg")
            count += 1
        copied[cls_name] = count
    return copied


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="D:/MER/datasets/picture_all_Apex_TIM20_unEVM_smic")
    parser.add_argument("--target", default="data/SMIC_data_3")
    parser.add_argument("--max-per-class", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--base-only", action="store_true")
    args = parser.parse_args()

    copied = copy_dataset(args.source, args.target, args.max_per_class, args.overwrite, args.base_only)
    print("Copied TIM20 sequences:")
    for cls_name, count in copied.items():
        print(f"{cls_name}: {count}")


if __name__ == "__main__":
    main()
