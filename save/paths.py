# /save/paths.py

"""
Save System Path Management

Provides platform-independent path resolution for save directories, configuration files,
and other game data storage locations.
"""

from __future__ import annotations

from pathlib import Path
import os
import platform

APP_FOLDER_NAME = "Victurus_game"

def get_documents_dir() -> Path:
    # Simple cross-platform Documents locator
    home = Path.home()
    if platform.system() == "Windows":
        return home / "Documents"
    # macOS/Linux: fall back to ~/Documents if present, else home
    doc = home / "Documents"
    return doc if doc.exists() else home

def get_app_dir() -> Path:
    p = get_documents_dir() / APP_FOLDER_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_config_dir() -> Path:
    p = get_app_dir() / "Config"
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_saves_dir() -> Path:
    p = get_app_dir() / "Saves"
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_ui_state_path() -> Path:
    # Historically this file was named ui_windows.json; switch to
    # the simpler ui_state.json name in the Config folder per user intent.
    return get_config_dir() / "ui_state.json"

def sanitize_save_name(name: str) -> str:
    # Keep alnum, dash, underscore, space; replace others with underscore
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in name.strip())
    return safe[:64] if safe else "Save"

def save_folder_for(name: str) -> Path:
    return get_saves_dir() / sanitize_save_name(name)
