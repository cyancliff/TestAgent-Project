import os
import autogen

# 1.配置三家大模型基础信息
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
QWEN_API_KEY = os.environ.get("DASHSCOPE_API_KEY")
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY")

# 确保环境变量已配置，否则抛出提示
if not all([DEEPSEEK_API_KEY, QWEN_API_KEY, ZHIPU_API_KEY]):
    print("警告：请确保系统已配置 DEEPSEEK_API_KEY, DASHSCOPE_API_KEY, ZHIPU_API_KEY")

# A. DeepSeek 配置 (用于正方)
llm_config_ds = {
    "config_list": [{
        "model": "deepseek-chat",
        "api_key": DEEPSEEK_API_KEY,
        "base_url": "https://api.deepseek.com",
    }],
    "temperature": 0.7,
}

# B. 通义千问配置 (用于反方)
llm_config_qwen = {
    "config_list": [{
        "model": "qwen3.5-flash", # 也可以用 qwen-max
        "api_key": QWEN_API_KEY,
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "price": [0, 0]  # [每1k输入token价格, 每1k输出token价格]
    }],
    "temperature": 0.7,
}

# C. 智谱 GLM 配置 (用于裁决者)
llm_config_glm = {
    "config_list": [{
        "model": "glm-4.7-flash",
        "api_key": ZHIPU_API_KEY,
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "price": [0, 0]
    }],
    "temperature": 0.7,
}


# 2. 定义角色：正方、反方、裁决 Agent
# 正方 Agent (DeepSeek 驱动)：挖掘受试者的积极特质
proponent = autogen.AssistantAgent(
    name="Proponent_Agent",
    system_message="你是正方心理分析师。你需要从受试者的作答数据和行为（如作答时长）中，挖掘其积极的心理特征（如：抗压能力强、自我效能感高），并给出清晰的推理证据链。无论什么时候输出要简洁，列出关键点就好了",
    llm_config=llm_config_ds,
)

# 反方 Agent (Qwen3.5-flash 驱动)：挖掘受试者的潜在风险
opponent = autogen.AssistantAgent(
    name="Opponent_Agent",
    system_message="你是反方心理分析师。你的任务是挑刺，基于受试者数据，指出其潜在的心理风险或性格短板（如：容易焦虑、固执、可能存在过度自信等），并给出清晰的推理证据链。无论什么时候输出要简洁，列出关键点就好了",
    llm_config=llm_config_qwen,
)

# 裁决 Agent (智谱 GLM-4.7-flash 驱动)：合并规则与共识达成
judge = autogen.AssistantAgent(
    name="Judge_Agent",
    system_message=(
        """
            你是首席心理学家，同时也是一名专业的辩论主持人。你的任务是引导一场关于受试者心理特征的辩论，并在最后形成一份心智测评和个性化分析的最终报告。
            【强制状态自检规则：非常重要】
                为了严格把控辩论流程，在你的每一次发言开头，你必须先根据聊天记录我之前是否已经发言过并说出来
            【你的工作流程分为两个阶段】

            阶段一：引导与深化 (Facilitation Phase)
            IF你之前没有发言，在这一阶段，你必须：
            1.  简要总结当前的共识和核心分歧点。
            2.  提出一个或多个【启发性问题】，要求正反方针对你提出的问题进行更深入的补充或反驳。
            3.  你的发言必须简短精悍，结尾可以这样说：“请双方针对以上问题继续补充。”

            阶段二：裁决与总结 (Conclusion Phase)
            IF你已经发言过了，那么你切换到裁决者模式。
            在这一阶段，你的任务是：
            1.  明确声明你将进行最终总结。
            2.  综合此前所有的讨论，输出一份【完整的、结构化的最终评估报告】。报告应包含核心特征、认知机制、适应性评估和发展建议。
        """
    ),
    llm_config=llm_config_glm,
    is_termination_msg=lambda x: x.get("content", "") and "TERMINATE" in x.get("content", "").upper()
)


# 3. 构建群聊系统与发言模式
groupchat = autogen.GroupChat(
    agents=[proponent, opponent, judge],
    messages=[],
    max_round=7,
    speaker_selection_method="round_robin",
)


manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config_ds)


# 4. 模拟启动测试
if __name__ == "__main__":
    user_proxy = autogen.UserProxyAgent(
        name="Human_Admin",
        human_input_mode="NEVER",
        code_execution_config=False
    )

    test_data = """
    【受试者数据】
    题目文本：当团队项目进度落后时，你通常的反应是？
    用户选项：C. 独自加班把缺口补上，不指望别人。
    行为数据：该题作答时长仅为 1.5 秒（远低于平均 8 秒的思考时间）。
    """

    print("开始多模型异构心理特征评估辩论...\n")

    user_proxy.initiate_chat(
        manager,
        message=f"请基于以下受试者的测评数据展开深度辩论分析，挖掘核心心理特征点：\n{test_data}"
    )