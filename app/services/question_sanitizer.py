import logging
import re

from sqlalchemy.orm import Session

from app.models.assessment import Question

logger = logging.getLogger(__name__)

_QUESTION_NUMBER_PREFIX_RE = re.compile(
    r"""
    ^\s*
    (?:
        第\s*\d{1,3}\s*题\s*[:：、.．。]?\s* |
        [\(（]\s*\d{1,3}\s*[\)）]\s*[:：、.．。]?\s* |
        \d{1,3}\s*[.．、。]\s* |
        \d{1,3}\s*[\)）]\s*
    )+
    """,
    re.VERBOSE,
)


def sanitize_question_content(content: str | None) -> str | None:
    if content is None:
        return None

    cleaned = content.strip()
    previous = None

    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = _QUESTION_NUMBER_PREFIX_RE.sub("", cleaned).strip()

    return cleaned


def repair_question_contents(db: Session) -> int:
    updated_count = 0

    for question in db.query(Question).all():
        cleaned = sanitize_question_content(question.content)
        if cleaned is not None and cleaned != question.content:
            question.content = cleaned
            updated_count += 1

    if updated_count:
        db.commit()
        logger.info("Normalized %s question contents in database", updated_count)

    return updated_count
