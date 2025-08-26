# tools/profile_app.py
from __future__ import annotations
import os, sys, cProfile, pstats, argparse, pathlib, multiprocessing

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--sort", default="cumtime", help="pstats sort key")
    parser.add_argument("--out", default="profile.txt")
    args = parser.parse_args()

    import time
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow

    prof = cProfile.Profile()
    prof.enable()

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()

    # Quit after N seconds so the profile closes cleanly
    from PySide6.QtCore import QTimer
    QTimer.singleShot(args.seconds * 1000, app.quit)

    rc = app.exec()
    prof.disable()

    ps = pstats.Stats(prof).strip_dirs().sort_stats(args.sort)
    ps.dump_stats("profile.pstat")
    with open(args.out, "w", encoding="utf-8") as f:
        setattr(ps, "stream", f)
        ps.print_stats(60)   # top 60 entries

    print(f"\nWrote cProfile stats to {args.out} and profile.pstat (loadable in SnakeViz)")
    return rc

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
