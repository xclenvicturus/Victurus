# Victurus/main.py
"""
Qt entrypoint for Victurus (PySide6).
- Creates QApplication
- Shows MainWindow with dock panes + galaxy map
- Safe message if PySide6 is not installed
"""
import sys

try:
    from engine.app.qt_app import run_qt_app
except Exception as e:  # pragma: no cover
    sys.stderr.write(
        "Failed to import Qt app. Ensure PySide6 is installed and the package layout matches.\n"
        f"Import error: {e}\n"
    )
    raise

if __name__ == "__main__":
    sys.exit(run_qt_app())
