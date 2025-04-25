# ArgoGUI

ArgoGUI is a Python-based graphical user interface for managing Argo Tunnels by Cloudflare. It simplifies the process of creating, configuring, and controlling Cloudflare tunnels, making secure remote access to local or internal services easy and user-friendly.

## Core Features
- **Manage Cloudflare Argo Tunnels**: Easily create, list, and delete tunnels.
- **Start/Stop Tunnels**: Control tunnel lifecycles directly from the interface.
- **View Tunnel Status**: See real-time status and logs of your tunnels.
- **Configuration Management**: Edit and manage tunnel configurations using a simple UI.
- **Web & CLI Interfaces**: Use either a web-based GUI or command-line interface according to your preference.
- **Environment Management**: Store and use environment variables securely via `.env`.
- **Extensible Core**: Modular codebase for easy extension and customization.

## Project Structure
```
ArgoGUI/
│   .env                # Environment variables
│   cli_ui.py           # Command-line interface
│   web_ui.py           # Web-based interface
│   run.py              # Main entry point
│   requirements.txt    # Python dependencies
│
└───core/
    │   config.py       # Configuration management
    │   manager.py      # Core logic and management
    │   utils.py        # Utility functions
```

## Getting Started
1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Run the application:**
   ```bash
   python run.py
   ```

## Requirements
See `requirements.txt` for a list of dependencies.

## License
This project is provided as-is for demonstration and educational purposes.
