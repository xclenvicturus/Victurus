# /ui/menus/file_menu.py

"""
File Menu System

Handles file operations including New Game, Load Game, Save Game, Save As, and Close Game
functionality with proper state management and UI integration.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QDialog
from PySide6.QtGui import QAction

from save.save_manager import SaveManager
from ui.state import window_state as _ws
from PySide6.QtCore import QTimer
from ui.dialogs.save_as_dialog import SaveAsDialog
from ui.dialogs.load_game_dialog import LoadGameDialog
from game_controller.log_config import get_ui_logger

logger = get_ui_logger('file_menu')

# NEW: background simulator + player system lookup
from game_controller.sim_loop import universe_sim
from data.db import get_player_full
from ui.menus.view_menu import sync_panels_menu_state


def install_file_menu(main_window):
    menubar = main_window.menuBar()
    file_menu = menubar.addMenu("&File")

    act_new = QAction("&New Game…", main_window)
    act_save = QAction("&Save", main_window)
    act_save_as = QAction("Save &As…", main_window)
    act_load = QAction("&Load Game…", main_window)
    act_close_game = QAction("&Close Game", main_window)

    file_menu.addAction(act_new)
    file_menu.addSeparator()
    file_menu.addAction(act_save)
    file_menu.addAction(act_save_as)
    file_menu.addSeparator()
    file_menu.addAction(act_load)
    file_menu.addSeparator()
    file_menu.addAction(act_close_game)

    # Wire actions
    act_new.triggered.connect(lambda: _on_new_game(main_window))
    act_save.triggered.connect(lambda: _on_save(main_window))
    act_save_as.triggered.connect(lambda: _on_save_as(main_window))
    act_load.triggered.connect(lambda: _on_load(main_window))
    act_close_game.triggered.connect(lambda: _on_close_game(main_window))

    # Store references to enable/disable them based on game state
    main_window._act_save = act_save
    main_window._act_save_as = act_save_as  
    main_window._act_close_game = act_close_game
    
    # Initially, only New Game and Load Game should be enabled
    _update_menu_state(main_window)


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
            # Apply per-save UI state (if any) so docks/panels are restored
            try:
                try:
                    # Suspend writes while we perform programmatic restore
                    SaveManager.suspend_ui_state_writes()
                except Exception:
                    pass
                    try:
                        # Prefer per-save UI state; fall back to global MainWindow entry
                        ui_state = SaveManager.read_ui_state_for_active() or (_ws._load_state() or {}).get('MainWindow') or {}
                        logger.debug("file_menu: loaded ui_state for save=%s keys=%s", getattr(SaveManager.active_save_dir(), 'name', None), list(ui_state.keys()) if isinstance(ui_state, dict) else None)
                        if ui_state:
                            try:
                                # Mark as restoring so internal handlers avoid persisting
                                win._restoring_ui = True
                            except Exception:
                                pass
                            try:
                                from save.ui_state_tracer import append_event
                                append_event("file_menu_apply_ui_state", f"keys={','.join(sorted(list(ui_state.keys()))) if isinstance(ui_state, dict) else ''}")
                                win._restore_ui_state(ui_state)
                                logger.debug("file_menu: applied ui_state to window %s", getattr(win, 'WIN_ID', 'MainWindow'))
                            except Exception:
                                logger.exception("file_menu: failed applying ui_state to window")
                    except Exception:
                        logger.exception("file_menu: error while loading/applying ui_state")
                finally:
                    # Resume writes after a short delay so programmatic layout settles
                    try:
                        QTimer.singleShot(80, lambda w=win: (SaveManager.resume_ui_state_writes(), setattr(w, '_restoring_ui', False) if hasattr(w, '_restoring_ui') else None))
                    except Exception:
                        try:
                            SaveManager.resume_ui_state_writes()
                        except Exception:
                            pass
                        try:
                            if hasattr(win, '_restoring_ui'):
                                try:
                                    win._restoring_ui = False
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass
            # Apply UI state for new game (same as load game) so docks/panels are restored
            try:
                try:
                    # Suspend writes while we perform programmatic restore
                    SaveManager.suspend_ui_state_writes()
                except Exception:
                    pass
                try:
                    # For new games, load the global UI state since there's no per-save state yet
                    ui_state = (_ws._load_state() or {}).get('MainWindow') or {}
                    logger.debug("file_menu: loaded ui_state for new game keys=%s", list(ui_state.keys()) if isinstance(ui_state, dict) else None)
                    if ui_state:
                        try:
                            # Mark as restoring so internal handlers avoid persisting
                            win._restoring_ui = True
                        except Exception:
                            pass
                        try:
                            from save.ui_state_tracer import append_event
                            append_event("file_menu_apply_ui_state_new_game", f"keys={','.join(sorted(list(ui_state.keys()))) if isinstance(ui_state, dict) else ''}")
                            win._restore_ui_state(ui_state)
                            logger.debug("file_menu: applied ui_state to new game window %s", getattr(win, 'WIN_ID', 'MainWindow'))
                        except Exception:
                            logger.exception("file_menu: failed applying ui_state to new game window")
                except Exception:
                    logger.exception("file_menu: error while loading/applying ui_state for new game")
                finally:
                    # Resume writes after a short delay so programmatic layout settles
                    try:
                        QTimer.singleShot(80, lambda w=win: (SaveManager.resume_ui_state_writes(), setattr(w, '_restoring_ui', False) if hasattr(w, '_restoring_ui') else None))
                    except Exception:
                        try:
                            SaveManager.resume_ui_state_writes()
                        except Exception:
                            pass
                        try:
                            if hasattr(win, '_restoring_ui'):
                                try:
                                    win._restoring_ui = False
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass
            # Now start the live UI
            win.start_game_ui()
            if getattr(win, "_map_view", None):
                win._map_view.setCurrentIndex(1)  # Switch to System tab
            # Ensure status dock exists before attempting to refresh it
            try:
                if hasattr(win, "_ensure_status_dock"):
                    try:
                        win._ensure_status_dock()
                    except Exception:
                        pass
                # Also ensure actions dock is created
                if hasattr(win, "_ensure_actions_dock"):
                    try:
                        win._ensure_actions_dock()
                    except Exception:
                        pass
                if getattr(win, "status_panel", None):
                    win.status_panel.refresh()
                # Also refresh actions panel to update contextual buttons
                if getattr(win, "actions_panel", None):
                    win.actions_panel.refresh()
            except Exception:
                pass

            # NEW: start background universe sim and set visible system to player's
            universe_sim.ensure_running()
            player = get_player_full()
            if player:
                universe_sim.set_visible_system(player.get("current_player_system_id"))

            win.append_log(("All", f"New game started: {save_path.name}"))
            
            # Update menu state to enable save/close actions
            _update_menu_state(win)
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
        win.append_log(("All", "Game saved."))
        try:
            if hasattr(win, "_ensure_status_dock"):
                try:
                    win._ensure_status_dock()
                except Exception:
                    pass
            if getattr(win, "status_panel", None):
                win.status_panel.refresh()
        except Exception:
            pass
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
            win.append_log(("All", f"Saved As: {dest.name}"))
            try:
                if hasattr(win, "_ensure_status_dock"):
                    try:
                        win._ensure_status_dock()
                    except Exception:
                        pass
                if getattr(win, "status_panel", None):
                    win.status_panel.refresh()
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(win, "Save As Failed", str(e))


# Global flag to prevent multiple concurrent load dialogs
_load_dialog_open = False

def _on_load(win):
    from game_controller.log_config import get_ui_logger
    logger = get_ui_logger('file_menu')
    
    global _load_dialog_open
    
    # Prevent multiple dialogs from opening simultaneously
    if _load_dialog_open:
        logger.debug("Load dialog already open, ignoring request")
        return
    
    try:
        _load_dialog_open = True
        logger.debug("Load game button pressed - creating dialog")
        dlg = LoadGameDialog(win)
        logger.debug("Load game dialog created, executing...")
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            save_path = dlg.get_selected_save_path()
            if save_path:
                try:
                    SaveManager.load_save(save_path)
                except Exception as e:
                    QMessageBox.critical(win, "Load Failed", str(e))
                    return
                # Apply per-save UI state (if any) so docks/panels are restored
                try:
                    try:
                        SaveManager.suspend_ui_state_writes()
                    except Exception:
                        pass
                    try:
                        ui_state = SaveManager.read_ui_state_for_active() or (_ws._load_state() or {}).get('MainWindow') or {}
                        if ui_state:
                            try:
                                win._restoring_ui = True
                            except Exception:
                                pass
                            try:
                                win._restore_ui_state(ui_state)
                            except Exception:
                                pass
                    finally:
                        try:
                            QTimer.singleShot(80, lambda w=win: (SaveManager.resume_ui_state_writes(), setattr(w, '_restoring_ui', False) if hasattr(w, '_restoring_ui') else None))
                        except Exception:
                            try:
                                SaveManager.resume_ui_state_writes()
                            except Exception:
                                pass
                            try:
                                if hasattr(win, '_restoring_ui'):
                                    try:
                                        win._restoring_ui = False
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                except Exception:
                    pass
                # Only initialize UI if it hasn't been created yet
                # Loading a save should not recreate the entire UI layout
                if not hasattr(win, "_map_view") or win._map_view is None:
                    win.start_game_ui()
                else:
                    # UI already exists, just refresh the data without recreating layout
                    if getattr(win, "_map_view", None):
                        win._map_view.setCurrentIndex(1)  # Switch to System tab
                
                try:
                    if hasattr(win, "_ensure_status_dock"):
                        try:
                            win._ensure_status_dock()
                        except Exception:
                            pass
                    # Also ensure actions dock is created
                    if hasattr(win, "_ensure_actions_dock"):
                        try:
                            win._ensure_actions_dock()
                        except Exception:
                            pass
                    if getattr(win, "status_panel", None):
                        win.status_panel.refresh()
                    # Also refresh actions panel to update contextual buttons
                    if getattr(win, "actions_panel", None):
                        win.actions_panel.refresh()
                    # Also refresh actions panel to update contextual buttons
                    if getattr(win, "actions_panel", None):
                        win.actions_panel.refresh()
                except Exception:
                    pass

                # NEW: start background universe sim and set visible system to player's
                try:
                    universe_sim.ensure_running()
                    player = get_player_full()
                    if player:
                        universe_sim.set_visible_system(player.get("current_player_system_id"))
                except Exception:
                    pass

                try:
                    win.append_log(("All", f"Loaded game: {save_path.name}"))
                except Exception:
                    pass
                
                # Update menu state to enable save/close actions
                _update_menu_state(win)
    except Exception as e:
        logger.error(f"Error in _on_load: {e}")
        try:
            from ui.error_handler import handle_error
            handle_error(e, "Loading game")
        except Exception:
            # Fallback to simple message box
            QMessageBox.critical(win, "Load Error", f"Failed to load game: {str(e)}")
    finally:
        # Always reset the flag when done
        _load_dialog_open = False


def _on_close_game(win):
    """Close the current game and return to the no-game-loaded state"""
    try:
        # Confirm with user
        reply = QMessageBox.question(
            win,
            "Close Game", 
            "Are you sure you want to close the current game? Any unsaved progress will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Stop the status refresh timer
        try:
            if hasattr(win, '_status_timer') and win._status_timer:
                win._status_timer.stop()
        except Exception:
            pass
        
        # Stop the universe simulation
        try:
            universe_sim.stop()
        except Exception:
            pass
        
        # Close database connection
        try:
            from data import db
            db.close_active_connection()
        except Exception:
            pass
        
        # Clear the active save
        try:
            SaveManager._active_save_dir = None
        except Exception:
            pass
        
        # Hide and remove all game-related docks
        try:
            # Hide status dock
            if hasattr(win, 'status_dock') and win.status_dock:
                win.status_dock.hide()
                # Get the widget inside the dock and delete it
                status_widget = win.status_dock.widget()
                if status_widget:
                    status_widget.deleteLater()
                win.removeDockWidget(win.status_dock)
                win.status_dock.deleteLater()
                win.status_dock = None
            
            # Hide log docks
            if hasattr(win, '_log_docks') and isinstance(win._log_docks, dict):
                for dock in win._log_docks.values():
                    if dock:
                        dock.hide()
                        # Get the widget inside the dock and delete it
                        log_widget = dock.widget()
                        if log_widget:
                            log_widget.deleteLater()
                        win.removeDockWidget(dock)
                        dock.deleteLater()
                win._log_docks = None
                win._log_panels = None
            
            # Hide location panel docks using the proper stored references
            if hasattr(win, '_dock_panel_galaxy') and win._dock_panel_galaxy:
                win._dock_panel_galaxy.hide()
                # Get the panel inside the dock and delete it
                galaxy_panel = win._dock_panel_galaxy.widget()
                if galaxy_panel:
                    galaxy_panel.deleteLater()
                win.removeDockWidget(win._dock_panel_galaxy)
                win._dock_panel_galaxy.deleteLater()
                win._dock_panel_galaxy = None
            
            if hasattr(win, '_dock_panel_system') and win._dock_panel_system:
                win._dock_panel_system.hide()
                # Get the panel inside the dock and delete it
                system_panel = win._dock_panel_system.widget()
                if system_panel:
                    system_panel.deleteLater()
                win.removeDockWidget(win._dock_panel_system)
                win._dock_panel_system.deleteLater()
                win._dock_panel_system = None
        except Exception:
            pass
        
        # Clean up controllers and presenters BEFORE destroying widgets
        try:
            # Clean up leader line controllers first to remove any overlays
            if hasattr(win, 'lead') and win.lead:
                try:
                    if hasattr(win.lead, 'detach'):
                        win.lead.detach()  # Detach overlays
                    if hasattr(win.lead, 'hide_all'):
                        win.lead.hide_all()  # Hide any visible elements
                    if hasattr(win.lead, 'clear'):
                        win.lead.clear()  # Clear any internal state
                except Exception:
                    pass
                win.lead = None
            
            if hasattr(win, 'lead_galaxy') and win.lead_galaxy:
                try:
                    if hasattr(win.lead_galaxy, 'detach'):
                        win.lead_galaxy.detach()  # Detach overlays
                    if hasattr(win.lead_galaxy, 'hide_all'):
                        win.lead_galaxy.hide_all()  # Hide any visible elements
                    if hasattr(win.lead_galaxy, 'clear'):
                        win.lead_galaxy.clear()  # Clear any internal state
                except Exception:
                    pass
                win.lead_galaxy = None
            
            # Clean up presenters
            if hasattr(win, 'presenter_galaxy'):
                win.presenter_galaxy = None
            if hasattr(win, 'presenter_system'):
                win.presenter_system = None
            if hasattr(win, 'travel_flow'):
                win.travel_flow = None
        except Exception:
            pass
        
        # Reset UI state to initial idle state
        try:
            # Ensure the idle label exists and has the correct text
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QLabel
            
            # Always create a fresh idle label to ensure it works properly
            win._idle_label = QLabel("No game loaded.\nUse File → New Game or Load Game to begin.")
            win._idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Add reasonable styling - white text for visibility on grey background
            win._idle_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: normal;
                    color: #ffffff;
                    padding: 20px;
                }
            """)
            
            # Get the current central widget before replacing it
            current_central = win.centralWidget()
            
            # Set the central widget back to the idle label first
            win.setCentralWidget(win._idle_label)
            
            # Now delete the old central widget if it was different
            if current_central and current_central != win._idle_label:
                current_central.deleteLater()
            
            # Ensure the idle label is visible and properly styled
            win._idle_label.show()
            win._idle_label.raise_()
            
            # Reset game-related attributes
            win._map_view = None
            win._central_splitter = None
            win._right_splitter = None
            win.location_panel_galaxy = None
            win.location_panel_system = None
            win.location_panel = None
            win.status_panel = None
            
            # Clear additional log-related attributes
            if hasattr(win, '_log_entries'):
                win._log_entries = []
            if hasattr(win, '_log_categories'):
                win._log_categories = None
            
            # Clear status bar
            try:
                if hasattr(win, 'lbl_systems'):
                    win.lbl_systems.setText("Systems: —")
                if hasattr(win, 'lbl_items'):
                    win.lbl_items.setText("Items: —")
                if hasattr(win, 'lbl_ships'):
                    win.lbl_ships.setText("Ships: —")
                if hasattr(win, 'lbl_credits'):
                    win.lbl_credits.setText("Credits: —")
            except Exception:
                pass
            
            # Update window title to remove game name
            win.setWindowTitle("Victurus")
            
            # Force a repaint to ensure the idle label is displayed
            win.update()
            win.repaint()
            
        except Exception:
            pass
        
        # Update menu state (disable save actions, enable new/load)
        _update_menu_state(win)
        
        # Update View menu state (disable panel toggles when no game loaded)
        sync_panels_menu_state(win)
        
        # Log the action
        try:
            win.append_log(("All", "Game closed"))
        except Exception:
            pass
            
    except Exception as e:
        try:
            from ui.error_handler import handle_error
            handle_error(e, "Closing game")
        except Exception:
            QMessageBox.critical(win, "Close Game Error", f"Failed to close game: {str(e)}")


def _update_menu_state(win):
    """Update the File menu actions based on whether a game is loaded"""
    try:
        # Check if a game is currently loaded
        has_active_save = SaveManager.active_save_dir() is not None
        
        # Enable/disable actions based on game state
        if hasattr(win, '_act_save') and win._act_save:
            win._act_save.setEnabled(has_active_save)
        if hasattr(win, '_act_save_as') and win._act_save_as:
            win._act_save_as.setEnabled(has_active_save)
        if hasattr(win, '_act_close_game') and win._act_close_game:
            win._act_close_game.setEnabled(has_active_save)
            
    except Exception:
        pass
