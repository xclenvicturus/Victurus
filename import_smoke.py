import importlib, traceback, sys

mods = [
    'data.db',
    'data.seed',
    'game.travel',
    'game.travel_flow',
    'save.save_manager',
    'ui.maps.tabs',
    'ui.maps.system',
    'ui.maps.galaxy',
    'ui.maps.icons',
    'ui.controllers.map_actions',
    'ui.controllers.galaxy_location_presenter',
    'ui.controllers.system_location_presenter',
    'ui.menus.view_menu',
    'ui.state.main_window_state',
    'ui.main_window'
]

print('BEGIN IMPORT SMOKE TEST')
ok = []
err = []
for m in mods:
    try:
        importlib.import_module(m)
        print('OK   ', m)
        ok.append(m)
    except Exception:
        print('ERROR', m)
        traceback.print_exc()
        err.append(m)

print('\nSUMMARY:')
print('OK:', len(ok))
print('ERR:', len(err))
if err:
    sys.exit(2)
sys.exit(0)
