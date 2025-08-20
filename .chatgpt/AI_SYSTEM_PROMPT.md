
**.chatgpt/AI_SYSTEM_PROMPT.md**
```markdown
# System Instructions for AI Assistants

You are assisting on the **Victurus** project.

1) **Mandatory repository review FIRST**
   - Navigate to: https://github.com/xclenvicturus/Victurus
   - Read the README, setup/requirements, and relevant source folders.
   - Rebuild context each session; do not rely on memory from previous asks.

2) **Editing policy**
   - Propose changes as **full file replacements for only the files you changed**.
   - Label each code block with the exact path of the file.
   - No diffs, no ellipses, no partial snippets.

3) **Delivery format**
   - Start with a concise **Plan** (what and why).
   - Then output **changed files in full**, one file per labeled code block.
   - End with **Run/validation steps** and a **commit message** suggestion.

4) **When access fails**
   - If the repo cannot be read, request either (a) specific files, or (b) a zipped project snapshot.
   - If still blocked, proceed with best effort and clearly state assumptions.

5) **Quality & safety**
   - Match project style and structure.
   - Keep changes minimal, documented, and testable.
   - Provide a brief manual test plan and commands to run.

Always follow this file and `AI_CONTRIBUTING.md` when working on this project.