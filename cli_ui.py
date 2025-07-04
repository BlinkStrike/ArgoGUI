from rich.console import Console
from rich.table import Table
from core import manager

console = Console()

def main():
    while True:
        console.print("\n[bold cyan]Cloudflared Tunnel CLI[/bold cyan]", style="green")
        console.print("[1] List Tunnels\n[2] Cloudflared Login\n[3] Create Tunnel\n[4] Delete Tunnel\n[5] Start Service\n[6] Stop Service\n[7] Restart Service\n[8] Service Status\n[9] Install cloudflared\n[10] Install as Service\n[11] Uninstall Service\n[12] Clean Service Files\n[13] Exit")
        choice = input("Select an option: ")

        if choice == "1":

            tunnels = manager.list_tunnels()
            console.print(tunnels)
        elif choice == "2":
            try:
                manager.cloudflared_login()
                console.print("cloudflared login completed. Follow the browser instructions.")
            except Exception as e:
                console.print(f"Failed to run cloudflared login: {e}")
        elif choice == "3":
            name = input("Enter tunnel name: ")
            manager.create_tunnel(name)
            # Get tunnel UUID from tunnel list
            import json, os
            tunnels_json = manager.list_tunnels()
            try:
                tunnels = json.loads(tunnels_json)
                tunnel = next((t for t in tunnels if t['name'] == name), None)
            except Exception:
                tunnel = None
            if not tunnel:
                console.print("Tunnel creation failed or tunnel not found.")
                return
            tunnel_id = tunnel['id']
            credentials_file = tunnel.get('credentials_file', os.path.expanduser(f"~/.cloudflared/{tunnel_id}.json"))
            url = input("Enter application URL to proxy (e.g. http://localhost:8000), or leave blank for private network: ")
            warp_routing = False
            if not url:
                warp_routing = input("Enable warp-routing for private network? (y/n): ").strip().lower() == 'y'
            config_path = manager.create_config_file(tunnel_id, credentials_file, url if url else None, warp_routing)
            console.print(f"Config file created at: {config_path}")
            # Offer to copy/symlink config/creds for service
            do_copy = input("Copy/symlink config and credentials for service account? (y/n): ").strip().lower() == 'y'
            if do_copy:
                try:
                    from core import manager as mgr
                    config_dest, creds_dest = mgr.copy_or_symlink_config_and_creds(config_path, credentials_file)
                    console.print(f"Config and credentials copied/symlinked to service directory:\n{config_dest}\n{creds_dest}")
                    # Update service config with new tunnel
                    mgr.update_service_config(tunnel_id, creds_dest, url if url else None)
                    console.print("Service config updated with new tunnel.")
                    
                    # Ask to restart service
                    do_restart = input("Restart service to apply new tunnel config? (y/n): ").strip().lower() == 'y'
                    if do_restart:
                        mgr.restart_service()
                        console.print("Service restarted with new tunnel config.")
                except Exception as e:
                    console.print(f"Failed to copy/symlink config or credentials: {e}")
            hostname = input("Enter hostname for DNS routing (optional, e.g. app.example.com): ")
            if hostname:
                try:
                    manager.add_dns_route(tunnel_id, hostname)
                    console.print(f"DNS route added: {hostname} -> tunnel {tunnel_id}")
                except Exception as e:
                    console.print(f"Failed to add DNS route: {e}")
            ip_cidr = input("Enter IP/CIDR for IP routing (optional, e.g. 10.0.0.0/24): ")
            if ip_cidr:
                try:
                    manager.add_ip_route(ip_cidr, tunnel_id)
                    console.print(f"IP route added: {ip_cidr} -> tunnel {tunnel_id}")
                except Exception as e:
                    console.print(f"Failed to add IP route: {e}")
            run_now = input("Would you like to run the tunnel now? (y/n): ").strip().lower() == 'y'
            if run_now:
                try:
                    manager.run_tunnel(tunnel_id)
                except Exception as e:
                    console.print(f"Failed to run tunnel: {e}")
            else:
                console.print(f"To start routing, run: cloudflared tunnel run {tunnel_id}")
        elif choice == "4":
            tunnel_id = input("Enter tunnel ID: ")
            manager.delete_tunnel(tunnel_id)
        elif choice == "5":
            manager.start_service()
            console.print("Service started")
        elif choice == "6":
            manager.stop_service()
            console.print("Service stopped")
        elif choice == "7":
            manager.restart_service()
            console.print("Service restarted")
        elif choice == "8":
            status = manager.is_service_running()
            console.print(f"Service running: {status}")
        elif choice == "9":
            from core.utils import download_and_install_cloudflared
            result = download_and_install_cloudflared()
            console.print(result)
        elif choice == "10":
            try:
                from core import manager as mgr
                # Try to get current tunnel info from config
                src_config = os.path.expanduser("~/.cloudflared/config.yml")
                tunnel_uuid = None
                creds_file = None
                url = None
                if os.path.exists(src_config):
                    with open(src_config, 'r') as f:
                        cfg = yaml.safe_load(f)
                        if cfg:
                            tunnel_uuid = cfg.get('tunnel')
                            creds_file = cfg.get('credentials-file')
                            url = cfg.get('url')
                
                # Install service with current tunnel config if available
                manager.install_service(tunnel_uuid=tunnel_uuid, credentials_file=creds_file, url=url)
                console.print(f"cloudflared service installed and configured with tunnel {tunnel_uuid if tunnel_uuid else '(none)'}")
            except Exception as e:
                console.print(f"Failed to install service: {e}")
        elif choice == "11":
            try:
                from core import manager as mgr
                src_config = os.path.expanduser("~/.cloudflared/config.yml")
                # Try to find a credentials file in config
                import yaml
                creds_file = None
                if os.path.exists(src_config):
                    with open(src_config, 'r') as f:
                        cfg = yaml.safe_load(f)
                        creds_file = cfg.get('credentials-file')
                if not creds_file or not os.path.exists(creds_file):
                    creds_file = input("Enter path to credentials file (e.g. ~/.cloudflared/<UUID>.json): ")
                config_dest, creds_dest = mgr.copy_or_symlink_config_and_creds(src_config, creds_file)
                console.print(f"Config and credentials copied/symlinked to service directory:\n{config_dest}\n{creds_dest}")
            except Exception as e:
                console.print(f"Failed to copy/symlink config or credentials: {e}")
        elif choice == "12":
            try:
                from core import manager as mgr
                output = mgr.diagnose_service_config()
                console.print(output)
                
                # Offer to update service config with current tunnel
                do_update = input("Update service config with current tunnel? (y/n): ").strip().lower() == 'y'
                if do_update:
                    src_config = os.path.expanduser("~/.cloudflared/config.yml")
                    if os.path.exists(src_config):
                        with open(src_config, 'r') as f:
                            cfg = yaml.safe_load(f)
                            if cfg:
                                tunnel_uuid = cfg.get('tunnel')
                                creds_file = cfg.get('credentials-file')
                                url = cfg.get('url')
                                if tunnel_uuid and creds_file:
                                    mgr.update_service_config(tunnel_uuid, creds_file, url)
                                    console.print("Service config updated.")
                                    do_restart = input("Restart service to apply new config? (y/n): ").strip().lower() == 'y'
                                    if do_restart:
                                        mgr.restart_service()
                                        console.print("Service restarted with new config.")
                                else:
                                    console.print("No tunnel configuration found in current config.")
            except Exception as e:
                console.print(f"Failed to diagnose service config: {e}")
        elif choice == "11":
            try:
                if input("Are you sure you want to uninstall the cloudflared service? (y/n): ").strip().lower() == 'y':
                    manager.uninstall_service()
                    console.print("Service uninstalled.")
            except Exception as e:
                console.print(f"Failed to uninstall service: {e}")
        elif choice == "12":
            try:
                if input("Are you sure you want to remove all service config files? (y/n): ").strip().lower() == 'y':
                    manager.clean_service_files()
                    console.print("Service config files removed.")
            except Exception as e:
                console.print(f"Failed to clean service files: {e}")
        elif choice == "13":
            break
        else:
            console.print("Invalid option")
