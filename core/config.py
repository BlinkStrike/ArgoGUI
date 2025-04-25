import yaml
from pathlib import Path

CONFIG_PATH = Path.home() / ".cloudflared" / "config.yml"

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    return {}

def save_config(config):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        yaml.safe_dump(config, f)


def update_config(new_entries: dict):
    config = load_config()
    config.update(new_entries)
    save_config(config)