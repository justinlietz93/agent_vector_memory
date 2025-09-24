#!/usr/bin/env python3
"""
Vector Memory Setup Script.

Interactive setup for configuring environment, collections, and usage modes.
Generates .env file and optionally runs initialization steps (install launcher, ensure collection, start watcher).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv, set_key
except ImportError:
    print("Installing python-dotenv for .env handling...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])
    from dotenv import load_dotenv, set_key

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
    """Search for potential chat log directories (Roo/VSCode patterns)."""
    candidates = []
    home = Path.home()
    # Common VSCode/Roo paths
    patterns = [
        home / ".config" / "Code" / "User" / "globalStorage" / "**" / "tasks",
        home / ".vscode" / "**" / "tasks",
        home / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "**" / "tasks",  # Windows
    ]
    for pattern in patterns:
        candidates.extend(
            str(path)
            for path in pattern.glob("*")
            if path.is_dir()
            and any(
                (path / f).exists()
                for f in ["ui_messages.json", "api_conversation_history.json"]
            )
        )
    return sorted(candidates, key=os.path.getmtime, reverse=True)  # Most recent first

def ensure_launcher_installed() -> None:
    """Run the install script if launcher not available."""
    import shutil
    if not shutil.which("vector-memory"):
        print("\nInstalling vector-memory launcher...")
        subprocess.check_call(["bash", "tools/install-vector-memory.sh"])
        os.environ["PATH"] = f"{os.path.expanduser('~/.local/bin')}:{os.environ.get('PATH', '')}"
    print("Launcher ready.")

def ensure_collection(collection_name: str) -> None:
    """Ensure the primary collection exists."""
    print(f"\nEnsuring collection '{collection_name}'...")
    subprocess.check_call(["vector-memory", "ensure-collection", "--name", collection_name])

def start_watcher(chat_dir: str, collection_name: str, background: bool = True) -> None:
    """Start the chat watcher (optionally in background)."""
    cmd = ["bash", "tools/watch_roo_code.sh"]
    if background:
        cmd = ["nohup"] + cmd + [">", "watcher.log", "2>&1", "&"]
    env = os.environ.copy()
    env["ROO_TASKS_DIR"] = chat_dir
    env["MEMORY_COLLECTION_NAME"] = collection_name
    subprocess.Popen(cmd, env=env)
    print(f"Watcher started for '{chat_dir}' (collection: {collection_name}). Logs: watcher.log")

def install_requirements() -> None:
    """Install project requirements if user confirms."""
    if ask_yes_no("Install requirements (UI deps from ui/requirements.txt and editable core install)?", default=True):
        # UI requirements
        ui_req = Path("ui/requirements.txt")
        if ui_req.exists():
            print("Installing UI requirements...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(ui_req)])
        else:
            print("No ui/requirements.txt found; skipping UI deps.")

        # Core editable install (optional for pip mode)
        if ask_yes_no("Install core package in editable mode (pip install -e .)?", default=False):
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", "."])
        print("Requirements installed.")

def setup_agent_prompts(agent_choice: str) -> None:
    """Copy/move agent-specific prompts to root based on choice."""
    prompts_dir = Path("docs/system-prompts")
    root = Path(".")

    if agent_choice == "Claude Code":
        src = prompts_dir / "CLAUDE.md"
        dst = root / "CLAUDE.md"
        if src.exists():
            shutil.move(src, dst)
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
            print(f"Prompt ready: {src}. Manually add to Roo Code GUI settings.")
        else:
            print("vector-mem.roo-code.md not found; skipping.")

    elif agent_choice == "VSCode Copilot Agent":
        src = prompts_dir / "vscode-vector-mem.instructions.md"
        dst = root / "vscode-vector-mem.instructions.md"
        if src.exists():
            shutil.copy2(src, dst)
            print(
                "Copied vscode-vector-mem.instructions.md to root for Copilot instructions."
            )
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

    else:
        print("Skipping agent prompt setup.")

def main() -> None:
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    print_step("Welcome to Vector Memory Setup!")
    print("This script will guide you through configuration. We'll generate/update .env and set up based on your choices.")

    # 1. Primary collection name
    default_coll = os.getenv("MEMORY_COLLECTION_NAME", "project_memory")
    collection_name = ask_choice(
        "What should the primary collection be named?",
        ["project_memory", "my_app_mem", "Custom..."],
        default=0
    )
    if collection_name == "Custom...":
        collection_name = input("Enter custom name: ").strip() or default_coll

    # 2. Embedding model (fixed)
    model = "mxbai-embed-large"  # Only supported
    print(f"Embedding model: {model} (default; pull via 'ollama pull {model}' if needed)")

    # 3. Ollama URL
    ollama_url = ask_choice(
        "Ollama URL?",
        ["http://localhost:11434", "Custom..."],
        default=0
    )
    if ollama_url == "Custom...":
        ollama_url = input("Enter Ollama URL (e.g., http://host:port): ").strip() or "http://localhost:11434"

    # 4. Qdrant URL
    qdrant_url = ask_choice(
        "Qdrant URL?",
        ["http://localhost:6333", "Custom..."],
        default=0
    )
    if qdrant_url == "Custom...":
        qdrant_url = input("Enter Qdrant URL (e.g., http://host:port): ").strip() or "http://localhost:6333"

    # 5. Agent environment
    agents = [
        "Claude Code (CLI agent; moves CLAUDE.md to root)",
        "Cursor AI IDE (copies vector-mem.cursorrules to root)",
        "Roo-Code VSCode Agent Extension (manual GUI add for vector-mem.roo-code.md)",
        "VSCode Copilot Agent (copies vscode-vector-mem.instructions.md to root)",
        "Windsurf AI IDE (copies vector-mem.windsurfrules to root)",
        "None (skip)"
    ]
    agent_choice = ask_choice("Which agent environment are you using?", agents, default=5)

    # 6. Enable chat log tailing?
    enable_tailing = ask_yes_no("Enable automatic chat log ingestion (tailing ui_messages.json)?", default=False)
    chat_dir = None
    if enable_tailing:
        locate = ask_yes_no("Enter path explicitly, or let system locate (searches VSCode/Roo paths)?", default=True)
        if locate:
            candidates = locate_chat_paths()
            if candidates:
                print("Found candidates (most recent first):")
                for i, cand in enumerate(candidates[:5]):
                    print(f"  {i}. {cand}")
                choice = ask_choice("Select or Custom...", candidates[:5] + ["Custom..."])
                if choice == "Custom...":
                    chat_dir = ask_path("Enter chat tasks dir:", candidates[0] if candidates else None)
                else:
                    chat_dir = choice
            else:
                print("No candidates found. Entering manually...")
                chat_dir = ask_path("Enter chat tasks dir (e.g., ~/.config/Code/.../tasks):")
        else:
            chat_dir = ask_path("Enter chat tasks dir:")

    # 7. Usage mode
    modes = [
        "MCP (tools for agents like Roo/Claude)",
        "UI (run the graphical interface)",
        "Passive (local upsert: run watcher for chat logs)"
    ]
    mode = ask_choice("How will you use Vector Memory?", modes, default=0)
    use_mcp = "MCP" in mode
    use_ui = "UI" in mode
    use_passive = "Passive" in mode
    run_now = ask_yes_no("Run setup actions now (install launcher, ensure collection, start services)?", default=True)

    # Generate .env
    config = {
        "MEMORY_COLLECTION_NAME": collection_name,
        "EMBED_MODEL": model,
        "OLLAMA_URL": ollama_url,
        "QDRANT_URL": qdrant_url,
    }
    if chat_dir:
        config["ROO_TASKS_DIR"] = chat_dir
        config["STORE_SETTINGS"] = "all" if ask_yes_no("Store full chat content (no redaction)?", default=False) else "redacted"

    for key, value in config.items():
        set_key(env_path, key, value)

    print(f"\nGenerated/updated .env with: {config}")

    # Setup agent prompts
    setup_agent_prompts(agent_choice)

    if run_now:
        # Install launcher
        ensure_launcher_installed()

        # Install requirements
        install_requirements()

        # Ensure collection
        ensure_collection(collection_name)

        # Start based on mode
        if use_passive and chat_dir:
            start_watcher(chat_dir, collection_name)
        if use_ui:
            subprocess.Popen([sys.executable, "ui/app.py"])
        if use_mcp:
            print("MCP ready: Use 'vector-memory-mcp' or import from mcp/api.py")

    print_step("Setup complete! Review .env and run 'source .env' if needed.")

if __name__ == "__main__":
    main()