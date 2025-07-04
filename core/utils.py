import subprocess
import platform

import requests
import shutil
import tempfile
import os

def check_cloudflared_installed():
    try:
        result = subprocess.run(["cloudflared", "--version"], capture_output=True, text=True)
        return "cloudflared" in result.stdout.lower()
    except FileNotFoundError:
        return False

def download_and_install_cloudflared(install_dir=None):
    """
    Downloads and installs the latest cloudflared for Windows, Linux, or macOS from the official GitHub releases.
    Args:
        install_dir (str): Directory to install cloudflared binary into. If None, uses OS-appropriate default.
    Returns:
        str: Path to the installed cloudflared binary or error message.
    """
    import sys
    import stat
    import tarfile

    api_url = "https://api.github.com/repos/cloudflare/cloudflared/releases/latest"
    try:
        resp = requests.get(api_url, timeout=15)
        resp.raise_for_status()
        release = resp.json()
        assets = release.get("assets", [])
        system = platform.system().lower()
        arch = platform.machine().lower()

        # Map platform.machine() to asset arch
        if arch in ("x86_64", "amd64"):
            arch = "amd64"
        elif arch in ("aarch64", "arm64"):
            arch = "arm64"
        elif arch in ("armv7l", "armv6l", "arm"):
            arch = "arm"
        elif arch in ("i386", "i686", "386"):
            arch = "386"

        # Determine asset name and install location
        if system == "windows":
            asset_suffix = f"windows-{arch}.exe"
            bin_name = "cloudflared.exe"
            if not install_dir:
                install_dir = os.getcwd()
        elif system == "linux":
            asset_suffix = f"linux-{arch}"
            bin_name = "cloudflared"
            if not install_dir:
                install_dir = os.path.expanduser("~/.local/bin")
                os.makedirs(install_dir, exist_ok=True)
        elif system == "darwin":
            asset_suffix = f"darwin-{arch}.tgz"
            bin_name = "cloudflared"
            if not install_dir:
                install_dir = os.path.expanduser("~/.local/bin")
                os.makedirs(install_dir, exist_ok=True)
        else:
            return f"Unsupported OS: {system}"

        asset = None
        # Find the correct asset
        for a in assets:
            if system == "darwin":
                if a["name"].endswith(asset_suffix):
                    asset = a
                    break
            else:
                if a["name"].endswith(asset_suffix):
                    asset = a
                    break
        if not asset:
            return f"Could not find cloudflared binary for {system}/{arch} in the latest release."
        url = asset["browser_download_url"]
        local_path = os.path.join(install_dir, bin_name)

        if system == "darwin":
            # Download and extract .tgz
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".tgz") as tmpf:
                    shutil.copyfileobj(r.raw, tmpf)
                    tmpf.flush()
                    tmpf.close()
                    with tarfile.open(tmpf.name, "r:gz") as tar:
                        for member in tar.getmembers():
                            if member.name.endswith("cloudflared"):
                                member.name = os.path.basename(member.name)
                                tar.extract(member, install_dir)
                                break
                    os.remove(tmpf.name)
            os.chmod(local_path, os.stat(local_path).st_mode | stat.S_IEXEC)
            return f"cloudflared installed at {local_path}"
        else:
            # Download binary
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(local_path, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
            os.chmod(local_path, os.stat(local_path).st_mode | stat.S_IEXEC)
            return f"cloudflared installed at {local_path}"
    except Exception as e:
        return f"Failed to download/install cloudflared: {e}"

def get_os_info():
    return platform.system(), platform.release()


def run_command(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        return result.stdout or result.stderr
    except Exception as e:
        return str(e)
