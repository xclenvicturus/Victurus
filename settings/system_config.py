# /settings/system_config.py

"""
Victurus System Configuration

Centralized system-wide adjustable settings:
- Visual parameters (spacing, colors, sizing)
- Timing and performance settings
- Map display and interaction parameters
- User-tweakable variables for fine-tuning
"""

# ---------------------------------------------------------------------------
# Orbit layout
# ---------------------------------------------------------------------------
# Innermost ring distance from the star.
# Units: astronomical units (AU). This determines the baseline orbital radius
# used when converting to pixels via `SPREAD_PX_PER_AU`.
# Typical values: 10.0 - 60.0. Larger values spread rings farther from the
# star and increase scene size.
BASE_ORBIT_AU = 30.0

# Default uniform gap between rings.
# Units: AU. When `RING_OFFSETS_AU` is None, consecutive rings are placed at
# BASE_ORBIT_AU + n * RING_GAP_AU. Increase to create more visual spacing
# between planetary rings. Typical: 10.0 - 40.0.
RING_GAP_AU = 26.4

# Visual scale: number of pixels per AU.
# Controls the conversion from AU -> pixels. Larger values zoom the map in;
# smaller values zoom out. Typical: 4.0 - 16.0 depending on desired zoom.
SPREAD_PX_PER_AU = 10.0

# Optional explicit gaps between consecutive rings (list of AU values).
# If set to a list, the list defines the gap (AU) between consecutive rings
# starting with the gap after the base ring. Example: [4.0, 6.0] means
# ring0=BASE_ORBIT_AU, ring1=BASE_ORBIT_AU+4.0, ring2=BASE_ORBIT_AU+4.0+6.0.
# Set to None to use the uniform RING_GAP_AU value instead.
RING_OFFSETS_AU = None

# ---------------------------------------------------------------------------
# Visual sizes (pixels)
# ---------------------------------------------------------------------------
# NOTE: Per-item visual size ranges and optional moon base radii were
# previously exposed here but are currently unused in the codebase. Keep
# higher-level spacing and parent/child margins below; individual item
# sizing is controlled closer to the rendering code where needed.

# Minimum radial margin for moons expressed as a fraction of the parent's
# visual radius. The computed moon orbit will be at least
# parent_radius + max(MOON_BASE_MARGIN_PX, parent_radius * MOON_PARENT_RADIUS_SCALE).
# Typical: 0.2 - 0.6 (20% - 60% of parent radius).
MOON_PARENT_RADIUS_SCALE = 0.80

# ---------------------------------------------------------------------------
# Parent-child orbit margins
# ---------------------------------------------------------------------------
# When a station or moon orbits a planet, this margin (in pixels) is added
# outside the parent's visual radius so children don't overlap the parent icon.
# Increasing this pushes children farther out radially.
STATION_BASE_MARGIN_PX = 24.0

# Additional radial pixels per extra station around the same parent.
# Each additional child increases its radial offset by this delta (before
# applying the minimum gap). Typical: 4 - 12.
STATION_PER_ITEM_DELTA_PX = 24.0

# Base margin for moons (pixels) applied outside the parent's visual radius.
MOON_BASE_MARGIN_PX = 10.0

# Additional radial pixels per extra moon around the same parent.
MOON_PER_ITEM_DELTA_PX = 6.0

# Minimum radial gap (pixels) between successive child orbit radii (applies
# to stations + moons). This prevents children from visually touching. Raise
# this to spread children into separate tiers.
CHILD_MIN_GAP_PX = 16.0

# ---------------------------------------------------------------------------
# Animation / timing
# ---------------------------------------------------------------------------
# Milliseconds between orbit tick updates. The widget currently manages its
# own default interval; this config entry was previously present but is not
# referenced elsewhere, so the interval is controlled in the view code.

# ---------------------------------------------------------------------------
# Follow / center smoothing
# ---------------------------------------------------------------------------
# Externally configurable tuning for the view centering behavior when the
# map locks to a location. These settings control how aggressively the view
# interpolates toward the locked entity, how often to retry when the item
# isn't present yet, and how sensitive the viewport must be (in device
# pixels) before performing a re-center operation. Adjust to reduce
# visible jitter or to make following snappier.
#
# Alpha applied each tick when interpolating the view center toward the
# target. Range 0.0 (no movement) .. 1.0 (instant). Lower values smooth more
# but increase lag; typical: 0.10 - 0.40.
VIEW_CENTER_SMOOTH_ALPHA = 0.25

# Milliseconds to wait between automatic retries when a requested location
# isn't yet present in the scene (race during load). Lower = faster retry.
VIEW_CENTER_RETRY_MS = 50

# Maximum number of retry attempts before giving up when an item lookup
# fails during a center request.
VIEW_CENTER_RETRY_MAX = 8

# Pixel threshold (device pixels) the viewport target must move before the
# view actually issues a re-center. Increasing this reduces micro-jitter
# at the cost of slightly less precise following. Typical: 1 - 4.
VIEW_CENTER_PIXEL_THRESHOLD = 2

# ---------------------------------------------------------------------------
# Persistence / features
# ---------------------------------------------------------------------------
# (No active persistence toggles remain here; persistence behavior is handled
# by the save manager and map code. Previously exposed flags were unused.)

# ---------------------------------------------------------------------------
# View / interaction
# ---------------------------------------------------------------------------
# Minimum and maximum unit scale allowed.
# The view's effective scale = SPREAD_PX_PER_AU * unit_scale (BackgroundView._unit_px).
# These limits remain available for any consumers that adjust unit scale.
VIEW_MIN_UNIT_SCALE = 0.35
VIEW_MAX_UNIT_SCALE = 2.0

# Number of seconds the view will suppress external auto-centering after the
# user performs an interaction (wheel or manual pan). This prevents the UI
# from immediately snapping the view back while the user is interacting.
# Typical: 0.5 - 2.5
VIEW_USER_INTERACTION_SUPPRESS_SEC = 1.25

# ---------------------------------------------------------------------------
# Background & starfield
# ---------------------------------------------------------------------------
# Logical unit default used by BackgroundView when no explicit unit scale is
# applied. This controls the base logical -> pixel multiplier used by views
# that haven't overridden their unit scale. Typical: 8.0 - 16.0.
VIEW_UNIT_PX = 10.0

# Starfield tiling: logical tile size in pixels for pre-rendered star tiles.
# Increase for higher detail at the cost of memory. Typical: 256-1024.
STARFIELD_TILE_PX = 512

# Starfield parallax layers (slow -> fast). Each value is a factor applied
# to the scene offset to compute parallax for that layer. Tweak to change
# perceived depth of the star layers.
STARFIELD_PARALLAX = [0.20, 0.45, 0.85]

# Approximate star count per tile for each parallax layer (same length as
# STARFIELD_PARALLAX). Increase counts to add more stars; lower to reduce
# rendering work. Example: [140, 90, 55].
STARFIELD_DENSITY = [140, 90, 55]

# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------
# Approximate number of astronomical units in one light-year. Used by
# list views and distance calculations. Adjust if your internal units change.
LY_TO_AU = 63241.0

# ---------------------------------------------------------------------------
# Icon / map visuals
# ---------------------------------------------------------------------------
# Fractional variance applied to event-by-event icon size randomization.
# Typical: 0.0 (no variance) .. 0.75. Controls make_map_symbol_item/randomized_px.
ICON_SIZE_VARIANCE_MAX = 0.50

# ---------------------------------------------------------------------------
# Travel / gameplay tunables
# ---------------------------------------------------------------------------
# Timing knobs used by TravelFlow (ms)
TRAVEL_PHASE_WRAP_MS = 5000
TRAVEL_CRUISE_MS_PER_AU = 3000  # Increased from 500ms to 3000ms per AU for better visual feedback
TRAVEL_WARP_MS_PER_LY = 500
TRAVEL_DRIP_STEP_MS = 10

# Fuel model weights used by TravelFlow planning
TRAVEL_WRAP_FUEL_WEIGHT = 2.00
TRAVEL_CRUISE_FUEL_WEIGHT = 1.00

# Shared fuel model constants (single source of truth)
TRAVEL_FUEL_PER_AU = 1.0 / 5.0
TRAVEL_WARP_FUEL_PER_LY = 2.0
TRAVEL_WARP_FUEL_WEIGHT = 1.40
