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
import importlib
from urllib.parse import urlparse
from typing import Optional

STEP_COUNTER = 0


def safe_input(prompt: str) -> str:
    """Input wrapper that handles KeyboardInterrupt with a clean exit."""
    try:
        return input(prompt)
    except KeyboardInterrupt:
        print("\nSetup cancelled by user.")
        sys.exit(1)

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

def ensure_python_package(package: str, import_name: Optional[str] = None) -> None:
    """Ensure a Python package is installed in the active environment."""
    name = import_name or package
    try:
        importlib.import_module(name)
        return
    except ModuleNotFoundError:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def extend_env_with_repo(env: dict[str, str]) -> dict[str, str]:
    """Augment environment so subprocesses can import vector_memory reliably."""
    repo_root = Path(__file__).resolve().parent
    package_parent = str(repo_root.parent)
    separator = os.pathsep

    existing_py = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{package_parent}{separator}{existing_py}" if existing_py else package_parent
    )

    python_bin_dir = str(Path(sys.executable).parent)
    existing_path = env.get("PATH", "")
    env["PATH"] = (
        f"{python_bin_dir}{separator}{existing_path}" if existing_path else python_bin_dir
    )

    return env

# Virtual environment setup at the very top (stdlib only)
if not in_venv():
    print("Vector Memory Setup - Virtual Environment Check")
    use_venv = safe_input("Use/create virtual environment (.venv) for installations? [Y/n]: ").strip().lower() in ('', 'y', 'yes')
    if use_venv:
        print("Creating and switching to virtual environment...")
        re_exec_in_venv()

# Now safe: import non-stdlib and proceed
import shutil

# Stdlib .env parsing
def load_env_from_file(env_path: Path) -> dict:
    """Load .env as dict (ignore comments)."""
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
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

def print_banner() -> None:
    print("=" * 50)
    print("Vector Memory Setup")
    print("=" * 50)

def print_step(message: str) -> None:
    print(f"\n{'='*50}")
    print(f"{message}")
    print(f"{'='*50}")

def print_section(title: str) -> None:
    global STEP_COUNTER
    STEP_COUNTER += 1
    print_step(f"Step {STEP_COUNTER}: {title}")

def ask_yes_no(question: str, default: bool = True) -> bool:
    default_str = " [Y/n]" if default else " [y/N]"
    response = safe_input(f"{question}{default_str}: ").strip().lower()
    return response in ('y', 'yes') if response else default

def ask_choice(question: str, options: list[str], default: int = 0) -> str:
    print(f"\n{question}")
    for i, opt in enumerate(options):
        marker = " (default)" if i == default else ""
        print(f"  {i}. {opt}{marker}")
    while True:
        try:
            choice = safe_input("Enter number: ").strip()
            if not choice:
                return options[default]
            idx = int(choice)
            if 0 <= idx < len(options):
                return options[idx]
            print(f"Invalid choice. Must be 0-{len(options)-1}")
        except ValueError:
            print("Invalid input. Enter a number.")

def ask_text(question: str, default: Optional[str] = None, required: bool = False) -> str:
    default_str = f" [{default}]" if default else ""
    while True:
        value = safe_input(f"{question}{default_str}: ").strip()
        if value:
            return value
        if default is not None and not required:
            return default
        if not required:
            return ""
        print("Input is required. Press Ctrl+C to cancel setup.")

def ask_path(question: str, default: Optional[str] = None) -> str:
    value = ask_text(question, default)
    return os.path.expanduser(value) if value else ""

def is_valid_http_url(value: str) -> bool:
    if not value:
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)

def ask_url(question: str, default: str) -> str:
    while True:
        value = ask_text(question, default).strip()
        if not value:
            print("URL is required. Please enter a full http(s) endpoint.")
            continue
        if is_valid_http_url(value):
            return value
        print("Invalid URL. Please provide a full http(s) URL, e.g. http://localhost:11434")

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

def ensure_launcher_installed(force: bool = False) -> None:
    """Install the launcher if missing or when forced."""
    launcher_script = Path("tools/install-vector-memory.sh")
    if not launcher_script.exists():
        print("Launcher script tools/install-vector-memory.sh not found; skipping install.")
        return

    launcher_available = shutil.which("vector-memory") is not None
    if launcher_available and not force:
        print("Launcher already available on PATH. Skipping install.")
        return

    print("\nInstalling vector-memory launcher...")
    subprocess.check_call(["bash", str(launcher_script)])
    os.environ["PATH"] = f"{os.path.expanduser('~/.local/bin')}:{os.environ.get('PATH', '')}"
    print("Launcher ready.")

def ensure_collection(collection_name: str) -> None:
    print(f"\nEnsuring collection '{collection_name}'...")
    ensure_python_package("requests")
    env = extend_env_with_repo(os.environ.copy())
    subprocess.check_call([
        sys.executable,
        "-m",
        "vector_memory.cli.main",
        "ensure-collection",
        "--name",
        collection_name,
    ], env=env)

def start_watcher(chat_dir: str, collection_name: str, background: bool = True) -> None:
    script_path = Path("tools/watch_roo_code.sh")
    if not script_path.exists():
        print("Watcher script tools/watch_roo_code.sh not found; skipping.")
        return

    ensure_python_package("requests")
    env = extend_env_with_repo(os.environ.copy())
    env["ROO_TASKS_DIR"] = chat_dir
    env["MEMORY_COLLECTION_NAME"] = collection_name

    if background:
        with open("watcher.log", "a", encoding="utf-8") as log_file:
            subprocess.Popen(["bash", str(script_path)], env=env, stdout=log_file, stderr=subprocess.STDOUT)
        print(f"Watcher started for '{chat_dir}' (collection: {collection_name}). Logs: watcher.log")
    else:
        subprocess.check_call(["bash", str(script_path)], env=env)

def install_requirements(force: Optional[bool] = None) -> None:
    if force is None:
        should_install = ask_yes_no("Install requirements (UI deps)?", default=True)
    else:
        should_install = force

    if not should_install:
        print("Skipped UI requirements install.")
        return

    ui_req = Path("ui/requirements.txt")
    if ui_req.exists():
        print("Installing UI requirements...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(ui_req)])
        print("Requirements installed.")
    else:
        print("No ui/requirements.txt; skipping UI dependency install.")


def get_suggested_actions(use_ui: bool, use_passive: bool, use_mcp: bool, chat_dir: Optional[str]) -> list[str]:
    actions: list[str] = ["Install/refresh vector-memory launcher", "Ensure collection in Qdrant"]
    if use_ui:
        actions.extend(["Install UI requirements", "Launch Qt UI"])
    if use_passive and chat_dir:
        actions.append("Start passive watcher")
    if use_mcp:
        actions.append("Review MCP tooling readiness")
    return actions


def build_summary(
    collection_name: str,
    ollama_url: str,
    qdrant_url: str,
    model: str,
    agent_choice: str,
    chat_dir: Optional[str],
    mode: str,
    suggested_actions: list[str],
) -> str:
    chat_status = f"Enabled ({chat_dir})" if chat_dir else "Disabled"
    lines = [
        f"• Collection          : {collection_name}",
        f"• Ollama endpoint     : {ollama_url}",
        f"• Qdrant endpoint     : {qdrant_url}",
        f"• Embedding model     : {model}",
        f"• Agent prompt assets : {agent_choice}",
        f"• Chat tailing        : {chat_status}",
        f"• Usage mode          : {mode}",
    ]
    if suggested_actions:
        lines.append(f"• Planned post-steps  : {', '.join(suggested_actions)}")
    return "\n".join(lines)


def prompt_actions(
    collection_name: str,
    use_passive: bool,
    chat_dir: Optional[str],
    use_ui: bool,
    use_mcp: bool,
) -> dict[str, bool]:
    actions: dict[str, bool] = {
        "launcher": ask_yes_no("Install/refresh vector-memory launcher now?", default=True),
        "requirements": use_ui and ask_yes_no("Install UI requirements now?", default=True),
        "ensure_collection": ask_yes_no(f"Ensure collection '{collection_name}' now?", default=True),
        "start_watcher": use_passive and chat_dir and ask_yes_no("Start passive watcher now?", default=True),
        "launch_ui": use_ui and ask_yes_no("Launch Qt UI now?", default=False),
        "show_mcp": use_mcp and ask_yes_no("Show MCP tooling guidance now?", default=True),
    }
    return actions


def execute_actions(
    actions: dict[str, bool],
    collection_name: str,
    chat_dir: Optional[str],
    use_passive: bool,
    use_ui: bool,
    use_mcp: bool,
) -> None:
    if actions.get("launcher"):
        ensure_launcher_installed(force=True)

    if actions.get("requirements") and use_ui:
        install_requirements(force=True)

    if actions.get("ensure_collection"):
        ensure_collection(collection_name)

    if actions.get("start_watcher") and use_passive and chat_dir:
        start_watcher(chat_dir, collection_name)

    if actions.get("launch_ui") and use_ui:
        subprocess.Popen([sys.executable, "ui/app.py"])

    if actions.get("show_mcp") and use_mcp:
        print("MCP ready: Use 'vector-memory-mcp' CLI or import vector_memory.mcp.api")

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
    global STEP_COUNTER
    STEP_COUNTER = 0

    print_banner()
    env_path = Path(".env")
    env = load_env_from_file(env_path) if env_path.exists() else {}

    print_section("Environment Basics")
    defaults = {
        "collection": env.get("MEMORY_COLLECTION_NAME", "project_memory"),
        "ollama_url": env.get("OLLAMA_URL", "http://localhost:11434"),
        "qdrant_url": env.get("QDRANT_URL", "http://localhost:6333"),
        "model": "mxbai-embed-large"  # Fixed
    }
    print(f"Current defaults: Collection={defaults['collection']}, Ollama={defaults['ollama_url']}, Qdrant={defaults['qdrant_url']}, Model={defaults['model']}")
    custom_env = ask_yes_no("Custom environment settings?", default=False)
    if custom_env:
        defaults["collection"] = ask_text("Primary collection", defaults["collection"]) or defaults["collection"]
        defaults["ollama_url"] = ask_url("Ollama URL", defaults["ollama_url"]) or defaults["ollama_url"]
        defaults["qdrant_url"] = ask_url("Qdrant URL", defaults["qdrant_url"]) or defaults["qdrant_url"]
        print(f"Model remains {defaults['model']}; pull with 'ollama pull {defaults['model']}' if needed.")
    collection_name, ollama_url, qdrant_url, model = defaults["collection"], defaults["ollama_url"], defaults["qdrant_url"], defaults["model"]

    print_section("Agent & Chat Tailing")
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
                options = list(candidates[:3]) + ["Custom..."]
                choice = ask_choice("Select?", options)
                chat_dir = ask_path("Enter path:") if choice == "Custom..." else choice
            else:
                chat_dir = ask_path("Enter path (e.g., ~/.config/Code/.../tasks):")
        else:
            chat_dir = ask_path("Enter path:")
        chat_dir = chat_dir or None

    print_section("Usage Mode")
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

    suggested_actions = get_suggested_actions(use_ui, use_passive, use_mcp, chat_dir)

    print_section("Confirm Choices")
    print(build_summary(
        collection_name,
        ollama_url,
        qdrant_url,
        model,
        agent_choice,
        chat_dir,
        mode,
        suggested_actions,
    ))

    confirm = ask_yes_no("Write .env and apply now?", default=True)
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
        store_option = ask_choice("Watcher storage mode?", ["Redacted (default)", "All content"], default=0)
        config["STORE_SETTINGS"] = "all" if store_option.lower().startswith("all") else "redacted"

    for key, value in config.items():
        set_env_key(env_path, key, value)

    print("\n.env updated!")

    setup_agent_prompts(agent_choice)

    # Run actions (optional)
    print_section("Post-Setup Actions")
    actions = prompt_actions(collection_name, use_passive, chat_dir, use_ui, use_mcp)
    execute_actions(actions, collection_name, chat_dir, use_passive, use_ui, use_mcp)

    print_step("Setup complete! Source .env for env vars.")


if __name__ == "__main__":
    main()