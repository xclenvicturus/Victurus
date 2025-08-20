# AI_CONTRIBUTING

Repo URL: https://github.com/xclenvicturus/Victurus

## Goal
When I (the AI) am asked to debug, add features, or refactor, I must **first review this repository** and then propose **complete, ready-to-paste file updates**—not partial snippets.

## Always-Check Rule
Before producing any analysis or code:
1) Open the repo at the URL above and read:
   - README, setup scripts, requirements, and top-level entry points.
   - Source directories (recursively) that are relevant to the task.
2) Build a quick mental map of modules, dependencies, and data flow.
3) Confirm target branch (default to `main` unless specified).

If the repo cannot be accessed, ask for a zipped copy or the exact files.

## Output Requirements
- **Changed files only, full content**: For every file you modify, output the **entire file**, not diffs.
- **File labeling**: Each file must be in its own code block and labeled with the exact path, e.g.:

  **engine/window_togglers.py**
  ```python
  # full updated file content here