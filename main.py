import sys
import argparse
import signal
from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication
from gui import SentinelGUI

try:
    from build_config import CAMERA_DEFAULT_MODE
except Exception:
    CAMERA_DEFAULT_MODE = "no-camera"


def _default_show_camera():
    return str(CAMERA_DEFAULT_MODE).strip().lower() == "show-camera"


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Sentinel Face Lock")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--show-camera",
        action="store_true",
        help="Force showing the camera preview window.",
    )
    group.add_argument(
        "--no-camera",
        action="store_true",
        help="Force hidden mode (no camera preview window).",
    )
    return parser.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])
    show_camera = _default_show_camera()
    if args.show_camera:
        show_camera = True
    elif args.no_camera:
        show_camera = False

    app = QApplication(sys.argv)
    if not show_camera:
        # Keep the app running even when no window is shown.
        app.setQuitOnLastWindowClosed(False)

    window = SentinelGUI(show_camera_preview=show_camera)
    app.aboutToQuit.connect(window.cleanup)

    # Keep Python signal handling responsive while Qt event loop is running.
    signal_timer = QtCore.QTimer()
    signal_timer.start(200)
    signal_timer.timeout.connect(lambda: None)

    def _handle_sigint(_sig, _frame):
        print("Shutdown requested (Ctrl+C). Exiting cleanly...")
        app.quit()

    signal.signal(signal.SIGINT, _handle_sigint)

    if show_camera:
        window.show()

    try:
        return app.exec()
    except KeyboardInterrupt:
        print("Interrupted. Exiting cleanly...")
        app.quit()
        return 0


if __name__ == "__main__":
    sys.exit(main())
