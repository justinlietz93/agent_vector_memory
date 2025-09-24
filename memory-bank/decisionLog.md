# Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-09-23 | Added `if __name__ == "__main__": main()` guard to `setup.py` | Setup wizard wasn’t executing after virtualenv re-exec due to missing entry point |
| 2025-09-23 | Routed ensure-collection via `python -m vector_memory.cli.main` | Using the current interpreter keeps CLI commands inside the active virtualenv |
| 2025-09-23 | Injected package parent into `PYTHONPATH` before CLI calls | Ensures `vector_memory` imports succeed without editable install |
| 2025-09-23 | Auto-install CLI dependency `requests` and share repo paths with subprocesses | Prevents users from needing manual pip/debug steps during setup post-actions |
| 2025-09-24 | Added http(s) URL validation prompts for Ollama/Qdrant inputs | Stops accidental yes/no answers from overwriting endpoint defaults |
