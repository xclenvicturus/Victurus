# /ui/menus/file_menu.py

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QDialog
from PySide6.QtGui import QAction

from save.save_manager import SaveManager
from ui.dialogs.save_as_dialog import SaveAsDialog
from ui.dialogs.load_game_dialog import LoadGameDialog

# NEW: background simulator + player system lookup
from game_controller.sim_loop import universe_sim
from data.db import get_player_full


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
    """
    Delegate New Game creation to LoadGameDialog's integrated new-game flow.
    That flow uses IDs (race/system/location) and avoids parsing labels.
    """
    dlg = LoadGameDialog(win)

    # Kick off the dialog's internal New Game flow (opens NewGameDialog inside).
    # The dialog will accept itself if creation succeeds.
    if hasattr(dlg, "_on_new_game"):
        dlg._on_new_game()

    if dlg.result() == QDialog.DialogCode.Accepted:
        save_path = dlg.get_selected_save_path()
        if save_path:
            try:
                SaveManager.load_save(save_path)
            except Exception as e:
                QMessageBox.critical(win, "Load Failed", str(e))
                return
            win.start_game_ui()
            if getattr(win, "_map_view", None):
                win._map_view.setCurrentIndex(1)  # Switch to System tab
            win.status_panel.refresh()

            # NEW: start background universe sim and set visible system to player's
            universe_sim.ensure_running()
            player = get_player_full()
            if player:
                universe_sim.set_visible_system(player.get("current_player_system_id"))

            win.append_log(f"New game started: {save_path.name}")
    else:
        # User canceled or creation failed; optionally show Load dialog normally.
        _on_load(win)


def _on_save(win):
    active_save = SaveManager.active_save_dir()
    if not active_save:
        _on_save_as(win)  # If no active save, treat as "Save As"
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
            if getattr(win, "_map_view", None):
                win._map_view.setCurrentIndex(1)  # Switch to System tab
            win.status_panel.refresh()

            # NEW: start background universe sim and set visible system to player's
            universe_sim.ensure_running()
            player = get_player_full()
            if player:
                universe_sim.set_visible_system(player.get("current_player_system_id"))

            win.append_log(f"Loaded game: {save_path.name}")
