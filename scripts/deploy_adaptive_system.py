#!/usr/bin/env python
"""
智能选题系统完整测试与启动脚本
"""
import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

def print_header(title):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"🚀 {title}")
    print("=" * 60)

def check_environment():
    """检查环境"""
    print_header("环境检查")

    # 检查Python版本
    python_version = sys.version_info
    print(f"Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")

    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("❌ Python版本需要3.8或更高")
        return False

    # 检查关键文件
    required_files = [
        "app/main.py",
        "app/services/question_selection.py",
        "frontend/src/components/Assessment.vue",
    ]

    all_ok = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}: 存在")
        else:
            print(f"❌ {file_path}: 缺失")
            all_ok = False

    return all_ok

def install_dependencies():
    """安装依赖"""
    print_header("安装依赖")

    # 检查requirements文件
    requirements_files = ["requirements_server.txt"]

    for req_file in requirements_files:
        if Path(req_file).exists():
            print(f"📦 安装 {req_file} 中的依赖...")
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--timeout", "300", "--retries", "10", "-r", req_file],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    print(f"✅ {req_file} 依赖安装成功")
                else:
                    print(f"⚠️  {req_file} 依赖安装可能有问题:")
                    print(result.stderr[:500])
            except Exception as e:
                print(f"❌ 安装依赖时出错: {e}")
        else:
            print(f"⚠️  {req_file} 不存在，跳过")

def start_backend():
    """启动后端服务"""
    print_header("启动后端服务")

    # 检查端口是否被占用
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 8000))
        sock.close()

        if result == 0:
            print("⚠️  端口8000已被占用，可能后端已在运行")
            print("   如果后端未运行，请先停止占用8000端口的进程")
            return None
    except:
        pass

    # 启动后端
    print("启动FastAPI后端服务 (uvicorn)...")
    backend_cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

    try:
        # 在Windows上使用CREATE_NEW_CONSOLE创建新窗口
        if sys.platform == "win32":
            backend_proc = subprocess.Popen(backend_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            backend_proc = subprocess.Popen(backend_cmd)

        print("✅ 后端服务启动中...")
        print("   请在新打开的终端窗口中查看后端日志")
        time.sleep(3)  # 给后端一点启动时间

        return backend_proc
    except Exception as e:
        print(f"❌ 启动后端失败: {e}")
        return None

def start_frontend():
    """启动前端服务"""
    print_header("启动前端服务")

    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        print("❌ frontend目录不存在")
        return None

    os.chdir(frontend_dir)

    # 检查node_modules
    if not Path("node_modules").exists():
        print("📦 安装前端依赖...")
        try:
            result = subprocess.run(["npm", "install"], capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ 前端依赖安装成功")
            else:
                print(f"⚠️  前端依赖安装可能有问题:")
                print(result.stderr[:500])
        except Exception as e:
            print(f"❌ 安装前端依赖失败: {e}")
            print("   请确保已安装Node.js和npm")
            os.chdir("..")
            return None

    # 启动前端开发服务器
    print("启动Vue前端开发服务器...")
    frontend_cmd = ["npm", "run", "dev"]

    try:
        # 在Windows上使用CREATE_NEW_CONSOLE创建新窗口
        if sys.platform == "win32":
            frontend_proc = subprocess.Popen(frontend_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            frontend_proc = subprocess.Popen(frontend_cmd)

        print("✅ 前端服务启动中...")
        print("   请在新打开的终端窗口中查看前端日志")
        time.sleep(5)  # 给前端一点启动时间

        os.chdir("..")
        return frontend_proc
    except Exception as e:
        print(f"❌ 启动前端失败: {e}")
        os.chdir("..")
        return None

def open_browser():
    """打开浏览器"""
    print_header("打开浏览器")

    urls = [
        "http://127.0.0.1:5173",  # Vite默认端口
        "http://localhost:5173",
        "http://127.0.0.1:3000",  # 可能的前端端口
        "http://localhost:3000"
    ]

    for url in urls:
        try:
            print(f"尝试打开: {url}")
            webbrowser.open(url)
            print(f"✅ 已尝试在浏览器中打开 {url}")
            print("   如果页面未自动打开，请手动在浏览器中输入上述地址")
            break
        except:
            continue

    print("\n📋 测试账户:")
    print("   用户名: adaptive_test_user")
    print("   密码: test123456")
    print("\n💡 提示: 首次答题使用中等难度题目，后续根据能力自适应选择")

def run_tests():
    """运行测试"""
    print_header("运行系统测试")

    test_script = Path("scripts/test_adaptive_selection.py")
    if not test_script.exists():
        print("❌ 测试脚本不存在")
        return False

    print("运行智能选题系统测试...")
    try:
        result = subprocess.run([sys.executable, str(test_script)],
                              capture_output=True, text=True)

        print(result.stdout)

        if result.returncode == 0:
            print("✅ 测试通过!")
            return True
        else:
            print("❌ 测试失败")
            if result.stderr:
                print("错误输出:")
                print(result.stderr[:1000])
            return False
    except Exception as e:
        print(f"❌ 运行测试时出错: {e}")
        return False

def show_instructions():
    """显示使用说明"""
    print_header("使用说明")

    print("📚 已完成的修改:")
    print("   1. ✅ 创建测试脚本: test_adaptive_selection.py")
    print("   2. ✅ 修改前端组件: frontend/src/components/Assessment.vue")
    print("   3. ✅ 添加调试日志: app/services/question_selection.py")
    print("   4. ✅ 创建监控脚本: monitor_selection.py")

    print("\n🚀 启动步骤:")
    print("   1. 启动后端: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print("   2. 启动前端: cd frontend && npm run dev")
    print("   3. 打开浏览器: http://127.0.0.1:5173")

    print("\n🔧 测试命令:")
    print("   测试API: python test_adaptive_selection.py")
    print("   监控系统: python monitor_selection.py")

    print("\n📊 查看日志:")
    print("   后端日志: 查看uvicorn终端窗口")
    print("   前端日志: 查看Vite终端窗口")
    print("   算法日志: 查看后端日志中的[SELECT], [ABILITY]等标记")

def main():
    """主函数"""
    print_header("TestAgent 智能选题系统部署工具")

    # 检查环境
    if not check_environment():
        print("\n⚠️  环境检查未通过，请修复上述问题")
        show_instructions()
        return 1

    # 显示选项菜单
    print("\n请选择操作:")
    print("1. 完整部署 (安装依赖 + 启动前后端 + 打开浏览器)")
    print("2. 仅启动后端服务")
    print("3. 仅启动前端服务")
    print("4. 运行系统测试")
    print("5. 运行性能监控")
    print("6. 显示使用说明")
    print("7. 退出")

    choice = input("\n请输入选项 (1-7): ").strip()

    if choice == "1":
        # 完整部署
        install_dependencies()
        backend_proc = start_backend()
        frontend_proc = start_frontend()

        if backend_proc or frontend_proc:
            open_browser()
            print("\n✅ 部署完成!")
            print("💡 请保持终端窗口打开，不要关闭服务")
            print("🛑 按Ctrl+C可停止服务")

            try:
                # 等待用户中断
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n正在停止服务...")
                if backend_proc:
                    backend_proc.terminate()
                if frontend_proc:
                    frontend_proc.terminate()
                print("服务已停止")

    elif choice == "2":
        start_backend()
    elif choice == "3":
        start_frontend()
    elif choice == "4":
        run_tests()
    elif choice == "5":
        subprocess.run([sys.executable, "scripts/monitor_selection.py"])
    elif choice == "6":
        show_instructions()
    elif choice == "7":
        print("退出")
    else:
        print("无效选项")

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        sys.exit(0)
