"""
自动更新模块
============
启动后定期检查 GitHub Releases，发现新版本立即在后台下载；
用户确认后通过临时脚本替换自身 exe 并重新启动。

环境变量:
    GITHUB_TOKEN — 私有仓库访问令牌（可选；公开仓库不需要）

发布新版本时的注意事项:
    1. 修改下方 APP_VERSION 为新版版本号（如 "0.2.0"）
    2. 在 GitHub 创建 Release，tag 形如 v0.2.0，并上传 KaliToolKit.exe 附件
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

# ========== 配置 ==========
APP_VERSION = "0.2.0"                  # 每次发布必须同步修改！
GITHUB_REPO = "sheyunyang/kali-toolkit"
ASSET_NAME = "KaliToolKit.exe"         # Release 附件名（必须与上传的附件一致）
CHECK_INTERVAL = 15 * 60               # 每 15 分钟检查一次
STARTUP_DELAY = 8                      # 启动 8 秒后首次检查
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# ========== 自替换辅助脚本（Windows） ==========
BAT_TEMPLATE = """@echo off
rem Kali ToolKit 自更新脚本：等待主程序退出 -> 替换 exe -> 重启 -> 自删除
:wait
ping 127.0.0.1 -n 2 >nul
copy /y "__NEW__" "__OLD__" >nul 2>&1
if errorlevel 1 goto wait
start "" "__OLD__"
del "%~f0"
"""

# ========== 全局状态 ==========
_lock = threading.Lock()
_state = {
    "state": "idle",           # idle | checking | downloading | ready | uptodate | error
    "current_version": APP_VERSION,
    "latest_version": "",
    "progress": 0,             # 0-100
    "downloaded_bytes": 0,
    "total_bytes": 0,
    "release_url": "",
    "error": "",
}


def get_status():
    with _lock:
        return dict(_state)


def _set_state(**kw):
    with _lock:
        _state.update(kw)


def is_frozen():
    """是否以 PyInstaller 打包的 exe 运行"""
    return getattr(sys, 'frozen', False)


def exe_path():
    return Path(sys.executable) if is_frozen() else None


def update_file_path():
    """新版本 exe 的下载位置"""
    if is_frozen():
        return exe_path().parent / (exe_path().stem + ".update.exe")
    # 开发模式：下载到用户目录，绝不覆盖源码目录
    d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "KaliToolKit" / "updates"
    d.mkdir(parents=True, exist_ok=True)
    return d / ASSET_NAME


def parse_version(tag):
    """'v0.2.0' -> (0, 2, 0)，取不到数字则 (0,)"""
    nums = re.findall(r'\d+', tag or "")
    return tuple(int(x) for x in nums[:3]) if nums else (0,)


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    n = max(len(a), len(b))
    a += (0,) * (n - len(a))
    b += (0,) * (n - len(b))
    return a > b


def _headers():
    h = {
        "User-Agent": f"KaliToolKit/{APP_VERSION}",
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _http_get_json(url, timeout=10):
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def check_once():
    """
    检查一次更新。
    发现新版本返回 {"version", "url", "page"}；已是最新或出错返回 None。
    """
    _set_state(state="checking", error="")
    try:
        data = _http_get_json(API_URL)
    except Exception as e:
        _set_state(state="error", error=f"无法连接更新服务器：{e}")
        return None

    latest = (data.get("tag_name") or "").strip()
    if not latest:
        _set_state(state="error", error="更新服务器返回异常")
        return None

    if not is_newer(latest, APP_VERSION):
        _set_state(state="uptodate", latest_version=latest)
        return None

    asset = next(
        (a for a in data.get("assets", []) if a.get("name") == ASSET_NAME),
        None,
    )
    if not asset:
        _set_state(state="error", error=f"新版本 {latest} 未找到 {ASSET_NAME} 附件")
        return None

    return {
        "version": latest,
        "url": asset["browser_download_url"],
        "page": data.get("html_url", ""),
    }


def download(release):
    """后台下载新版本，带进度"""
    dest = update_file_path()
    tmp = dest.with_name(dest.name + ".part")
    _set_state(
        state="downloading",
        latest_version=release["version"],
        release_url=release["page"],
        progress=0, downloaded_bytes=0, total_bytes=0, error="",
    )
    try:
        req = urllib.request.Request(release["url"], headers=_headers())
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                pct = round(got * 100 / total) if total else 0
                _set_state(progress=pct, downloaded_bytes=got, total_bytes=total)
        if total and got < total:
            raise IOError("文件下载不完整")
        os.replace(tmp, dest)
        _set_state(state="ready", progress=100)
    except Exception as e:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        _set_state(state="error", error=f"下载失败：{e}")


def check_and_download():
    """检查一次；若发现新版本则立即下载"""
    release = check_once()
    if release:
        download(release)


def start_update_checker():
    """后台守护线程：启动后先查一次，之后每 CHECK_INTERVAL 复查"""
    def loop():
        time.sleep(STARTUP_DELAY)
        while True:
            try:
                check_and_download()
            except Exception:
                pass
            time.sleep(CHECK_INTERVAL)

    threading.Thread(target=loop, daemon=True, name="update-checker").start()


def install_and_restart():
    """
    用户确认后：生成自替换脚本 -> 延迟退出主程序 -> 脚本替换 exe 并重启。
    返回 (ok, message)。
    """
    if not is_frozen():
        return False, "开发模式下无法自更新，请手动替换文件"

    dest = update_file_path()
    if not dest.exists():
        return False, "更新文件尚未下载完成"

    old = exe_path()
    try:
        fd, bat_name = tempfile.mkstemp(suffix=".bat", prefix="kali_update_")
        os.close(fd)
        bat = Path(bat_name)
        script = (BAT_TEMPLATE
                  .replace("__NEW__", str(dest))
                  .replace("__OLD__", str(old)))
        # bat 按 GBK 编码写入，兼容中文路径
        bat.write_bytes(script.encode("gbk", errors="replace"))

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.Popen(
            ["cmd", "/c", str(bat)],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            startupinfo=si,
            close_fds=True,
        )
    except Exception as e:
        return False, f"无法启动更新脚本：{e}"

    # 1 秒后强制退出，让辅助脚本接管（os._exit 不跑清理，立即释放 exe 占用）
    threading.Timer(1.0, lambda: os._exit(0)).start()
    return True, "正在重启以完成更新…"
