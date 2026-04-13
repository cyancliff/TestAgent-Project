"""
阶段管理服务：处理分阶段作答的推进、校验、提交逻辑
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.core.constants import STAGES, STAGE_DIM_MAP, STAGE_QUESTION_COUNT
from app.models.question import AnswerRecord, AssessmentSession, ModuleDebateResult, Question, User


class StageService:
    """阶段管理服务"""

    def __init__(self, db: Session, session_id: int, user_id: int):
        self.db = db
        self.session_id = session_id
        self.user_id = user_id
        self._session: Optional[AssessmentSession] = None

    @property
    def session(self) -> AssessmentSession:
        if self._session is None:
            self._session = self.db.query(AssessmentSession).filter(
                AssessmentSession.id == self.session_id,
                AssessmentSession.user_id == self.user_id,
            ).first()
            if self._session is None:
                raise ValueError("会话不存在")
        return self._session

    def get_current_stage(self) -> str:
        """获取当前阶段"""
        stage = self.session.current_stage
        return stage if stage else "intro"

    def get_submitted_stages(self) -> list[str]:
        """获取已提交的阶段列表"""
        raw = self.session.submitted_stages
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(raw, list):
            return [str(s) for s in raw]
        return []

    def get_stage_dimension(self, stage: str) -> Optional[str]:
        """获取阶段对应的 dimension_id"""
        return STAGE_DIM_MAP.get(stage)

    def get_stage_question_count(self, stage: str) -> int:
        """获取阶段预期题目数"""
        return STAGE_QUESTION_COUNT.get(stage, 10)

    def get_answered_in_stage(self, stage: str) -> list[AnswerRecord]:
        """获取某阶段已作答的记录（基于题目 dimension_id 匹配）"""
        all_records = self.db.query(AnswerRecord).filter(
            AnswerRecord.session_id == self.session_id,
            AnswerRecord.user_id == self.user_id,
        ).all()
        if not all_records:
            return []

        target_dim = self.get_stage_dimension(stage)
        if not target_dim:
            return []

        exam_nos = [r.exam_no for r in all_records]
        questions = self.db.query(Question).filter(
            Question.exam_no.in_(exam_nos)
        ).all() if exam_nos else []
        q_map = {q.exam_no: q for q in questions}

        return [r for r in all_records if q_map.get(r.exam_no) and q_map[r.exam_no].dimension_id == target_dim]

    def is_stage_complete(self, stage: str) -> bool:
        """判断某阶段是否已答满"""
        answered = self.get_answered_in_stage(stage)
        return len(answered) >= self.get_stage_question_count(stage)

    def get_stage_answered_count(self, stage: str) -> int:
        """获取某阶段已答题数"""
        return len(self.get_answered_in_stage(stage))

    def get_stage_questions(self, stage: str, exclude_answered: bool = True) -> list[Question]:
        """获取某阶段的题目列表"""
        dim_id = self.get_stage_dimension(stage)
        if not dim_id:
            return []

        query = self.db.query(Question).filter(Question.dimension_id == dim_id)

        if exclude_answered:
            answered_records = self.db.query(AnswerRecord).filter(
                AnswerRecord.session_id == self.session_id,
                AnswerRecord.user_id == self.user_id,
            ).all()
            if answered_records:
                answered_exam_nos = [r.exam_no for r in answered_records]
                query = query.filter(Question.exam_no.notin_(answered_exam_nos))

        return query.order_by(Question.exam_no).all()

    def get_all_answer_records(self) -> list[AnswerRecord]:
        """获取当前 session 的所有作答记录"""
        return self.db.query(AnswerRecord).filter(
            AnswerRecord.session_id == self.session_id,
            AnswerRecord.user_id == self.user_id,
        ).order_by(AnswerRecord.created_at.asc()).all()

    def advance_to_next_stage(self) -> Optional[str]:
        """推进到下一阶段，返回新阶段名；如果全部完成返回 None"""
        submitted = self.get_submitted_stages()
        current = self.get_current_stage()

        # 标记当前阶段为已提交
        if current not in submitted:
            submitted.append(current)
            self.session.submitted_stages = submitted

        # 找到下一个未提交的阶段
        for stage in STAGES:
            if stage not in submitted:
                self.session.current_stage = stage
                self.db.commit()
                return stage

        # 全部阶段完成
        self.session.current_stage = None
        self.session.status = "completed"
        self.db.commit()
        return None

    def restart_session(self):
        """重新作答：重置阶段，清理辩论结果，保留作答记录用于 upsert"""
        self.session.current_stage = "intro"
        self.session.submitted_stages = []
        self.session.status = "active"

        # 清理旧辩论结果（重新作答需要重新辩论）
        self.db.query(ModuleDebateResult).filter(
            ModuleDebateResult.session_id == self.session_id,
        ).delete()
        # 保留 AnswerRecord（用于 upsert 复用）
        self.db.commit()
