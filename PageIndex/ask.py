import json
import os

from openai import OpenAI

# ================= 配置区 =================
# 1. 填入你的 DeepSeek 真实 API Key
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# 2. 初始化标准的客户端，指向 DeepSeek 官方服务器
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# 3. 指定我们之前成功生成的两个文件
JSON_PATH = "./results/MinerU_markdown_ATMR_Longtext_structure.json"
MD_PATH = "MinerU_markdown_ATMR_Longtext.md"
# ==========================================

print("正在加载本地目录树和正文资料库...")
with open(JSON_PATH, encoding="utf-8") as f:
    doc_structure = f.read()

with open(MD_PATH, encoding="utf-8") as f:
    md_lines = f.readlines()


# --- 定义两个给大模型的“超能力”工具 ---
def get_document_structure():
    """工具1：获取文档的目录树"""
    return doc_structure


def get_page_content(start_line: int, end_line: int):
    """工具2：根据行号获取具体的原文内容"""
    start_idx = max(0, start_line - 1)
    # 稍微多取50行，防止段落被生硬截断
    end_idx = min(len(md_lines), end_line + 50)
    return "".join(md_lines[start_idx:end_idx])


# 告诉大模型这两个工具怎么用
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_document_structure",
            "description": "获取文档的目录树结构。当你需要寻找某类特质（如AR特质）在文档的哪个章节时，优先调用此工具查看 line_num。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_page_content",
            "description": "根据找到的章节起始和结束行号，提取正文内容进行阅读。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_line": {"type": "integer", "description": "起始行号"},
                    "end_line": {"type": "integer", "description": "结束行号"},
                },
                "required": ["start_line", "end_line"],
            },
        },
    },
]

# --- 发起 RAG 问答主循环 ---
query = "如果一个孩子是 AR 特质，他通常会有哪些天赋优势？在性格上又有什么潜在的弱势？"

messages = [
    {
        "role": "system",
        "content": "你是一个基于真实文档回答问题的专家。执行步骤：1.先调用工具查看目录，找到对应章节行号；2.调用工具提取正文；3.基于正文回答问题。禁止自己编造。",
    },
    {"role": "user", "content": query},
]

print(f"\n🙋‍♂️ 你的问题: {query}")
print("🤖 AI 探员开始工作...\n")

# 允许 AI 最多进行 3 轮推理（看目录 -> 翻正文 -> 回答）
for i in range(10):
    response = client.chat.completions.create(model="deepseek-chat", messages=messages, tools=tools)

    msg = response.choices[0].message
    messages.append(msg)

    # 如果 AI 决定调用工具
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            args = json.loads(tool_call.function.arguments)
            if tool_call.function.name == "get_document_structure":
                print("-> 🕵️‍♂️ AI 动作：正在查阅《目录树》寻找对应章节行号...")
                result = get_document_structure()
            elif tool_call.function.name == "get_page_content":
                print(f"-> 📖 AI 动作：正在翻阅正文 (第 {args['start_line']} 行 至 {args['end_line']} 行)...")
                result = get_page_content(args["start_line"], args["end_line"])

            # 将工具得到的内容汇报给 AI
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
    else:
        # 如果没有调用工具，说明资料找齐了，AI 输出了最终答案！
        print("\n================= 🌟 AI 分析师的最终回答 =================\n")
        print(msg.content)
        break
