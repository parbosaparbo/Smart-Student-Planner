"""
StudyMind AI — Native Desktop App Launcher
Runs Streamlit seamlessly inside a native, standalone desktop window.
No browser tabs, no address bar — 100% native desktop application experience.
"""
import sys
import os
import time
import socket
import subprocess
import threading
import urllib.request
from pathlib import Path

# App metadata
APP_TITLE = "StudyMind AI — Smart Academic Coach"
DEFAULT_PORT = 8501
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 850


def find_free_port(start_port=8501):
    """Find a free port starting from start_port."""
    port = start_port
    while port < start_port + 50:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return start_port


def wait_for_server(url, timeout=30):
    """Wait until the Streamlit server responds."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def start_streamlit_server(port):
    """Start Streamlit in headless mode as a subprocess."""
    workspace = Path(__file__).parent.resolve()
    python_exe = workspace / ".venv" / "Scripts" / "python.exe"
    if not python_exe.exists():
        python_exe = sys.executable

    entry_file = "Dashboard.py"
    cmd = [
        str(python_exe),
        "-m",
        "streamlit",
        "run",
        entry_file,
        f"--server.port={port}",
        "--server.headless=true",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--browser.gatherUsageStats=false",
    ]

    # Hide console window on Windows
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(
        cmd,
        cwd=str(workspace),
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def launch_edge_app_mode(url):
    """Fallback: open as borderless standalone desktop window via MS Edge."""
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    edge_bin = next((p for p in edge_paths if os.path.exists(p)), None)
    if edge_bin:
        cmd = [
            edge_bin,
            f"--app={url}",
            f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
            f"--app-id=StudyMindAI",
        ]
        return subprocess.Popen(cmd)
    return None


def main():
    print(f"🧠 Launching {APP_TITLE} Desktop Application...")
    port = find_free_port(DEFAULT_PORT)
    url = f"http://127.0.0.1:{port}"

    # Start Streamlit server
    server_proc = start_streamlit_server(port)

    # Wait for ready
    print(f"⏳ Initializing local engine on port {port}...")
    if not wait_for_server(url, timeout=25):
        print("⚠️ Server initialization taking longer than expected. Opening window now...")

    # Launch Native Desktop Window via pywebview
    opened_native = False
    try:
        import webview

        print("✨ Native desktop window ready.")

        def on_closed():
            # Cleanly terminate server on window close
            try:
                server_proc.terminate()
            except Exception:
                pass

        window = webview.create_window(
            title=APP_TITLE,
            url=url,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            min_size=(1000, 680),
            confirm_close=False,
            text_select=True,
        )
        window.events.closed += on_closed
        opened_native = True
        webview.start(private_mode=False)

    except Exception as e:
        print(f"Note: pywebview native backend fallback: {e}")

    # Fallback to Edge App Mode if pywebview didn't run
    if not opened_native:
        print("🚀 Opening standalone Edge desktop window...")
        app_proc = launch_edge_app_mode(url)
        if app_proc:
            try:
                app_proc.wait()
            except KeyboardInterrupt:
                pass
        else:
            import webbrowser
            webbrowser.open(url)

    # Cleanup server
    try:
        server_proc.terminate()
        server_proc.wait(timeout=3)
    except Exception:
        server_proc.kill()

    print("👋 StudyMind AI closed.")


if __name__ == "__main__":
    main()

