# app/api/assessment.py

import asyncio
import json
import queue
import threading

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from app.models.question import SessionLocal, Question, AnswerRecord, AssessmentSession
from app.services.ai_detector import check_anomaly_and_generate_question
from app.services.report_service import build_debate_context, save_report_to_file
from agent.debate_manager import run_debate_streaming

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Schema 定义 ---
class StartSessionRequest(BaseModel):
    user_id: int

class AnswerSubmitRequest(BaseModel):
    session_id: int
    user_id: int
    exam_no: str
    selected_option: str
    time_spent: float


class AnswerSubmitResponse(BaseModel):
    status: str
    message: str
    score: float
    follow_up_question: Optional[str] = None


class ExplanationSubmitRequest(BaseModel):
    session_id: int
    user_id: int
    exam_no: str
    text: str


# --- 接口 0：启动新会话 ---
@router.post("/start-session")
async def start_session(payload: StartSessionRequest, db: Session = Depends(get_db)):
    new_session = AssessmentSession(user_id=payload.user_id, status='active')
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return {"session_id": new_session.id, "status": "success"}


# --- 接口 1：获取题目 ---
# --- 接口 1：获取题目 (10题极速测试版) ---
TEST_LIMIT = 10  # 极速测试版只取前 10 题


@router.get("/question/{index}")
async def get_question(index: int, db: Session = Depends(get_db)):
    # 核心拦截：如果前端请求的题号达到了 10，直接告诉它测试结束了！
    if index >= TEST_LIMIT:
        raise HTTPException(status_code=404, detail="10题极速测试已完成")

    db_question = db.query(Question).offset(index).limit(1).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="题库已做完")

    return {
        "examNo": db_question.exam_no,
        "exam": db_question.content,
        "options": db_question.options,
        "total": TEST_LIMIT  # 动态告诉前端，总进度条只有 10
    }

# --- 接口 2：提交答案 (含自动算分与持久化) ---
@router.post("/submit", response_model=AnswerSubmitResponse)
async def submit_answer(payload: AnswerSubmitRequest, db: Session = Depends(get_db)):
    db_question = db.query(Question).filter(Question.exam_no == payload.exam_no).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 1. 智能计算本题得分
    current_score = 0.0
    try:
        # 找到用户选的选项在列表中的索引，然后去 scores 列表里拿对应的分数
        opt_index = db_question.options.index(payload.selected_option)
        current_score = float(db_question.scores[opt_index])
    except Exception as e:
        print(f"算分出错: {e}")

    # 2. AI 瞬间拦截逻辑
    detection_result = await check_anomaly_and_generate_question(
        time_spent=payload.time_spent,
        avg_time=db_question.avg_time,
        question_content=db_question.content,
        selected_option=payload.selected_option
    )

    # 3. 写入数据库！
    is_anomaly_flag = 1 if detection_result["status"] == "anomaly" else 0
    new_record = AnswerRecord(
        session_id=payload.session_id,
        user_id=payload.user_id,
        exam_no=payload.exam_no,
        selected_option=payload.selected_option,
        score=current_score,
        time_spent=payload.time_spent,
        is_anomaly=is_anomaly_flag,
        ai_follow_up=detection_result.get("follow_up")
    )
    db.add(new_record)
    db.commit()

    return AnswerSubmitResponse(
        status=detection_result["status"],
        message="记录已成功存入数据库",
        score=current_score,
        follow_up_question=detection_result.get("follow_up")
    )


# --- 接口 3：提交补充解释 (新增！) ---
@router.post("/submit_explanation")
async def submit_explanation(payload: ExplanationSubmitRequest, db: Session = Depends(get_db)):
    # 找到刚才那条被拦截的异常记录
    record = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == payload.session_id,
        AnswerRecord.user_id == payload.user_id,
        AnswerRecord.exam_no == payload.exam_no,
        AnswerRecord.is_anomaly == 1
    ).order_by(AnswerRecord.created_at.desc()).first()

    if record:
        record.user_explanation = payload.text
        db.commit()
        return {"status": "success", "message": "解释已入库"}

    raise HTTPException(status_code=404, detail="找不到对应的异常记录")


@router.post("/finish")
async def finish_assessment(
        user_id: str,
        session_id: int,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    """
    前端答完10题后调用此接口。
    返回成功响应，提示前端连接流式端点观看实时辩论。
    """
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if session:
        session.status = 'completed'
        from datetime import datetime
        session.finished_at = datetime.now()
        db.commit()

    return {
        "status": "success",
        "message": "测评已完成！请连接 /finish-stream 端点观看专家评审团的实时辩论并获取最终报告。"
    }


@router.get("/finish-stream")
async def finish_assessment_stream(user_id: str, session_id: int):
    """
    SSE 端点：实时推送多智能体辩论过程到前端。
    前端用 EventSource 连接此接口。
    """
    db = SessionLocal()

    try:
        prompt = build_debate_context(user_id, db, session_id)
    except ValueError as e:
        db.close()
        raise HTTPException(status_code=404, detail=str(e))

    message_queue = queue.Queue()

    # 在后台线程启动辩论
    debate_thread = threading.Thread(
        target=run_debate_streaming,
        args=(prompt, message_queue),
        daemon=True
    )
    debate_thread.start()

    async def event_generator():
        try:
            while True:
                try:
                    # 在线程池中执行阻塞的 queue.get，不阻塞事件循环
                    msg = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: message_queue.get(block=True, timeout=2.0)
                    )
                except queue.Empty:
                    # 超时但辩论还在进行，发送心跳保持连接
                    if debate_thread.is_alive():
                        yield ": heartbeat\n\n"
                        continue
                    else:
                        # 辩论线程已结束，再尝试清空队列中剩余消息
                        remaining_handled = False
                        while not message_queue.empty():
                            try:
                                msg = message_queue.get_nowait()
                                if msg["type"] == "message":
                                    data = json.dumps({"agent": msg["agent"], "content": msg["content"]}, ensure_ascii=False)
                                    yield f"event: agent_message\ndata: {data}\n\n"
                                elif msg["type"] == "done":
                                    file_path = save_report_to_file(user_id, msg["content"])
                                    save_report_to_session(db, session_id, msg["content"], file_path)
                                    data = json.dumps({"report": msg["content"]}, ensure_ascii=False)
                                    yield f"event: debate_complete\ndata: {data}\n\n"
                                    remaining_handled = True
                                elif msg["type"] == "error":
                                    data = json.dumps({"message": msg["content"]}, ensure_ascii=False)
                                    yield f"event: error\ndata: {data}\n\n"
                                    remaining_handled = True
                            except queue.Empty:
                                break
                        if not remaining_handled:
                            # 队列真的为空且线程已死，发送兜底错误
                            data = json.dumps({"message": "辩论服务异常终止，请检查后端日志"}, ensure_ascii=False)
                            yield f"event: error\ndata: {data}\n\n"
                        break

                if msg["type"] == "message":
                    data = json.dumps({"agent": msg["agent"], "content": msg["content"]}, ensure_ascii=False)
                    yield f"event: agent_message\ndata: {data}\n\n"

                elif msg["type"] == "done":
                    # 保存报告到文件和数据库
                    file_path = save_report_to_file(user_id, msg["content"])
                    save_report_to_session(db, session_id, msg["content"], file_path)
                    data = json.dumps({"report": msg["content"]}, ensure_ascii=False)
                    yield f"event: debate_complete\ndata: {data}\n\n"
                    break

                elif msg["type"] == "error":
                    data = json.dumps({"message": msg["content"]}, ensure_ascii=False)
                    yield f"event: error\ndata: {data}\n\n"
                    break
        finally:
            db.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


def save_report_to_session(db, session_id: int, report_content: str, file_path: str):
    """将报告内容存入会话记录"""
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if session:
        session.report_content = report_content
        session.report_file_path = file_path
        session.status = 'completed'
        db.commit()


# --- 接口：获取用户历史测评记录 ---
@router.get("/history/{user_id}")
async def get_history(user_id: int, db: Session = Depends(get_db)):
    sessions = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == user_id
    ).order_by(AssessmentSession.started_at.desc()).all()

    result = []
    for s in sessions:
        # 查询该会话的答题记录统计
        records = db.query(AnswerRecord).filter(AnswerRecord.session_id == s.id).all()
        total_score = sum(r.score for r in records)
        anomaly_count = sum(1 for r in records if r.is_anomaly == 1)

        result.append({
            "session_id": s.id,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
            "status": s.status,
            "question_count": len(records),
            "total_score": total_score,
            "anomaly_count": anomaly_count,
            "has_report": s.report_content is not None,
        })

    return {"user_id": user_id, "sessions": result}


# --- 接口：获取某次测评的详细报告 ---
@router.get("/report/{session_id}")
async def get_report(session_id: int, db: Session = Depends(get_db)):
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    records = db.query(AnswerRecord).filter(AnswerRecord.session_id == session_id).all()
    answers = []
    for r in records:
        question = db.query(Question).filter(Question.exam_no == r.exam_no).first()
        answers.append({
            "exam_no": r.exam_no,
            "question": question.content if question else "未知",
            "selected_option": r.selected_option,
            "score": r.score,
            "time_spent": r.time_spent,
            "is_anomaly": r.is_anomaly,
            "ai_follow_up": r.ai_follow_up,
            "user_explanation": r.user_explanation,
        })

    return {
        "session_id": session.id,
        "user_id": session.user_id,
        "status": session.status,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "finished_at": session.finished_at.isoformat() if session.finished_at else None,
        "report": session.report_content,
        "answers": answers,
    }