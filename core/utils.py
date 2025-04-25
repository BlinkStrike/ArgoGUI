import subprocess
import platform

def check_cloudflared_installed():
    try:
        result = subprocess.run(["cloudflared", "--version"], capture_output=True, text=True)
        return "cloudflared" in result.stdout.lower()
    except FileNotFoundError:
        return False

def get_os_info():
    return platform.system(), platform.release()


def run_command(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        return result.stdout or result.stderr
    except Exception as e:
        return str(e)
