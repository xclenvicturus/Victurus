from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QDialog

from PySide6.QtGui import QAction

from save.manager import SaveManager
from ui.dialogs.new_game_dialog import NewGameDialog
from ui.dialogs.save_as_dialog import SaveAsDialog
from ui.dialogs.load_game_dialog import LoadGameDialog


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
        win.start_game_ui()
        if win._map_view:
            win._map_view.setCurrentIndex(1) # Switch to System tab
        win.status_panel.refresh()
        win.append_log(f"New game '{save_name}' started.")


def _on_save(win):
    active_save = SaveManager.active_save_dir()
    if not active_save:
        _on_save_as(win) # If no active save, treat as "Save As"
        return

    reply = QMessageBox.question(
        win,
        "Save Game",
        f"Overwrite the current save file '{active_save.name}'?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if reply == QMessageBox.StandardButton.No:
        return

    try:
        SaveManager.save_current()
        win.append_log("Game saved.")
        win.status_panel.refresh()
    except Exception as e:
        QMessageBox.critical(win, "Save Failed", str(e))


def _on_save_as(win):
    dlg = SaveAsDialog(win)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        new_name = dlg.get_save_name()
        if not new_name:
            QMessageBox.warning(win, "Save As", "Save name cannot be empty.")
            return
        try:
            dest = SaveManager.save_as(new_name)
            win.append_log(f"Saved As: {dest.name}")
            win.status_panel.refresh()
        except Exception as e:
            QMessageBox.critical(win, "Save As Failed", str(e))


def _on_load(win):
    dlg = LoadGameDialog(win)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        save_path = dlg.get_selected_save_path()
        if save_path:
            try:
                SaveManager.load_save(save_path)
            except Exception as e:
                QMessageBox.critical(win, "Load Failed", str(e))
                return
            win.start_game_ui()
            if win._map_view:
                win._map_view.setCurrentIndex(1) # Switch to System tab
            win.status_panel.refresh()
            win.append_log(f"Loaded game: {save_path.name}")