# Standard File Headers for Victurus

## Overview

All Python files in the Victurus project must have standardized headers that include the file path and a descriptive docstring. This ensures consistent documentation across the codebase and makes it easier for developers and AI assistants to understand file purposes and functionality.

## Required Format

Every Python file must start with:

```python
# /relative/path/to/file.py

"""File Title

Brief description of what this file does.
• Bullet point describing key functionality
• Another bullet point for additional features  
• Third bullet point for other important aspects
• More bullet points as needed for complex files
"""

from __future__ import annotations
```

### Format Rules

1. **Path Comment**: Must be the very first line, using `# /` followed by the relative path from project root
2. **Docstring**: Must immediately follow the path comment with a descriptive title and bullet-point functionality list
3. **Import Statement**: Standard `from __future__ import annotations` follows the docstring
4. **No Blank Lines**: Between path comment and docstring
5. **One Blank Line**: Between docstring and imports

## Examples

### Simple Utility File
```python
# /ui/utils/docks.py

"""Dock Widget Utilities

Helper functions for creating and managing dock widgets with state persistence.
• Register dock widgets for state management
• Handle visibility change callbacks
• Provide consistent dock configuration
"""

from __future__ import annotations
```

### Complex System File
```python
# /ui/maps/system.py

"""System Map Display Widget

SystemMapWidget for displaying solar system layouts with interactive elements.
• Central star positioning with orbit rings for planets
• Station and moon orbital mechanics around parent bodies
• Resource node visualization on outer system rings
• Animated starfield overlay and background rendering
• Travel path visualization and progress indicators
• Entity resolution for map-list synchronization
• Deterministic asset assignment using GIF-based graphics
"""

from __future__ import annotations
```

### Dialog File
```python
# /ui/dialogs/load_game_dialog.py

"""Load Game Dialog

Dialog for loading saved games with metadata display and management.
• Tree widget showing saves with timestamps and details
• Load, delete, and rename functionality
• New game creation option
• Sortable columns for organization
• Save validation and error handling
"""

from __future__ import annotations
```

## Guidelines for Writing Good Headers

### Path Comments
- Always use forward slashes, even on Windows
- Path should be relative to project root
- No leading slash (start with folder name or file name for root files)

### Docstring Titles
- Use concise, descriptive titles that capture the file's primary purpose
- Avoid redundant words like "Module" or "File"
- Use title case for the main title

### Bullet Points
- Start each point with a bullet (•) and a space
- Use present tense, active voice
- Focus on what the file provides or enables
- Order from most important to least important functionality
- Keep points concise but descriptive

### Common Patterns

**For UI Components**: Focus on user-visible functionality and interaction patterns
**For System Components**: Emphasize data flow, processing, and integration points  
**For Dialogs**: List main actions and features available to the user
**For Utilities**: Describe helper functions and what they enable
**For Data/Database**: Focus on data management and access patterns
**For Controllers**: Emphasize coordination and business logic

## AI Instructions Integration

When creating new Python files, AI assistants should automatically include this standard header format. The format ensures:

- Immediate context about file location in project
- Clear understanding of file purpose and functionality
- Consistent documentation style across all files
- Easy navigation and maintenance for developers

## Enforcement

- All existing files have been updated to use this standard format
- New files must follow this format from creation
- Code reviews should verify header compliance
- The format is part of the project's coding standards

---

*This standard was established during the September 2025 codebase standardization effort to improve code maintainability and developer experience.*
