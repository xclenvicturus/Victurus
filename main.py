"""
Victurus entrypoint.
Ensures the database exists (schema + seed handled in data/db.py) and launches the UI.
"""

from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from data import db


def main() -> int:
    # Ensure DB file exists and is initialized/seeded (handled inside get_connection)
    conn = db.get_connection()
    conn.close()

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
