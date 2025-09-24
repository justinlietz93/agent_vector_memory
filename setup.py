#!/usr/bin/env python3
"""
Vector Memory Setup Script.

Interactive setup for configuring environment, collections, and usage modes.
Generates .env file and optionally runs initialization steps (install launcher, ensure collection, start watcher).
"""

import os
import sys
from pathlib import Path
import subprocess

def in_venv() -> bool:
    """Check if currently in a virtual environment."""
    return (hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))

def create_venv() -> str:
    """Create .venv and return python path."""
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("Creating virtual environment in .venv...")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_path)])
    if sys.platform == "win32":
        python_path = venv_path / "Scripts" / "python.exe"
    else:
        python_path = venv_path / "bin" / "python"
    return str(python_path)

def re_exec_in_venv() -> None:
    """Re-execute the script in .venv."""
    python_path = create_venv()
    os.execv(python_path, [python_path, __file__] + sys.argv[1:])

# Virtual environment setup at the very top (stdlib only)
if not in_venv():
    print("Vector Memory Setup - Virtual Environment Check")
    use_venv = input("Use/create virtual environment (.venv) for installations? [Y/n]: ").strip().lower() in ('', 'y', 'yes')
    if use_venv:
        print("Creating and switching to virtual environment...")
        re_exec_in_venv()

# Now safe: import non-stdlib and proceed
import shutil
from typing import Optional

# Stdlib .env parsing
def load_env_from_file(env_path: Path) -> dict:
    """Load .env as dict (ignore comments)."""
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    env[key] = value.strip('"\'')
    return env

def set_env_key(env_path: Path, key: str, value: str) -> None:
    """Write key=value to .env (append if new, overwrite if exists)."""
    env = load_env_from_file(env_path)
    env[key] = value
    with open(env_path, 'w') as f:
        for k, v in env.items():
            f.write(f"{k}={v}\n")

def print_step(message: str) -> None:
    print(f"\n{'='*50}")
    print(f"{message}")
    print(f"{'='*50}")

def ask_yes_no(question: str, default: bool = True) -> bool:
    default_str = " [Y/n]" if default else " [y/N]"
    response = input(f"{question}{default_str}: ").strip().lower()
    return response in ('y', 'yes') if response else default

def ask_choice(question: str, options: list[str], default: int = 0) -> str:
    print(f"\n{question}")
    for i, opt in enumerate(options):
        marker = " (default)" if i == default else ""
        print(f"  {i}. {opt}{marker}")
    while True:
        try:
            choice = input("Enter number: ").strip()
            if not choice:
                return options[default]
            idx = int(choice)
            if 0 <= idx < len(options):
                return options[idx]
            print(f"Invalid choice. Must be 0-{len(options)-1}")
        except ValueError:
            print("Invalid input. Enter a number.")

def ask_path(question: str, default: Optional[str] = None) -> str:
    default_str = f" [{default}]" if default else ""
    path = input(f"{question}{default_str}: ").strip()
    return default if not path and default else os.path.expanduser(path)

def locate_chat_paths() -> list[str]:
    """Search for potential chat log directories."""
    print("Searching for chat log directories...")
    candidates = []
    home = Path.home()
    patterns = [
        home / ".config" / "Code" / "User" / "globalStorage" / "**" / "tasks",
        home / ".vscode" / "**" / "tasks",
        home / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "**" / "tasks",
    ]
    for pattern in patterns:
        print(f"Searching: {pattern}")
        candidates.extend(
            str(path)
            for path in pattern.glob("*")
            if path.is_dir()
            and any(
                (path / f).exists()
                for f in ["ui_messages.json", "api_conversation_history.json"]
            )
        )
    print(f"Found {len(candidates)} candidates.")
    if not candidates:
        print("Try running: find ~ -name 'ui_messages.json' 2>/dev/null | head -5")
    return sorted(candidates, key=os.path.getmtime, reverse=True)

def ensure_launcher_installed() -> None:
    if not shutil.which("vector-memory"):
        print("\nInstalling vector-memory launcher...")
        subprocess.check_call(["bash", "tools/install-vector-memory.sh"])
        os.environ["PATH"] = f"{os.path.expanduser('~/.local/bin')}:{os.environ.get('PATH', '')}"
    print("Launcher ready.")

def ensure_collection(collection_name: str) -> None:
    print(f"\nEnsuring collection '{collection_name}'...")
    subprocess.check_call(["vector-memory", "ensure-collection", "--name", collection_name])

def start_watcher(chat_dir: str, collection_name: str, background: bool = True) -> None:
    cmd = ["bash", "tools/watch_roo_code.sh"]
    if background:
        cmd = ["nohup"] + cmd + [">", "watcher.log", "2>&1", "&"]
    env = os.environ.copy()
    env["ROO_TASKS_DIR"] = chat_dir
    env["MEMORY_COLLECTION_NAME"] = collection_name
    subprocess.Popen(cmd, env=env)
    print(f"Watcher started for '{chat_dir}' (collection: {collection_name}). Logs: watcher.log")

def install_requirements() -> None:
    if ask_yes_no("Install requirements (UI deps)?", default=True):
        ui_req = Path("ui/requirements.txt")
        if ui_req.exists():
            print("Installing UI requirements...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(ui_req)])
        else:
            print("No ui/requirements.txt; skipping.")
        print("Requirements installed.")

def setup_agent_prompts(agent_choice: str) -> None:
    prompts_dir = Path("docs/system-prompts")
    root = Path(".")
    if agent_choice == "Claude Code":
        src = prompts_dir / "CLAUDE.md"
        dst = root / "CLAUDE.md"
        if src.exists():
            shutil.move(str(src), str(dst))
            print("Moved CLAUDE.md to root.")
        else:
            print("CLAUDE.md not found; skipping.")

    elif agent_choice == "Cursor AI IDE":
        src = prompts_dir / "vector-mem.cursorrules"
        dst = root / "vector-mem.cursorrules"
        if src.exists():
            shutil.copy2(src, dst)
            print("Copied vector-mem.cursorrules to root.")
        else:
            print("vector-mem.cursorrules not found; skipping.")

    elif agent_choice == "Roo-Code VSCode Agent Extension":
        src = prompts_dir / "vector-mem.roo-code.md"
        if src.exists():
            print(f"Prompt ready: {src}. Manually add to Roo Code GUI.")
        else:
            print("vector-mem.roo-code.md not found; skipping.")

    elif agent_choice == "VSCode Copilot Agent":
        src = prompts_dir / "vscode-vector-mem.instructions.md"
        dst = root / "vscode-vector-mem.instructions.md"
        if src.exists():
            shutil.copy2(src, dst)
            print("Copied vscode-vector-mem.instructions.md to root.")
        else:
            print("vscode-vector-mem.instructions.md not found; skipping.")

    elif agent_choice == "Windsurf AI IDE":
        src = prompts_dir / "vector-mem.windsurfrules"
        dst = root / "vector-mem.windsurfrules"
        if src.exists():
            shutil.copy2(src, dst)
            print("Copied vector-mem.windsurfrules to root.")
        else:
            print("vector-mem.windsurfrules not found; skipping.")

def main() -> None:
    env_path = Path(".env")
    env = load_env_from_file(env_path) if env_path.exists() else {}

    print_step("Environment Basics")
    defaults = {
        "collection": env.get("MEMORY_COLLECTION_NAME", "project_memory"),
        "ollama_url": env.get("OLLAMA_URL", "http://localhost:11434"),
        "qdrant_url": env.get("QDRANT_URL", "http://localhost:6333"),
        "model": "mxbai-embed-large"  # Fixed
    }
    print(f"Current defaults: Collection={defaults['collection']}, Ollama={defaults['ollama_url']}, Qdrant={defaults['qdrant_url']}, Model={defaults['model']}")
    custom_env = ask_yes_no("Custom environment settings?", default=False)
    if custom_env:
        defaults["collection"] = input(f"Primary collection [ {defaults['collection']} ]: ").strip() or defaults["collection"]
        defaults["ollama_url"] = input(f"Ollama URL [ {defaults['ollama_url']} ]: ").strip() or defaults['ollama_url']
        defaults["qdrant_url"] = input(f"Qdrant URL [ {defaults['qdrant_url']} ]: ").strip() or defaults['qdrant_url']
        print(f"Model remains {defaults['model']}; pull with 'ollama pull {defaults['model']}' if needed.")
    collection_name, ollama_url, qdrant_url, model = defaults["collection"], defaults["ollama_url"], defaults["qdrant_url"], defaults["model"]

    print_step("Agent & Chat Tailing")
    agents = [
        "Claude Code (moves CLAUDE.md to root)",
        "Cursor AI IDE (copies vector-mem.cursorrules to root)",
        "Roo-Code VSCode Agent Extension (manual GUI for vector-mem.roo-code.md)",
        "VSCode Copilot Agent (copies vscode-vector-mem.instructions.md to root)",
        "Windsurf AI IDE (copies vector-mem.windsurfrules to root)",
        "None (skip)"
    ]
    agent_choice = ask_choice("Agent environment?", agents, default=5)

    enable_tailing = ask_yes_no("Enable chat log tailing?", default=False)
    chat_dir = None
    if enable_tailing:
        locate = ask_yes_no("Auto-locate or explicit path?", default=True)
        if locate:
            candidates = locate_chat_paths()
            if candidates:
                print("Top candidates (recent first):")
                for i, cand in enumerate(candidates[:3]):
                    print(f"  {i}. {cand}")
                choice = ask_choice("Select?", candidates[:3] + ["Custom..."])
                if choice == "Custom...":
                    chat_dir = ask_path("Enter path:")
                else:
                    chat_dir = choice
            else:
                chat_dir = ask_path("Enter path (e.g., ~/.config/Code/.../tasks):")
        else:
            chat_dir = ask_path("Enter path:")

    print_step("Usage Mode")
    modes = [
        "All (MCP + UI + Passive watcher)",
        "MCP (agent tools)",
        "UI only",
        "Passive watcher only"
    ]
    mode = ask_choice("Usage?", modes, default=0)
    use_mcp = "All" in mode or "MCP" in mode
    use_ui = "All" in mode or "UI" in mode
    use_passive = "All" in mode or "Passive" in mode

    print_step("Confirm Choices")
    summary = f"""
- Collection: {collection_name}
- Ollama: {ollama_url}
- Qdrant: {qdrant_url}
- Model: {model}
- Agent: {agent_choice}
- Chat Tailing: {'Enabled (' + chat_dir + ')' if chat_dir else 'Disabled'}
- Mode: {mode}
"""
    print(summary)
    confirm = ask_yes_no("Write .env and apply? [Y/n]:", default=True)
    if not confirm:
        print("Setup cancelled.")
        sys.exit(0)

    # Apply
    config = {
        "MEMORY_COLLECTION_NAME": collection_name,
        "EMBED_MODEL": model,
        "OLLAMA_URL": ollama_url,
        "QDRANT_URL": qdrant_url,
    }
    if chat_dir:
        config["ROO_TASKS_DIR"] = chat_dir
        config["STORE_SETTINGS"] = input("Full content (all) or redacted? [redacted]: ").strip().lower()
        if config["STORE_SETTINGS"] not in ("all", "full"):
            config["STORE_SETTINGS"] = "redacted"

    for key, value in config.items():
        set_env_key(env_path, key, value)

    print("\n.env updated!")

    setup_agent_prompts(agent_choice)

    # Run actions (optional)
    if ask_yes_no("Run actions now (launcher, requirements, collection, services)?", default=True):
        ensure_launcher_installed()
        install_requirements()
        ensure_collection(collection_name)
        if use_passive and chat_dir:
            start_watcher(chat_dir, collection_name)
        if use_ui:
            subprocess.Popen([sys.executable, "ui/app.py"])
        if use_mcp:
            print("MCP ready: Use 'vector-memory-mcp' or import mcp/api.py")

    print_step("Setup complete! Source .env for env vars.")