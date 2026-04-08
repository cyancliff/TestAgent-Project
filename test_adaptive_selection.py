#!/usr/bin/env python
"""
智能选题系统完整测试脚本
测试自适应选题API的完整流程
"""
import requests
import json
import time
import sys

API_BASE = "http://127.0.0.1:8000/api/v1"

def test_adaptive_system():
    """测试智能选题系统的完整流程"""
    print("=" * 60)
    print("[搜索] 智能选题系统测试")
    print("=" * 60)

    try:
        # 1. 注册用户
        print("\n1. 📝 注册测试用户...")
        try:
            reg_resp = requests.post(f"{API_BASE}/auth/register", json={
                "username": "adaptive_test_user",
                "password": "test123456"
            }, timeout=10)
            reg_resp.raise_for_status()
            user_data = reg_resp.json()
            user_id = user_data["user_id"]
            print(f"   ✅ 用户注册成功")
            print(f"   📋 用户ID: {user_id}, 用户名: {user_data['username']}")
        except requests.exceptions.RequestException as e:
            print(f"   ❌ 用户注册失败: {e}")
            print("   💡 可能用户已存在，尝试登录...")
            # 尝试登录
            login_resp = requests.post(f"{API_BASE}/auth/login", json={
                "username": "adaptive_test_user",
                "password": "test123456"
            }, timeout=10)
            login_resp.raise_for_status()
            user_data = login_resp.json()
            user_id = user_data["user_id"]
            print(f"   ✅ 用户登录成功")
            print(f"   📋 用户ID: {user_id}")

        # 2. 创建会话
        print("\n2. 🚀 创建测评会话...")
        try:
            session_resp = requests.post(f"{API_BASE}/assessment/start-session", json={
                "user_id": user_id
            }, timeout=10)
            session_resp.raise_for_status()
            session_data = session_resp.json()
            session_id = session_data["session_id"]
            print(f"   ✅ 会话创建成功")
            print(f"   📋 会话ID: {session_id}")
        except requests.exceptions.RequestException as e:
            print(f"   ❌ 会话创建失败: {e}")
            return False

        # 3. 测试自适应选题
        print("\n3. 🧠 测试自适应选题算法...")
        print("   📊 将进行10轮自适应选题测试")

        modules = ['A', 'T', 'M', 'R']
        answered_questions = []

        for i in range(10):  # 测试10题
            print(f"\n   🔄 第{i+1}/10题:")

            # 确定模块（前2题无模块，后续按A/T/M/R循环）
            module = None
            if i >= 2:
                module = modules[(i - 2) % 4]
                print(f"      模块: {module}")

            # 获取自适应题目
            try:
                question_resp = requests.post(f"{API_BASE}/assessment/adaptive-question", json={
                    "session_id": session_id,
                    "user_id": user_id,
                    "module": module
                }, timeout=10)
                question_resp.raise_for_status()
                question_data = question_resp.json()

                exam_no = question_data['examNo']
                is_adaptive = question_data.get('is_adaptive', False)
                remaining = question_data.get('remaining', 'N/A')

                print(f"      📝 题目编号: {exam_no}")
                print(f"      🎯 自适应模式: {is_adaptive}")
                print(f"      📈 剩余题数: {remaining}")

                # 检查题目统计信息
                if 'question_stats' in question_data:
                    stats = question_data['question_stats']
                    print(f"      📊 难度: {stats.get('difficulty', 'N/A'):.2f}")
                    print(f"      📊 区分度: {stats.get('discrimination', 'N/A'):.2f}")
                    print(f"      🔢 特征向量: {stats.get('has_feature_vector', False)}")

                # 记录已答题目
                answered_questions.append(exam_no)

                # 模拟答题（选择第一个选项）
                if question_data.get('options') and len(question_data['options']) > 0:
                    selected_option = question_data['options'][0]

                    # 模拟作答时间：逐渐减少，模拟熟悉度提高
                    time_spent = max(3.0, 10.0 - i * 0.5)  # 3-10秒之间

                    submit_resp = requests.post(f"{API_BASE}/assessment/submit", json={
                        "session_id": session_id,
                        "user_id": user_id,
                        "exam_no": exam_no,
                        "selected_option": selected_option,
                        "time_spent": time_spent
                    }, timeout=10)
                    submit_resp.raise_for_status()
                    submit_data = submit_resp.json()

                    print(f"      ✅ 答题成功")
                    print(f"      ⏱️ 模拟耗时: {time_spent:.1f}秒")
                    print(f"      📈 得分: {submit_data.get('score', 'N/A')}")
                    print(f"      🚨 异常检测: {submit_data.get('status', 'N/A')}")

                    if submit_data.get('follow_up_question'):
                        print(f"      💬 AI追问: {submit_data.get('follow_up_question')[:50]}...")
                else:
                    print(f"      ⚠️ 题目无选项，跳过答题")

                time.sleep(0.3)  # 短暂延迟，避免请求过快

            except requests.exceptions.RequestException as e:
                print(f"      ❌ 请求失败: {e}")
                # 尝试回退到顺序模式
                print(f"      🔄 尝试回退到顺序选题...")
                try:
                    # 使用顺序选题API
                    seq_resp = requests.get(f"{API_BASE}/assessment/question/{i}", timeout=10)
                    if seq_resp.status_code == 200:
                        seq_data = seq_resp.json()
                        print(f"      📝 顺序选题成功: {seq_data.get('examNo', '未知')}")
                    else:
                        print(f"      ❌ 顺序选题也失败")
                except:
                    print(f"      ❌ 所有选题模式均失败")
                continue

        # 4. 分析测试结果
        print("\n" + "=" * 60)
        print("📈 测试结果分析")
        print("=" * 60)

        print(f"\n📊 答题统计:")
        print(f"   总答题数: {len(answered_questions)}")
        print(f"   题目去重数: {len(set(answered_questions))}")

        if len(answered_questions) > 0:
            print(f"\n📋 答题记录:")
            for j, q in enumerate(answered_questions[:5]):  # 只显示前5个
                print(f"   {j+1}. {q}")
            if len(answered_questions) > 5:
                print(f"   ... 还有{len(answered_questions)-5}题")

        print(f"\n✅ 智能选题系统测试完成!")
        print(f"💡 建议:")
        print(f"   1. 检查后端日志，查看自适应算法决策过程")
        print(f"   2. 验证题目难度是否随用户能力变化")
        print(f"   3. 测试容错机制（如关闭后端查看前端回退）")

        return True

    except Exception as e:
        print(f"\n[错误] 测试过程中发生未预期错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_api_status():
    """检查API服务状态"""
    print("\n[搜索] 检查API服务状态...")
    try:
        health_resp = requests.get("http://127.0.0.1:8000/", timeout=5)
        if health_resp.status_code == 200:
            print("   [成功] 后端服务正常运行")
            return True
        else:
            print(f"   [错误] 后端服务异常: HTTP {health_resp.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   [错误] 无法连接到后端服务 (127.0.0.1:8000)")
        print("   [提示] 请启动后端服务: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        return False
    except Exception as e:
        print(f"   [错误] 检查API状态时出错: {e}")
        return False

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("[实验] TestAgent 智能选题系统集成测试")
    print("=" * 60)

    # 检查依赖
    print("\n[工具] 检查环境依赖...")
    try:
        import requests
        print("   [成功] requests 已安装")
    except ImportError:
        print("   ❌ requests 未安装，请运行: pip install requests")
        return 1

    # 检查API服务状态
    if not check_api_status():
        print("\n⚠️  无法继续测试，请先启动后端服务")
        print("   启动命令: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        return 1

    # 运行测试
    success = test_adaptive_system()

    if success:
        print("\n🎉 所有测试完成！")
        print("📋 下一步:")
        print("   1. 修改前端 Assessment.vue 组件，集成自适应选题")
        print("   2. 运行前端开发服务器: cd frontend && npm run dev")
        print("   3. 进行完整的前后端集成测试")
        return 0
    else:
        print("\n⚠️  测试未完全通过，请检查上述错误")
        return 1

if __name__ == "__main__":
    sys.exit(main())