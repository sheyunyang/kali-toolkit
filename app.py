import webview
import sys
import os
import pathlib
import socket
import time
import threading
import urllib.request
import uvicorn


# ========== 路径处理 ==========
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
FRONTEND_HTML = os.path.join(BASE_DIR, 'frontend', 'index.html')

sys.path.insert(0, BACKEND_DIR)


# ========== 端口选择 ==========
def pick_free_port():
    """找一个空闲的本机端口，避免 8000 被占用导致后端静默失败"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def wait_for_backend(port, timeout=15):
    """轮询健康检查，等待 FastAPI 就绪"""
    url = f'http://127.0.0.1:{port}/'
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


# ========== 过渡页 HTML ==========
SPLASH_HTML = """
<!DOCTYPE html>
<html>
<head>
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        background: #000;
        color: #00f0ff;
        font-family: 'Consolas', 'Courier New', monospace;
        height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        user-select: none;
        -webkit-user-select: none;
    }
    .logo {
        font-size: 48px;
        font-weight: 700;
        letter-spacing: 8px;
        margin-bottom: 40px;
        text-shadow: 0 0 30px rgba(0, 240, 255, 0.8);
        animation: pulse 1.5s ease-in-out infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 0.7; }
        50% { opacity: 1; }
    }
    .loading-bar {
        width: 400px;
        height: 3px;
        background: rgba(0, 240, 255, 0.1);
        border-radius: 10px;
        overflow: hidden;
        margin-bottom: 20px;
    }
    .loading-progress {
        height: 100%;
        background: linear-gradient(90deg, #00f0ff, #7c3aed);
        border-radius: 10px;
        animation: loading 3s ease-in-out infinite;
    }
    @keyframes loading {
        0% { width: 5%; margin-left: 0; }
        50% { width: 60%; margin-left: 20%; }
        100% { width: 5%; margin-left: 95%; }
    }
    .hint {
        font-size: 12px;
        color: #475569;
        letter-spacing: 3px;
        animation: blink 1.5s ease-in-out infinite;
    }
    @keyframes blink {
        0%, 100% { opacity: 0.4; }
        50% { opacity: 1; }
    }
</style>
</head>
<body>
    <div class="logo">KALI TOOLKIT</div>
    <div class="loading-bar">
        <div class="loading-progress"></div>
    </div>
    <div class="hint">LOADING...</div>
</body>
</html>
"""


def run_backend(port):
    """后台线程启动 FastAPI"""
    try:
        time.sleep(0.3)
        os.chdir(BACKEND_DIR)
        from main import app
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    except Exception as e:
        print(f"后端启动失败: {e}")


def on_loaded(splash_window):
    """主窗口加载完成后，延迟关闭过渡窗口"""
    time.sleep(1.0)
    try:
        splash_window.destroy()
    except Exception:
        pass


if __name__ == '__main__':
    port = pick_free_port()

    # 1. 后台线程启动后端
    backend_thread = threading.Thread(target=run_backend, args=(port,), daemon=True)
    backend_thread.start()

    # 2. 先创建过渡窗口（无边框，置顶）
    splash_window = webview.create_window(
        title='Kali ToolKit',
        html=SPLASH_HTML,
        width=600,
        height=400,
        frameless=True,
        easy_drag=True,
        background_color='#000000',
        on_top=True,
        resizable=False,
    )

    # 3. 等后端就绪后，打开主窗口（健康检查替代固定 sleep）
    def open_main():
        ready = wait_for_backend(port, timeout=15)
        if not ready:
            print('后端启动超时，仍尝试打开主窗口')
        url = pathlib.Path(FRONTEND_HTML).as_uri() + f'?api_port={port}'
        main_window = webview.create_window(
            title='Kali ToolKit · Lite',
            url=url,
            width=1400,
            height=900,
            min_size=(1000, 600),
            background_color='#0a0e17',
        )
        # 主窗口加载完成后，关闭过渡窗口
        threading.Thread(target=on_loaded, args=(splash_window,), daemon=True).start()

    threading.Thread(target=open_main, daemon=True).start()

    # 4. 启动 PyWebView 主循环
    webview.start()
