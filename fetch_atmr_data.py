import requests
import json
import time


def fetch_all_questions():
    url = "http://wx.drzh-atmr.cn/web/exam/dndx/major/list"
    headers = {"Content-Type": "application/json"}

    all_questions = []
    test_uuid = ""
    total_count = 102  # 我们刚刚获取到的总题数

    print("🚀 开始全量抓取 ATMR 题库，共计 102 题...")

    for i in range(total_count):
        # 构造请求体
        payload = {"index": i}
        # 如果已经拿到了 testUuid (即从第2题开始)，必须带上它
        if test_uuid:
            payload["testUuid"] = test_uuid

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            body = data.get("body", {})

            # 第一题请求成功后，把 testUuid 保存下来供后面使用
            if i == 0:
                test_uuid = body.get("testUuid", "")

            questions = body.get("examInfoDtoList", [])
            if questions:
                q_info = questions[0]
                all_questions.append(q_info)
                # 打印进度条
                print(f"✅ 成功抓取第 {i + 1}/{total_count} 题: [{q_info.get('examNo')}] {q_info.get('exam')}")
            else:
                print(f"⚠️ 第 {i + 1} 题未返回题目数据！")

            # 礼貌性延迟，保护导师的服务器
            time.sleep(0.5)

        except Exception as e:
            print(f"❌ 抓取第 {i + 1} 题时发生网络错误: {e}")
            break

    # 将所有题目保存到本地的 JSON 文件中
    with open("atmr_full_questions.json", "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=4)

    print(f"\n🎉 抓取彻底完成！共获得 {len(all_questions)} 道题目。")
    print("数据已安全保存在当前目录的 atmr_full_questions.json 文件中。")


if __name__ == "__main__":
    fetch_all_questions()