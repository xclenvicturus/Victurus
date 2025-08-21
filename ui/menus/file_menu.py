from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QDialog

from PySide6.QtGui import QAction

from save.manager import SaveManager
from ui.dialogs.new_game_dialog import NewGameDialog


def install_file_menu(main_window):
    menubar = main_window.menuBar()
    file_menu = menubar.addMenu("&File")

    act_new = QAction("&New Game…", main_window)
    act_save = QAction("&Save", main_window)
    act_save_as = QAction("Save &As…", main_window)
    act_load = QAction("&Load Game…", main_window)

    file_menu.addAction(act_new)
    file_menu.addSeparator()
    file_menu.addAction(act_save)
    file_menu.addAction(act_save_as)
    file_menu.addSeparator()
    file_menu.addAction(act_load)

    # Wire actions
    act_new.triggered.connect(lambda: _on_new_game(main_window))
    act_save.triggered.connect(lambda: _on_save(main_window))
    act_save_as.triggered.connect(lambda: _on_save_as(main_window))
    act_load.triggered.connect(lambda: _on_load(main_window))


def _on_new_game(win):
    dlg = NewGameDialog(win)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        save_name, commander, loc_label = dlg.get_values()
        from game.new_game import start_new_game
        try:
            start_new_game(save_name, commander, loc_label)
        except Exception as e:
            QMessageBox.critical(win, "New Game Failed", str(e))
            return
        win.start_game_ui()   # replace idle UI with live game UI
        win.status_panel.refresh()


def _on_save(win):
    try:
        SaveManager.save_current()
        win.append_log("Game saved.")
        win.status_panel.refresh()
    except Exception as e:
        QMessageBox.critical(win, "Save Failed", str(e))


def _on_save_as(win):
    from save.paths import get_saves_dir
    saves_dir = get_saves_dir()
    # We only need a name; using file dialog to capture a base name.
    fname, _ = QFileDialog.getSaveFileName(
        win,
        "Save As… (enter a new save name)",
        str(saves_dir / "New Save"),
        "SQLite DB (*.db)",
    )
    if fname:
        path = Path(fname)
        new_name = path.stem
        try:
            dest = SaveManager.save_as(new_name)
            win.append_log(f"Saved As: {dest.name}")
            win.status_panel.refresh()
        except Exception as e:
            QMessageBox.critical(win, "Save As Failed", str(e))


def _on_load(win):
    from save.paths import get_saves_dir
    root = get_saves_dir()
    # Use QFileDialog to select a folder under Saves
    dir_path = QFileDialog.getExistingDirectory(win, "Select Save Folder", str(root))
    if dir_path:
        try:
            SaveManager.load_save(Path(dir_path))
        except Exception as e:
            QMessageBox.critical(win, "Load Failed", str(e))
            return
        win.start_game_ui()    # rebuild UI for loaded game
        win.status_panel.refresh()
