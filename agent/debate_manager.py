import os
import queue
import threading
import time
import autogen


def run_debate_streaming(user_data_context: str, message_queue: queue.Queue):
    """
    与 run_debate 相同的辩论逻辑，但通过 message_queue 实时推送每条消息。
    消息格式: {"agent": str, "content": str, "type": "message"|"done"|"error"}
    """
    try:
        config_list_deepseek = [{
            "model": "deepseek-chat",
            "api_key": os.environ.get("DEEPSEEK_API_KEY"),
            "base_url": "https://api.deepseek.com/v1"
        }]
        config_list_qwen = [{
            "model": "qwen-plus",
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
            agents=[human_admin, proponent, opponent, judge],
            messages=[],
            max_round=12,
            speaker_selection_method="auto"
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


def run_debate(user_data_context: str) -> str:
    """
    接收用户的全量答题数据，通过 human_admin 投入群聊，触发多智能体辩论。
    返回由 Judge 生成的最终心理画像报告。
    """

    # 1. 异构大模型配置 (请确保环境变量中已配置对应 API_KEY)
    config_list_deepseek = [{
        "model": "deepseek-chat",
        "api_key": os.environ.get("DEEPSEEK_API_KEY"),
        "base_url": "https://api.deepseek.com/v1"
    }]
    config_list_qwen = [{
        "model": "qwen-plus",  # 或 qwen-max
        "api_key": os.environ.get("DASHSCOPE_API_KEY"),
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
    }]
    config_list_zhipu = [{
        "model": "glm-4",
        "api_key": os.environ.get("ZHIPU_API_KEY"),
        "base_url": "https://open.bigmodel.cn/api/paas/v4"
    }]

    # 2. 定义 Agents
    # 【核心改动】：创建 human_admin，由它负责“喂”数据
    human_admin = autogen.UserProxyAgent(
        name="Human_Admin",
        system_message="你是测评系统管理员，负责将收集到的用户作答数据原封不动地提交给专家组进行评审，你不参与辩论。",
        code_execution_config=False,
        human_input_mode="NEVER"  # 纯自动化，不需要终端人为输入
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

    # 3. 构建群聊
    groupchat = autogen.GroupChat(
        agents=[human_admin, proponent, opponent, judge],
        messages=[],
        max_round=12,
        speaker_selection_method="auto"  # 让模型自行判断发言顺序
    )
    manager = autogen.GroupChatManager(
        groupchat=groupchat,
        llm_config={"config_list": config_list_zhipu}  # 由裁判模型担任大管家
    )

    # 4. 组装发给专家组的数据，由 human_admin 发起对话
    initial_message = f"""各位专家好，我是系统管理员。以下是某位用户在 ATMR 心理测评中的完整作答记录。
包含了每道题的选项、作答耗时(毫秒)、是否触发 AI 异常拦截，以及拦截后用户的解释说明。
请你们立即根据这些数据展开深度辩论，并最终由 Judge_GLM4 输出评估报告。

【用户测评数据面板】：
{user_data_context}
"""
    print("🚀 正在唤醒多智能体慢车道，启动深度辩论...")
    human_admin.initiate_chat(manager, message=initial_message)

    # 5. 从群聊历史中提取最后的综合报告
    final_report = "生成报告失败，请检查模型 API 状态。"
    for msg in reversed(groupchat.messages):
        if msg.get("name") == "Judge_GLM4" and "TERMINATE" in msg.get("content", ""):
            final_report = msg["content"].replace("TERMINATE", "").strip()
            break

    return final_report