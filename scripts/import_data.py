import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.core.database import SessionLocal
from app.models.assessment import Question
from app.services.question_sanitizer import sanitize_question_content

_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
_QUESTIONS_FILE = os.path.join(_DATA_DIR, "atmr_full_questions.json")


def calculate_avg_time(question_text: str, options: list) -> float:
    text_length = len(question_text or "")
    options_length = sum(len(opt) for opt in options) if options else 0
    total_length = text_length + options_length
    return round((total_length / 10.0) + 2.0, 1)


def estimate_question_params(scores):
    if not scores or len(scores) < 2:
        return 0.5, 0.7

    try:
        score_values = [float(score) for score in scores]
        avg_score = sum(score_values) / len(score_values)
        max_score = max(score_values)
        variance = sum((score - avg_score) ** 2 for score in score_values) / len(score_values)

        difficulty = 1.0 - (avg_score / max_score) if max_score > 0 else 0.5
        max_variance = 6.25
        discrimination = min(0.5 + (variance / max_variance), 1.0)

        difficulty = max(0.0, min(1.0, difficulty))
        discrimination = max(0.3, min(1.0, discrimination))
        return difficulty, discrimination
    except Exception:
        return 0.5, 0.7


def import_questions_to_db():
    print("Starting question bank import...")

    try:
        with open(_QUESTIONS_FILE, "r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except FileNotFoundError:
        print(f"Questions file not found: {_QUESTIONS_FILE}")
        return

    db = SessionLocal()
    created_count = 0
    updated_count = 0

    try:
        for item in raw_data:
            exam_no = item.get("examNo")
            q_content = sanitize_question_content(item.get("exam", "")) or ""
            q_options = item.get("options", [])
            existing_question = db.query(Question).filter(Question.exam_no == exam_no).first()

            if existing_question:
                if q_content and existing_question.content != q_content:
                    existing_question.content = q_content
                    updated_count += 1
                continue

            is_reverse = bool(item.get("reversalDesc"))
            calculated_time = calculate_avg_time(q_content, q_options)
            difficulty, discrimination = estimate_question_params(item.get("scores", []))

            db.add(
                Question(
                    exam_no=exam_no,
                    dimension_id=item.get("examTypeId"),
                    content=q_content,
                    options=q_options,
                    scores=item.get("scores", []),
                    trait_label=item.get("title"),
                    ai_analysis_prompt=item.get("description"),
                    is_reverse=is_reverse,
                    avg_time=calculated_time,
                    difficulty=difficulty,
                    discrimination=discrimination,
                )
            )
            created_count += 1

        db.commit()
    finally:
        db.close()

    print(f"Question bank import complete. Created {created_count} questions.")
    if updated_count:
        print(f"Normalized {updated_count} existing question contents.")


if __name__ == "__main__":
    import_questions_to_db()
