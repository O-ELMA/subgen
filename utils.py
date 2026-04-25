import os
from pathlib import Path

import config


def update_env_file(key_value):
    """Write or update NANO_GPT_KEY in .env file."""
    env_path = Path(".env")
    lines = []
    key_found = False

    if env_path.exists():
        with open(env_path, "r") as f:
            lines = f.readlines()

    for i, line in enumerate(lines):
        if line.strip().startswith("NANO_GPT_KEY="):
            lines[i] = f"NANO_GPT_KEY={key_value}\n"
            key_found = True
            break

    if not key_found:
        lines.append(f"NANO_GPT_KEY={key_value}\n")

    with open(env_path, "w") as f:
        f.writelines(lines)


def ensure_api_key(get_key_callback):
    """Check if API key exists; if not, call get_key_callback to obtain it.

    The callback must return a non-empty string (the API key).
    Once obtained, the key is set in config.NANOGPT_API_KEY,
    os.environ['NANO_GPT_KEY'], and persisted to .env.
    """
    if config.NANOGPT_API_KEY:
        return

    key = get_key_callback()
    if not key:
        raise ValueError("API key cannot be empty.")

    config.NANOGPT_API_KEY = key
    os.environ["NANO_GPT_KEY"] = key
    update_env_file(key)
