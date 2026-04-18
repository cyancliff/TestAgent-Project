import asyncio
import os
import queue
import threading
import time

import autogen

# 评分标准（注入到辩论专家 prompt 中）
SCORING_STANDARD = """
【评分标准参考】
测评采用 1-5 分李克特量表，4大维度各10题，单项满分50分。
等级划分：偏低（10-23分，潜伏特质）/ 中等（24-37分，情境特质）/ 偏高（38-50分，显性主导特质）。
前两题存在加权调节机制（+2分）。对外展示以50分为封顶。
请在分析中结合用户的维度得分等级进行解读。
"""


def _retrieve_rag_evidence(user_data_context: str) -> str:
    """同步包装：从 ATMR 知识库中检索与用户数据相关的证据。"""
    try:
        from app.services.rag_service import retrieve_evidence_for_debate

        # 从用户数据中提取特质关键词
        traits_keywords = []
        for trait in ["A", "T", "M", "R"]:
            if f'"{trait}"' in user_data_context or f"模块 {trait}" in user_data_context:
                traits_keywords.append(trait)
        user_traits = ", ".join(traits_keywords) if traits_keywords else "ATMR"

        # 同步执行异步函数
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                evidence = pool.submit(asyncio.run, retrieve_evidence_for_debate(user_traits)).result(timeout=30)
        else:
            evidence = asyncio.run(retrieve_evidence_for_debate(user_traits))

        if evidence:
            print(f"[辩论服务] RAG 检索到 {len(evidence)} 字符的证据")
        return evidence or ""
    except Exception as e:
        print(f"[辩论服务] RAG 检索失败（不影响辩论）: {e}")
        return ""


def run_debate_streaming(user_data_context: str, message_queue: queue.Queue):
    """
    多智能体辩论逻辑，通过 message_queue 实时推送每条消息。
    human_admin 只在开头发言一次，之后由正反方和裁决者轮流辩论。
    消息格式: {"agent": str, "content": str, "type": "message"|"done"|"error"}
    """
    try:
        print(f"[辩论服务] 开始辩论，用户数据长度: {len(user_data_context)}")

        # RAG 检索：获取 ATMR 理论知识作为辩论证据
        rag_evidence = _retrieve_rag_evidence(user_data_context)
        evidence_block = ""
        if rag_evidence:
            evidence_block = f"""

【ATMR 理论知识库参考】
以下是从 ATMR 心理学知识库中检索到的相关理论依据，请在辩论中引用这些专业知识来支撑你的论点：
{rag_evidence}
"""

        config_list_deepseek = [
            {
                "model": "deepseek-chat",
                "api_key": os.environ.get("DEEPSEEK_API_KEY"),
                "base_url": "https://api.deepseek.com/v1",
            }
        ]
        config_list_qwen = [
            {
                "model": "qwen3.5-flash",
                "api_key": os.environ.get("DASHSCOPE_API_KEY"),
                "base_url": "https://coding.dashscope.aliyuncs.com/v1",
            }
        ]
        config_list_zhipu = [
            {
                "model": "glm-4.6-flash",
                "api_key": os.environ.get("ZHIPU_API_KEY"),
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
            }
        ]

        print(
            f"[辩论服务] API密钥检查 - DeepSeek: {'已设置' if os.environ.get('DEEPSEEK_API_KEY') else '未设置'}, "
            f"DashScope: {'已设置' if os.environ.get('DASHSCOPE_API_KEY') else '未设置'}, "
            f"Zhipu: {'已设置' if os.environ.get('ZHIPU_API_KEY') else '未设置'}"
        )

        human_admin = autogen.UserProxyAgent(
            name="Human_Admin",
            system_message="你是测评系统管理员，负责将收集到的用户作答数据原封不动地提交给专家组进行评审，你不参与辩论。",
            code_execution_config=False,
            human_input_mode="NEVER",
        )
        proponent = autogen.AssistantAgent(
            name="Proponent_DeepSeek",
            system_message=f"你是正方心理学专家。请重点从积极的角度分析用户的作答数据（尤其是克服异常阻碍的追问回答），挖掘其内在潜力、自我效能感与抗压能力。{evidence_block}{SCORING_STANDARD}",
            llm_config={"config_list": config_list_deepseek},
        )
        opponent = autogen.AssistantAgent(
            name="Opponent_Qwen",
            system_message=f"你是反方风控专家。请用批判性的眼光审查用户的作答耗时和异常标记，挖掘其潜在的性格弱点、僵化归因或过度自信风险，并对正方的乐观估计进行反驳。{evidence_block}{SCORING_STANDARD}",
            llm_config={"config_list": config_list_qwen},
        )
        judge = autogen.AssistantAgent(
            name="Judge_GLM4.7",
            system_message=f"""你是主裁决官（高级心理学教授）。负责控场并最终输出ATMR综合评估报告。{evidence_block}{SCORING_STANDARD}
【强制思维链规则】：你每次发言的开头必须包含 `【内部记录：这是我第X次发言】`。
- 第1次发言：简单总结正反方初步观点，并提出一个尖锐的问题引导他们深入。
- 第2次发言：综合所有数据和辩论，直接输出一份极具专业度的结构化心理画像报告（包含认知、情感、行为、潜力四个维度）。
  **禁止要求**：不要在报告开头写任何关于"感谢正反方专家""辩论总结""各位专家"之类的开场白，不要提及"正方/反方/两位专家"。直接从报告标题开始输出。报告中必须明确标注各维度的等级（偏低/中等/偏高），并结合等级特征进行分析。必须在报告正文的最后一行输出 `TERMINATE`。""",
            llm_config={"config_list": config_list_zhipu},
        )

        print("[辩论服务] 代理创建完成")

        groupchat = autogen.GroupChat(
            agents=[proponent, opponent, judge],  # human_admin 不参与轮次，只开头发言
            messages=[],
            max_round=7,
            speaker_selection_method="round_robin",
        )
        manager = autogen.GroupChatManager(groupchat=groupchat, llm_config={"config_list": config_list_zhipu})

        initial_message = f"""各位专家好，我是系统管理员。以下是某位用户在 ATMR 心理测评中的完整作答记录。
包含了每道题的选项、作答耗时(毫秒)、是否触发 AI 异常拦截，以及拦截后用户的解释说明。
请你们立即根据这些数据展开深度辩论，并最终由 Judge_GLM4.7 输出评估报告。

{SCORING_STANDARD}

【用户测评数据面板】：
{user_data_context}
"""

        # 在子线程中运行阻塞的 initiate_chat
        print("[辩论服务] 启动聊天线程...")
        chat_thread = threading.Thread(
            target=human_admin.initiate_chat, args=(manager,), kwargs={"message": initial_message}, daemon=True
        )
        chat_thread.start()
        print("[辩论服务] 聊天线程已启动")

        # 轮询 groupchat.messages，实时推送新消息
        seen = 0
        print("[辩论服务] 开始轮询消息...")
        while chat_thread.is_alive() or seen < len(groupchat.messages):
            current_len = len(groupchat.messages)
            if seen < current_len:
                print(f"[辩论服务] 发现 {current_len - seen} 条新消息")
            while seen < current_len:
                msg = groupchat.messages[seen]
                print(f"[辩论服务] 推送消息: {msg.get('name', 'Unknown')}, 长度: {len(msg.get('content', ''))}")
                message_queue.put(
                    {"agent": msg.get("name", "Unknown"), "content": msg.get("content", ""), "type": "message"}
                )
                seen += 1
            if chat_thread.is_alive():
                time.sleep(0.5)
            else:
                print("[辩论服务] 聊天线程已结束")

        print(f"[辩论服务] 轮询结束，共处理 {seen} 条消息")

        # 提取最终报告
        final_report = "生成报告失败，请检查模型 API 状态。"
        for msg in reversed(groupchat.messages):
            if msg.get("name") == "Judge_GLM4.7" and "TERMINATE" in msg.get("content", ""):
                final_report = msg["content"].replace("TERMINATE", "").strip()
                break

        print(f"[辩论服务] 最终报告长度: {len(final_report)}")
        message_queue.put({"agent": "system", "content": final_report, "type": "done"})
        print("[辩论服务] 完成消息已放入队列")

    except Exception as e:
        print(f"[辩论服务] 发生异常: {e}")
        import traceback

        traceback.print_exc()
        message_queue.put({"agent": "system", "content": str(e), "type": "error"})
