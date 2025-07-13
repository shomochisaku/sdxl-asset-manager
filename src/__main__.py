"""Main entry point for running SDXL Asset Manager as a module.

This allows the CLI to be invoked with 'python -m src' command.
"""

from src.cli import cli  # type: ignore[attr-defined]

if __name__ == '__main__':
    cli()
