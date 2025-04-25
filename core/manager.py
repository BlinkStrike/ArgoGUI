import subprocess
import yaml
from pathlib import Path

CONFIG_PATH = Path.home() / ".cloudflared" / "config.yml"

def list_tunnels():
    result = subprocess.run(["cloudflared", "tunnel", "list", "--output", "json"],
                            capture_output=True, text=True)
    return result.stdout

def create_tunnel(name: str):
    subprocess.run(["cloudflared", "tunnel", "create", name])

def delete_tunnel(tunnel_id: str):
    subprocess.run(["cloudflared", "tunnel", "delete", tunnel_id])

def install_service():
    subprocess.run(["cloudflared", "service", "install"])

def start_service():
    subprocess.run(["sudo", "systemctl", "start", "cloudflared"])

def stop_service():
    subprocess.run(["sudo", "systemctl", "stop", "cloudflared"])

def is_service_running():
    result = subprocess.run(["systemctl", "is-active", "cloudflared"], capture_output=True, text=True)
    return "active" in result.stdout
