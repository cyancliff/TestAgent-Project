import os
from pageindex import PageIndex

# 1. 填入你的 DeepSeek API Key
os.environ["DEEPSEEK_API_KEY"] = os.environ.get("DEEPSEEK_API_KEY")

# 2. 读取你刚刚处理好的完美 Markdown 文件
# 请确保文件名和路径与你实际保存的一致
with open("ATMR_clean.md", "r", encoding="utf-8") as f:
    document_text = f.read()

# 3. 初始化 PageIndex 引擎，指定使用 DeepSeek
print("正在初始化 PageIndex 引擎...")
agentic_index = PageIndex(model="deepseek/deepseek-chat")

# 4. 构建索引树 (注意：这一步大模型会通读全文并构建结构，需要消耗一定的 Token 和时间，请耐心等待几分钟)
print("DeepSeek 正在阅读文档并构建目录树，请稍候...")
agentic_index.build_index(document_text)
print("🎉 目录树构建完成！大脑已准备就绪。")

# ----------------- 分割线：下面是提问部分 -----------------

# 5. 发起测试提问
# 你可以把这里换成任何你想测试的问题
query = "如果一个孩子是 AR 特质，他通常会有哪些天赋优势？在性格上又有什么潜在的弱势？"

print(f"\n正在思考问题：{query}\n")
# 系统会根据目录树去寻找答案
response = agentic_index.query(query)

print("🤖 AI 分析师的回答：\n")
print(response)