"""Build the PageIndex workspace entry for the Big Five knowledge base."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
PAGEINDEX_DIR = ROOT_DIR / "PageIndex"
WORKSPACE = PAGEINDEX_DIR / "results"
SOURCE_PATH = PAGEINDEX_DIR / "BigFive_Personality_Knowledge.md"
DOC_NAME = "BigFive_Personality_Knowledge"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(PAGEINDEX_DIR) not in sys.path:
    sys.path.insert(0, str(PAGEINDEX_DIR))

from app.core.config import (  # noqa: E402
    get_deepseek_api_key,
    get_deepseek_rag_model,
    get_deepseek_rag_retrieve_model,
)
from pageindex import PageIndexClient  # noqa: E402


def _to_pageindex_model_name(model_name: str) -> str:
    return model_name if "/" in model_name else f"deepseek/{model_name}"


def _remove_existing_big_five_entries() -> list[str]:
    """Remove old indexed Big Five docs so repeated builds stay deterministic."""
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    meta_path = WORKSPACE / "_meta.json"
    if not meta_path.exists():
        return []

    with meta_path.open(encoding="utf-8") as f:
        meta = json.load(f)

    removed_ids = [
        doc_id
        for doc_id, entry in list(meta.items())
        if entry.get("doc_name") == DOC_NAME
    ]
    for doc_id in removed_ids:
        meta.pop(doc_id, None)
        doc_path = WORKSPACE / f"{doc_id}.json"
        if doc_path.exists():
            doc_path.unlink()

    if removed_ids:
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    return removed_ids


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"Big Five knowledge source not found: {SOURCE_PATH}")

    api_key = get_deepseek_api_key()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required to build the Big Five PageIndex index.")

    removed_ids = _remove_existing_big_five_entries()
    if removed_ids:
        print(f"Removed old Big Five PageIndex documents: {', '.join(removed_ids)}")

    os.environ.setdefault("OPENAI_API_KEY", api_key)
    client = PageIndexClient(
        api_key=api_key,
        model=_to_pageindex_model_name(get_deepseek_rag_model()),
        retrieve_model=_to_pageindex_model_name(get_deepseek_rag_retrieve_model()),
        workspace=str(WORKSPACE),
    )
    doc_id = client.index(str(SOURCE_PATH), mode="md")

    print(f"Big Five PageIndex index built: doc_id={doc_id}")
    print(f"Workspace: {WORKSPACE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
