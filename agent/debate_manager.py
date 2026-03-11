import os
import autogen

#配置 DeepSeek 大模型基础信息

API_KEY = os.environ.get("DEEPSEEK_API_KEY")

config_list = [
    {
        "model": "deepseek-chat",  # 调用 DeepSeek-V3 的标准模型名
        "api_key": API_KEY,
        "base_url": "https://api.deepseek.com",
    }
]

# 统一的大模型配置字典
llm_config = {
    "config_list": config_list,
    "temperature": 0.7,  # 稍微调高一点温度，让辩论更加丰富多样
}

# 2. 定义角色：正方、反方、裁决 Agent

# 正方 Agent：挖掘受试者的积极特质
proponent = autogen.AssistantAgent(
    name="Proponent_Agent",
    system_message="你是正方心理分析师。你需要从受试者的作答数据和行为（如作答时长）中，挖掘其积极的心理特征（如：抗压能力强、自我效能感高），并给出清晰的推理证据链。无论什么时候输出要简洁，列出关键点就好了",
    llm_config=llm_config,
)

# 反方 Agent：挖掘受试者的潜在风险
opponent = autogen.AssistantAgent(
    name="Opponent_Agent",
    system_message="你是反方心理分析师。你的任务是挑刺，基于受试者数据，指出其潜在的心理风险或性格短板（如：容易焦虑、固执、可能存在过度自信等），并给出清晰的推理证据链。无论什么时候输出要简洁，列出关键点就好了",
    llm_config=llm_config,
)

# 裁决 Agent：合并规则与共识达成
# 裁决 Agent：合并规则与共识达成
judge = autogen.AssistantAgent(
    name="Judge_Agent",
    system_message=(
        """"
            你是首席心理学家，同时也是一名专业的辩论主持人。你的任务是引导一场关于受试者心理特征的辩论，并在最后形成一份心智测评和个性化分析的最终报告。

            【你的工作流程分为两个阶段】
            
            阶段一：引导与深化 (Facilitation Phase)
            你第一二次发言的时候，你发现正反方的观点还停留在表面，或者证据不够充分，你的任务【不是】给出最终结论。
            在这一阶段，你必须：
            1.  简要总结当前的共识和核心分歧点。
            2.  提出一个或多个【启发性问题】，要求正反方针对你提出的问题进行更深入的补充或反驳。
            3.  你的发言必须简短精悍，结尾可以这样说：“请双方针对以上问题继续补充。”
            
            阶段二：裁决与总结 (Conclusion Phase)
            当你第三次发言的时候，你切换到裁决者模式
            在这一阶段，你的任务是：
            1.  明确声明你将进行最终总结。
            2.  综合此前所有的讨论，输出一份【完整的、结构化的最终评估报告】。报告应包含核心特征、认知机制、适应性评估和发展建议。
            
        """
    ),
    llm_config=llm_config,
    # 修改判定逻辑：只有当内容中包含 TERMINATE 这个词时，才返回 True
    is_termination_msg=lambda x: x.get("content", "") and "TERMINATE" in x.get("content", "").upper()
)


# ==========================================
# 3. 构建群聊系统与发言模式
# ==========================================

# 将三个 Agent 放入一个聊天室，并设定固定轮次的对话限制（例如 4 轮）
groupchat = autogen.GroupChat(
    agents=[proponent, opponent, judge],
    messages=[],
    max_round=10,
    speaker_selection_method="round_robin",  # 采用轮询发言模式，确保每个人依次发言
)

# 创建群聊管理员
manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config)

# ==========================================
# 4. 模拟启动测试
# ==========================================
if __name__ == "__main__":
    # 创建一个代表我们人类（开发者）的 UserProxy
    user_proxy = autogen.UserProxyAgent(
        name="Human_Admin",
        human_input_mode="NEVER",  # 纯自动辩论，不需要人类中途打字插嘴
        code_execution_config=False  # 我们不需要它写代码执行，只需要文本推理
    )

    # 模拟一条来自 ATMR 测试系统抓取到的复杂作答数据
    test_data = """
    【受试者数据】
    题目文本：当团队项目进度落后时，你通常的反应是？
    用户选项：C. 独自加班把缺口补上，不指望别人。
    行为数据：该题作答时长仅为 1.5 秒（远低于平均 8 秒的思考时间）。
    """

    print("开始多角色心理特征评估辩论...\n")

    # 向系统发送第一条消息，引发辩论
    user_proxy.initiate_chat(
        manager,
        message=f"请基于以下受试者的测评数据展开深度辩论分析，挖掘核心心理特征点：\n{test_data}"
    )