import subprocess
import yaml
from pathlib import Path
import os
import shutil
import platform
import sys
import ctypes

CONFIG_PATH = Path.home() / ".cloudflared" / "config.yml"

def list_tunnels():
    result = subprocess.run(["cloudflared", "tunnel", "list", "--output", "json"],
                            capture_output=True, text=True)
    return result.stdout

def create_tunnel(name: str):
    subprocess.run(["cloudflared", "tunnel", "create", name])

def delete_tunnel(tunnel_id: str):
    subprocess.run(["cloudflared", "tunnel", "delete", tunnel_id])

def get_service_config_dir():
    import platform
    import os
    system = platform.system().lower()
    if system == "windows":
        # Service runs as LocalSystem, home is C:\Windows\System32\config\systemprofile
        return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "config", "systemprofile", ".cloudflared")
    else:
        # Service usually runs as root
        return os.path.expanduser("/root/.cloudflared")

def update_service_config(tunnel_uuid=None, credentials_file=None, url=None):
    """Update service config and restart if needed"""
    import yaml, os, shutil
    service_dir = get_service_config_dir()
    config_path = os.path.join(service_dir, "config.yml")
    os.makedirs(service_dir, exist_ok=True)

    # Read existing config if it exists
    cfg = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                cfg = yaml.safe_load(f) or {}
        except Exception:
            pass

    # Update config with new values
    if tunnel_uuid:
        cfg['tunnel'] = tunnel_uuid
    if credentials_file:
        cfg['credentials-file'] = str(credentials_file)
        # Also copy credentials file to service dir
        creds_dest = os.path.join(service_dir, os.path.basename(credentials_file))
        shutil.copy2(credentials_file, creds_dest)
    if url:
        cfg['url'] = url

    # Write updated config
    with open(config_path, 'w') as f:
        yaml.safe_dump(cfg, f)

    return config_path

def install_service(config_path=None, tunnel_uuid=None, credentials_file=None, url=None):
    import platform
    import shutil
    import os
    import sys
    import subprocess

    # First ensure we have a valid config
    if config_path is None:
        config_path = update_service_config(tunnel_uuid, credentials_file, url)

    system = platform.system().lower()
    if system == "windows":
        import ctypes
        exe = shutil.which("cloudflared.exe") or "cloudflared.exe"
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False

        args = f'service install --config "{config_path}"'
        if not is_admin:
            print("Administrator privileges are required to install the service. Prompting for elevation...")
            try:
                # First install the service
                ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
                print("Service installed. Starting service...")
                # Then start it
                ctypes.windll.shell32.ShellExecuteW(None, "runas", "sc.exe", "start Cloudflared", None, 1)
            except Exception as e:
                print(f"Failed to elevate privileges: {e}")
        else:
            subprocess.run([exe, "service", "install", "--config", config_path])
            subprocess.run(["sc", "start", "Cloudflared"])
    else:
        if os.geteuid() != 0:
            print("Root privileges are required to install the service. Prompting for sudo...")
            try:
                subprocess.run(["sudo", "cloudflared", "service", "install", "--config", config_path])
                subprocess.run(["sudo", "systemctl", "start", "cloudflared"])
            except Exception as e:
                print(f"Failed to escalate privileges: {e}")
        else:
            subprocess.run(["cloudflared", "service", "install", "--config", config_path])
            subprocess.run(["systemctl", "start", "cloudflared"])

def copy_or_symlink_config_and_creds(src_config, src_creds):
    import os, shutil, platform
    service_dir = get_service_config_dir()
    os.makedirs(service_dir, exist_ok=True)
    config_dest = os.path.join(service_dir, "config.yml")
    creds_dest = os.path.join(service_dir, os.path.basename(src_creds))
    system = platform.system().lower()
    # Try symlink, fallback to copy on Windows
    def _safe_link_or_copy(src, dst):
        try:
            if os.path.exists(dst):
                os.remove(dst)
            if system == "windows":
                shutil.copy2(src, dst)
            else:
                os.symlink(src, dst)
        except Exception:
            shutil.copy2(src, dst)
    _safe_link_or_copy(src_config, config_dest)
    _safe_link_or_copy(src_creds, creds_dest)
    return config_dest, creds_dest

def verify_service_config(tunnel_uuid, creds_file, url=None):
    import yaml, os
    config_path = get_service_config_dir() + "/config.yml"
    problems = []
    auto_fixed = False
    ok = True
    if not os.path.exists(config_path):
        problems.append(f"Config file not found: {config_path}")
        ok = False
    else:
        with open(config_path, 'r') as f:
            try:
                cfg = yaml.safe_load(f)
            except Exception as e:
                cfg = None
                problems.append(f"Config file not valid YAML: {e}")
                ok = False
        if cfg:
            if str(cfg.get('tunnel')) != str(tunnel_uuid):
                problems.append(f"Config 'tunnel' does not match: {cfg.get('tunnel')} != {tunnel_uuid}")
                ok = False
            if str(cfg.get('credentials-file')) != str(creds_file):
                problems.append(f"Config 'credentials-file' does not match: {cfg.get('credentials-file')} != {creds_file}")
                ok = False
            if url and str(cfg.get('url')) != str(url):
                problems.append(f"Config 'url' does not match: {cfg.get('url')} != {url}")
                ok = False
    if not ok:
        # Optionally auto-fix
        fix_service_config(tunnel_uuid, creds_file, url)
        auto_fixed = True
    return ok, problems, auto_fixed

def fix_service_config(tunnel_uuid, creds_file, url=None):
    import yaml, os
    config_path = get_service_config_dir() + "/config.yml"
    cfg = {
        'tunnel': tunnel_uuid,
        'credentials-file': str(creds_file)
    }
    if url:
        cfg['url'] = url
    with open(config_path, 'w') as f:
        yaml.safe_dump(cfg, f)
    return config_path

def diagnose_service_config():
    import yaml, os
    config_path = get_service_config_dir() + "/config.yml"
    output = []
    if not os.path.exists(config_path):
        output.append(f"Config file not found: {config_path}")
        return '\n'.join(output)
    with open(config_path, 'r') as f:
        try:
            cfg = yaml.safe_load(f)
        except Exception as e:
            return f"Config file not valid YAML: {e}"
    output.append(f"Config file: {config_path}")
    output.append(f"tunnel: {cfg.get('tunnel')}")
    output.append(f"credentials-file: {cfg.get('credentials-file')}")
    output.append(f"url: {cfg.get('url')}")
    # Check if credentials file exists
    creds_file = cfg.get('credentials-file')
    if not creds_file or not os.path.exists(creds_file):
        output.append(f"Credentials file missing: {creds_file}")
    else:
        output.append(f"Credentials file found: {creds_file}")
    # Optionally: check tunnel status
    try:
        info = tunnel_info(cfg.get('tunnel'))
        output.append(f"Tunnel info: {info}")
    except Exception as e:
        output.append(f"Could not get tunnel info: {e}")
    return '\n'.join(output)


def start_service():
    import platform
    import subprocess
    import os
    system = platform.system().lower()
    if system == "windows":
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False
        if not is_admin:
            print("Administrator privileges required. Prompting for elevation...")
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "sc.exe", "start Cloudflared", None, 1)
        else:
            subprocess.run(["sc", "start", "Cloudflared"])
    else:
        if os.geteuid() != 0:
            print("Root privileges required. Prompting for sudo...")
            subprocess.run(["sudo", "systemctl", "start", "cloudflared"])
        else:
            subprocess.run(["systemctl", "start", "cloudflared"])

def uninstall_service():
    """Uninstall the cloudflared service"""
    system = platform.system().lower()
    if system == "windows":
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False
        if not is_admin:
            print("Administrator privileges required. Prompting for elevation...")
            try:
                # First stop the service
                ctypes.windll.shell32.ShellExecuteW(None, "runas", "sc.exe", "stop Cloudflared", None, 1)
                # Then remove it
                exe = shutil.which("cloudflared.exe") or "cloudflared.exe"
                ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, "service uninstall", None, 1)
            except Exception as e:
                print(f"Failed to elevate privileges: {e}")
        else:
            subprocess.run(["sc", "stop", "Cloudflared"])
            subprocess.run(["cloudflared", "service", "uninstall"])
    else:
        if os.geteuid() != 0:
            print("Root privileges required. Prompting for sudo...")
            try:
                subprocess.run(["sudo", "systemctl", "stop", "cloudflared"])
                subprocess.run(["sudo", "cloudflared", "service", "uninstall"])
            except Exception as e:
                print(f"Failed to escalate privileges: {e}")
        else:
            subprocess.run(["systemctl", "stop", "cloudflared"])
            subprocess.run(["cloudflared", "service", "uninstall"])

def clean_service_files():
    """Remove all service config files"""
    import os
    import shutil
    service_dir = get_service_config_dir()
    if os.path.exists(service_dir):
        try:
            shutil.rmtree(service_dir)
            print(f"Removed service config directory: {service_dir}")
        except Exception as e:
            print(f"Failed to remove service config directory: {e}")

def stop_service():
    import platform
    import subprocess
    import os
    system = platform.system().lower()
    if system == "windows":
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False
        if not is_admin:
            print("Administrator privileges required. Prompting for elevation...")
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "sc.exe", "stop Cloudflared", None, 1)
        else:
            subprocess.run(["sc", "stop", "Cloudflared"])
    else:
        if os.geteuid() != 0:
            print("Root privileges required. Prompting for sudo...")
            subprocess.run(["sudo", "systemctl", "stop", "cloudflared"])
        else:
            subprocess.run(["systemctl", "stop", "cloudflared"])

def restart_service():
    import platform
    import subprocess
    import os
    system = platform.system().lower()
    if system == "windows":
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False
        if not is_admin:
            print("Administrator privileges required. Prompting for elevation...")
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "sc.exe", "stop Cloudflared", None, 1)
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "sc.exe", "start Cloudflared", None, 1)
        else:
            subprocess.run(["sc", "stop", "Cloudflared"])
            subprocess.run(["sc", "start", "Cloudflared"])
    else:
        if os.geteuid() != 0:
            print("Root privileges required. Prompting for sudo...")
            subprocess.run(["sudo", "systemctl", "restart", "cloudflared"])
        else:
            subprocess.run(["systemctl", "restart", "cloudflared"])

def is_service_running():
    import platform
    import subprocess
    system = platform.system().lower()
    if system == "windows":
        # Try using PowerShell to check service status
        try:
            cmd = [
                "powershell",
                "-Command",
                "Get-Service -Name Cloudflared | Select-Object -ExpandProperty Status"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            status = result.stdout.strip().lower()
            return status == "running"
        except Exception:
            return False
    else:
        try:
            result = subprocess.run(["systemctl", "is-active", "cloudflared"], capture_output=True, text=True)
            return "active" in result.stdout
        except Exception:
            return False

def cloudflared_login():
    import platform
    import shutil
    import subprocess
    system = platform.system().lower()
    if system == "windows":
        exe = shutil.which("cloudflared.exe") or "cloudflared.exe"
        proc = subprocess.run([exe, "login"], check=True)
    else:
        exe = shutil.which("cloudflared") or "cloudflared"
        proc = subprocess.run([exe, "login"], check=True)
    return proc.returncode == 0

def create_config_file(tunnel_uuid, credentials_file, url=None, warp_routing=False):
    """
    Create a config.yml for the tunnel. If url is provided, configures app proxy; else, private network.
    """
    import yaml
    from pathlib import Path
    config = {
        'tunnel': tunnel_uuid,
        'credentials-file': str(credentials_file)
    }
    if url:
        config['url'] = url
    if warp_routing:
        config['warp-routing'] = {'enabled': True}
    config_path = Path.home() / ".cloudflared" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        yaml.safe_dump(config, f)
    return str(config_path)

def add_dns_route(tunnel, hostname):
    import platform
    import shutil
    import subprocess
    system = platform.system().lower()
    exe = shutil.which("cloudflared.exe") if system == "windows" else shutil.which("cloudflared")
    exe = exe or ("cloudflared.exe" if system == "windows" else "cloudflared")
    return subprocess.run([exe, "tunnel", "route", "dns", tunnel, hostname], check=True)

def add_ip_route(ip_cidr, tunnel):
    import platform
    import shutil
    import subprocess
    system = platform.system().lower()
    exe = shutil.which("cloudflared.exe") if system == "windows" else shutil.which("cloudflared")
    exe = exe or ("cloudflared.exe" if system == "windows" else "cloudflared")
    return subprocess.run([exe, "tunnel", "route", "ip", "add", ip_cidr, tunnel], check=True)

def show_ip_routes():
    import platform
    import shutil
    import subprocess
    system = platform.system().lower()
    exe = shutil.which("cloudflared.exe") if system == "windows" else shutil.which("cloudflared")
    exe = exe or ("cloudflared.exe" if system == "windows" else "cloudflared")
    return subprocess.run([exe, "tunnel", "route", "ip", "show"], check=True)

def run_tunnel(tunnel):
    import platform
    import shutil
    import subprocess
    system = platform.system().lower()
    exe = shutil.which("cloudflared.exe") if system == "windows" else shutil.which("cloudflared")
    exe = exe or ("cloudflared.exe" if system == "windows" else "cloudflared")
    return subprocess.run([exe, "tunnel", "run", tunnel], check=True)

def tunnel_info(tunnel):
    import platform
    import shutil
    import subprocess
    system = platform.system().lower()
    exe = shutil.which("cloudflared.exe") if system == "windows" else shutil.which("cloudflared")
    exe = exe or ("cloudflared.exe" if system == "windows" else "cloudflared")
    return subprocess.run([exe, "tunnel", "info", tunnel], check=True)
