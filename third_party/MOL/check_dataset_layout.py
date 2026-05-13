import argparse
from pathlib import Path


DATASETS = {
    ("SAMM", 3): ["surprise", "positive", "negative"],
    ("CASME2", 3): ["surprise", "positive", "negative"],
    ("SMIC", 3): ["surprise", "positive", "negative"],
    ("SAMM", 5): ["surprise", "happiness", "anger", "contempt", "others"],
    ("CASME2", 5): ["surprise", "happiness", "disgust", "repression", "others"],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="SAMM", choices=["SAMM", "CASME2", "SMIC"])
    parser.add_argument("--cls", default=3, type=int, choices=[3, 5])
    args = parser.parse_args()

    key = (args.dataset, args.cls)
    if key not in DATASETS:
        raise SystemExit(f"{args.dataset} does not support {args.cls}-class layout in MOL.")

    root = Path("data") / f"{args.dataset}_data_{args.cls}"
    print(f"Checking {root.resolve()}")
    if not root.exists():
        raise SystemExit(f"Missing dataset root: {root}")

    total_videos = 0
    total_frames = 0
    for cls_name in DATASETS[key]:
        cls_dir = root / cls_name
        if not cls_dir.exists():
            print(f"[missing] {cls_dir}")
            continue

        videos = [p for p in cls_dir.iterdir() if p.is_dir()]
        frame_count = 0
        for video in videos:
            frame_count += len(list(video.glob("*.jpg")))
        total_videos += len(videos)
        total_frames += frame_count
        print(f"[ok] {cls_name}: {len(videos)} videos, {frame_count} jpg frames")

    print(f"Total: {total_videos} videos, {total_frames} jpg frames")
    if total_videos == 0 or total_frames == 0:
        raise SystemExit("No usable videos found. Put extracted frame folders under the class directories.")


if __name__ == "__main__":
    main()
