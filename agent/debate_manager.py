import os
import queue
import threading
import time
import autogen


def run_debate_streaming(user_data_context: str, message_queue: queue.Queue):
    """
    多智能体辩论逻辑，通过 message_queue 实时推送每条消息。
    human_admin 只在开头发言一次，之后由正反方和裁决者轮流辩论。
    消息格式: {"agent": str, "content": str, "type": "message"|"done"|"error"}
    """
    try:
        config_list_deepseek = [{
            "model": "deepseek-chat",
            "api_key": os.environ.get("DEEPSEEK_API_KEY"),
            "base_url": "https://api.deepseek.com/v1"
        }]
        config_list_qwen = [{
            "model": "qwen3.5-flash",
            "api_key": os.environ.get("DASHSCOPE_API_KEY"),
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
        }]
        config_list_zhipu = [{
            "model": "glm-4",
            "api_key": os.environ.get("ZHIPU_API_KEY"),
            "base_url": "https://open.bigmodel.cn/api/paas/v4"
        }]

        human_admin = autogen.UserProxyAgent(
            name="Human_Admin",
            system_message="你是测评系统管理员，负责将收集到的用户作答数据原封不动地提交给专家组进行评审，你不参与辩论。",
            code_execution_config=False,
            human_input_mode="NEVER"
        )
        proponent = autogen.AssistantAgent(
            name="Proponent_DeepSeek",
            system_message="你是正方心理学专家。请重点从积极的角度分析用户的作答数据（尤其是克服异常阻碍的追问回答），挖掘其内在潜力、自我效能感与抗压能力。",
            llm_config={"config_list": config_list_deepseek}
        )
        opponent = autogen.AssistantAgent(
            name="Opponent_Qwen",
            system_message="你是反方风控专家。请用批判性的眼光审查用户的作答耗时和异常标记，挖掘其潜在的性格弱点、僵化归因或过度自信风险，并对正方的乐观估计进行反驳。",
            llm_config={"config_list": config_list_qwen}
        )
        judge = autogen.AssistantAgent(
            name="Judge_GLM4",
            system_message="""你是主裁决官（高级心理学教授）。负责控场并最终输出ATMR综合评估报告。
【强制思维链规则】：你每次发言的开头必须包含 `【内部记录：这是我第X次发言】`。
- 第1次发言：简单总结正反方初步观点，并提出一个尖锐的问题引导他们深入。
- 第2次发言：综合所有数据和辩论，输出一份极具专业度的结构化心理画像报告（包含认知、情感、行为、潜力四个维度），并必须在报告正文的最后一行输出 `TERMINATE`。""",
            llm_config={"config_list": config_list_zhipu}
        )

        groupchat = autogen.GroupChat(
            agents=[proponent, opponent, judge],  # human_admin 不参与轮次，只开头发言
            messages=[],
            max_round=7,
            speaker_selection_method="round_robin"
        )
        manager = autogen.GroupChatManager(
            groupchat=groupchat,
            llm_config={"config_list": config_list_zhipu}
        )

        initial_message = f"""各位专家好，我是系统管理员。以下是某位用户在 ATMR 心理测评中的完整作答记录。
包含了每道题的选项、作答耗时(毫秒)、是否触发 AI 异常拦截，以及拦截后用户的解释说明。
请你们立即根据这些数据展开深度辩论，并最终由 Judge_GLM4 输出评估报告。

【用户测评数据面板】：
{user_data_context}
"""

        # 在子线程中运行阻塞的 initiate_chat
        chat_thread = threading.Thread(
            target=human_admin.initiate_chat,
            args=(manager,),
            kwargs={"message": initial_message},
            daemon=True
        )
        chat_thread.start()

        # 轮询 groupchat.messages，实时推送新消息
        seen = 0
        while chat_thread.is_alive() or seen < len(groupchat.messages):
            current_len = len(groupchat.messages)
            while seen < current_len:
                msg = groupchat.messages[seen]
                message_queue.put({
                    "agent": msg.get("name", "Unknown"),
                    "content": msg.get("content", ""),
                    "type": "message"
                })
                seen += 1
            if chat_thread.is_alive():
                time.sleep(0.5)

        # 提取最终报告
        final_report = "生成报告失败，请检查模型 API 状态。"
        for msg in reversed(groupchat.messages):
            if msg.get("name") == "Judge_GLM4" and "TERMINATE" in msg.get("content", ""):
                final_report = msg["content"].replace("TERMINATE", "").strip()
                break

        message_queue.put({"agent": "system", "content": final_report, "type": "done"})

    except Exception as e:
        message_queue.put({"agent": "system", "content": str(e), "type": "error"})


