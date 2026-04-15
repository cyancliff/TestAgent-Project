"""Extract encrypted CFI-V2 test videos with resume support."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from zipfile import ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


OUTER_PASSWORD = b"zeAzLQN7DnSIexQukc9W"
INNER_PASSWORD = b".chalearnLAPFirstImpressionsSECONDRoundICPRWorkshop2016."


def ensure_parent(path: Path) -> None:
    """Create a parent directory if it does not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


def copy_member(zf: ZipFile, member_name: str, destination: Path, pwd: bytes | None = None) -> None:
    """Extract a single zip member to a destination path."""
    ensure_parent(destination)
    with zf.open(member_name, pwd=pwd) as source, destination.open("wb") as target:
        shutil.copyfileobj(source, target, length=1024 * 1024)


def extract_outer_archives(test_root: Path, nested_dir: Path) -> tuple[int, int]:
    """Extract inner zip archives from the encrypted outer archives."""
    outer_archives = ["test-1e.zip", "test-2e.zip"]
    extracted_files = 0
    skipped_files = 0

    for archive_name in outer_archives:
        archive_path = test_root / archive_name
        with ZipFile(archive_path) as zf:
            members = [info for info in zf.infolist() if not info.is_dir()]
            print(f"[outer] {archive_name}: members={len(members)}")
            for info in members:
                destination = nested_dir / info.filename
                if destination.exists() and destination.stat().st_size == info.file_size:
                    skipped_files += 1
                    continue
                copy_member(zf, info.filename, destination, pwd=OUTER_PASSWORD)
                extracted_files += 1

    return extracted_files, skipped_files


def extract_inner_archives(nested_dir: Path, videos_dir: Path) -> tuple[int, int, int]:
    """Extract mp4 files from the encrypted inner archives."""
    inner_archives = sorted(nested_dir.glob("**/test80_*.zip"))
    extracted_archives = 0
    extracted_videos = 0
    skipped_videos = 0

    print(f"[inner] archives_found={len(inner_archives)}")
    for index, inner_archive in enumerate(inner_archives, start=1):
        with ZipFile(inner_archive) as zf:
            members = [info for info in zf.infolist() if not info.is_dir()]
            for info in members:
                destination = videos_dir / Path(info.filename).name
                if destination.exists() and destination.stat().st_size == info.file_size:
                    skipped_videos += 1
                    continue
                copy_member(zf, info.filename, destination, pwd=INNER_PASSWORD)
                extracted_videos += 1
        extracted_archives += 1
        if index % 5 == 0 or index == len(inner_archives):
            current_mp4 = len(list(videos_dir.glob("*.mp4")))
            print(
                f"[inner] done={index}/{len(inner_archives)} "
                f"extracted_videos={extracted_videos} skipped_videos={skipped_videos} current_mp4={current_mp4}"
            )

    return extracted_archives, extracted_videos, skipped_videos


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract encrypted CFI-V2 test videos with resume support")
    parser.add_argument(
        "--test-root",
        default="multimodal_personality/data/cfi_v2/test",
        help="Root directory of the CFI-V2 test phase",
    )
    parser.add_argument(
        "--nested-dir",
        default="multimodal_personality/data/cfi_v2/test/videos/_nested_test_archives",
        help="Directory used to store extracted inner zip archives",
    )
    args = parser.parse_args()

    test_root = Path(args.test_root)
    videos_dir = test_root / "videos"
    nested_dir = Path(args.nested_dir)
    videos_dir.mkdir(parents=True, exist_ok=True)
    nested_dir.mkdir(parents=True, exist_ok=True)

    outer_extracted, outer_skipped = extract_outer_archives(test_root=test_root, nested_dir=nested_dir)
    inner_done, video_extracted, video_skipped = extract_inner_archives(nested_dir=nested_dir, videos_dir=videos_dir)
    final_mp4 = len(list(videos_dir.glob("*.mp4")))

    print(
        "[summary] "
        f"outer_extracted={outer_extracted} outer_skipped={outer_skipped} "
        f"inner_archives_done={inner_done} video_extracted={video_extracted} "
        f"video_skipped={video_skipped} final_mp4={final_mp4}"
    )


if __name__ == "__main__":
    main()
