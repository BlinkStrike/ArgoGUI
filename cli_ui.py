from rich.console import Console
from rich.table import Table
from core import manager

console = Console()

def main():
    while True:
        console.print("\n[bold cyan]Cloudflared Tunnel CLI[/bold cyan]", style="green")
        console.print("[1] List Tunnels\n[2] Create Tunnel\n[3] Delete Tunnel\n[4] Start Service\n[5] Stop Service\n[6] Service Status\n[7] Exit")
        choice = input("Select an option: ")

        if choice == "1":
            tunnels = manager.list_tunnels()
            console.print(tunnels)
        elif choice == "2":
            name = input("Enter tunnel name: ")
            manager.create_tunnel(name)
        elif choice == "3":
            tunnel_id = input("Enter tunnel ID: ")
            manager.delete_tunnel(tunnel_id)
        elif choice == "4":
            manager.start_service()
            console.print("Service started")
        elif choice == "5":
            manager.stop_service()
            console.print("Service stopped")
        elif choice == "6":
            status = manager.is_service_running()
            console.print(f"Service running: {status}")
        elif choice == "7":
            break
        else:
            console.print("Invalid option")
