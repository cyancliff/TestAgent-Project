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

from app.models.question import SessionLocal, Question, AnswerRecord
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
class AnswerSubmitRequest(BaseModel):
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
    user_id: int
    exam_no: str
    text: str


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
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    """
    前端答完10题后调用此接口。
    返回成功响应，提示前端连接流式端点观看实时辩论。
    不再启动后台辩论，避免重复。
    """
    # 不再启动后台任务，辩论将通过 /finish-stream 端点进行
    return {
        "status": "success",
        "message": "测评已完成！请连接 /finish-stream 端点观看专家评审团的实时辩论并获取最终报告。"
    }


@router.get("/finish-stream")
async def finish_assessment_stream(user_id: str):
    """
    SSE 端点：实时推送多智能体辩论过程到前端。
    前端用 EventSource 连接此接口。
    """
    db = SessionLocal()

    try:
        prompt = build_debate_context(user_id, db)
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
                                    save_report_to_file(user_id, msg["content"])
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
                    # 保存报告到文件
                    save_report_to_file(user_id, msg["content"])
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