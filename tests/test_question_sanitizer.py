from unittest.mock import MagicMock

import pytest

from app.services.question_sanitizer import repair_question_contents, sanitize_question_content


@pytest.mark.parametrize(
    ("raw_content", "expected"),
    [
        ("50.我喜欢不断挑战自我，突破现有状态", "我喜欢不断挑战自我，突破现有状态"),
        ("25. 我常常会根据自己的心情来决定做事方式", "我常常会根据自己的心情来决定做事方式"),
        ("（12）我会主动规划长期目标", "我会主动规划长期目标"),
        ("第8题：我更关注过程而不是结果", "我更关注过程而不是结果"),
        ("2024年我更关注长期成长", "2024年我更关注长期成长"),
    ],
)
def test_sanitize_question_content(raw_content, expected):
    assert sanitize_question_content(raw_content) == expected


def test_repair_question_contents_updates_dirty_records():
    db = MagicMock()
    dirty_question = MagicMock(content="50.我喜欢不断挑战自我，突破现有状态")
    clean_question = MagicMock(content="我能在压力下保持稳定")
    db.query.return_value.all.return_value = [dirty_question, clean_question]

    updated_count = repair_question_contents(db)

    assert updated_count == 1
    assert dirty_question.content == "我喜欢不断挑战自我，突破现有状态"
    db.commit.assert_called_once()


def test_repair_question_contents_skips_commit_when_nothing_changes():
    db = MagicMock()
    db.query.return_value.all.return_value = [MagicMock(content="我能在压力下保持稳定")]

    updated_count = repair_question_contents(db)

    assert updated_count == 0
    db.commit.assert_not_called()
