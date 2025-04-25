import sys
from core.utils import check_cloudflared_installed

if __name__ == "__main__":
    if not check_cloudflared_installed():
        print("cloudflared is not installed. Please install it first.")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python run.py [cli|web]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "cli":
        import cli_ui
        cli_ui.main()
    elif mode == "web":
        import web_ui
        web_ui.main()
    else:
        print("Invalid mode. Use 'cli' or 'web'.")