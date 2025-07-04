import sys
from core.utils import check_cloudflared_installed

if __name__ == "__main__":
    if not check_cloudflared_installed():
        print("cloudflared is not installed.")
        choice = input("Would you like to download and install cloudflared automatically? (y/n): ").strip().lower()
        if choice == "y":
            from core.utils import download_and_install_cloudflared
            result = download_and_install_cloudflared()
            print(result)
            if not check_cloudflared_installed():
                print("cloudflared installation failed or not detected. Please install it manually.")
                sys.exit(1)
        else:
            print("Please install cloudflared manually and re-run this tool.")
            sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python run.py [cli|web|desktop]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "cli":
        import cli_ui
        cli_ui.main()
    elif mode == "web":
        import web_ui
        web_ui.main()
    elif mode == "desktop":
        import desktop_ui
        desktop_ui.main()
    else:
        print("Invalid mode. Use 'cli', 'web', or 'desktop'.")