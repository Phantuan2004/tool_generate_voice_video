"""Điểm khởi động của ứng dụng Video to SRT."""

import os
import subprocess
import sys
import time
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from gui_app import create_app


def main():
    """Khởi động ứng dụng PyQt6 trong Main Thread."""
    application = QApplication(sys.argv)
    window = create_app()
    window.show()
    sys.exit(application.exec())


def run_with_watchdog():
    """Chạy GUI trong subprocess, tự động restart khi phát hiện thay đổi file .py."""
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        print("[Auto-Reload] Chưa cài đặt watchdog. Đang chạy bình thường...")
        main()
        return

    project_dir = Path(__file__).resolve().parent
    child_proc = None

    def stop_child():
        nonlocal child_proc
        if child_proc and child_proc.poll() is None:
            child_proc.terminate()
            try:
                child_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child_proc.kill()

    def start_child():
        nonlocal child_proc
        stop_child()
        # Chạy GUI trong tiến trình con với cờ --child để QApplication luôn chạy trên Main Thread
        child_proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child"])

    class CodeChangeHandler(FileSystemEventHandler):
        def __init__(self):
            super().__init__()
            self.last_reload = 0

        def on_any_event(self, event):
            # Chỉ lắng nghe file .py và bỏ qua các thư mục hệ thống / môi trường ảo
            src_path = getattr(event, "src_path", "")
            if not src_path or not src_path.endswith(".py"):
                return

            path_obj = Path(src_path)
            ignored_parts = {".venv", "venv", ".git", "__pycache__", "transcripts", "build", "dist"}
            if any(part in ignored_parts for part in path_obj.parts):
                return

            if event.event_type in ("modified", "created", "deleted"):
                now = time.time()
                if now - self.last_reload > 1.2:  # Debounce 1.2s tránh reload lặp khi lưu file
                    self.last_reload = now
                    try:
                        rel_path = os.path.relpath(src_path, project_dir)
                    except ValueError:
                        rel_path = src_path
                    print(f"\n[Auto-Reload] Phát hiện thay đổi: {rel_path}. Đang khởi động lại ứng dụng...")
                    start_child()

    print("[Auto-Reload] Đang chạy với chế độ tự động reload (chỉ giám sát code dự án)...")
    start_child()

    observer = Observer()
    observer.schedule(CodeChangeHandler(), path=str(project_dir), recursive=True)
    observer.start()

    has_logged_crash = False

    try:
        while True:
            time.sleep(0.5)
            if child_proc and child_proc.poll() is not None:
                return_code = child_proc.returncode
                # Nếu người dùng chủ động đóng cửa sổ (return code 0), thoát luôn reloader
                if return_code == 0:
                    break
                # Nếu ứng dụng bị lỗi cú pháp/crash trong khi đang sửa code, giữ reloader chờ sửa xong
                if not has_logged_crash:
                    print(
                        f"\n[Auto-Reload] Ứng dụng dừng với mã lỗi: {return_code}. "
                        "Chế độ auto-reload vẫn đang chờ bạn sửa code để tự khởi động lại..."
                    )
                    has_logged_crash = True
            else:
                has_logged_crash = False
    except KeyboardInterrupt:
        pass
    finally:
        stop_child()
        observer.stop()
        observer.join()


if __name__ == "__main__":
    if "--child" in sys.argv:
        main()
    elif "--no-reload" in sys.argv:
        main()
    else:
        run_with_watchdog()
