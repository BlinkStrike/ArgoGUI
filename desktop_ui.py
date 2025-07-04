import sys
import json
import os
import yaml
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QTextEdit, QTabWidget, 
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QCheckBox, QGroupBox, QFormLayout, QDialog, QDialogButtonBox, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from core import manager
from core.utils import check_cloudflared_installed, download_and_install_cloudflared

class CommandThread(QThread):
    """Thread for running commands without blocking the UI"""
    output_ready = pyqtSignal(str)
    finished_with_status = pyqtSignal(bool, str)
    
    def __init__(self, command_func, *args, **kwargs):
        super().__init__()
        self.command_func = command_func
        self.args = args
        self.kwargs = kwargs
        # Connect finished signal to handle cleanup
        self.finished.connect(self.deleteLater)
        
    def run(self):
        try:
            result = self.command_func(*self.args, **self.kwargs)
            self.output_ready.emit(str(result))
            self.finished_with_status.emit(True, "")
        except Exception as e:
            self.finished_with_status.emit(False, str(e))

class TunnelInfoDialog(QDialog):
    def __init__(self, parent=None, tunnel_id=None, tunnel_info=None):
        super().__init__(parent)
        self.tunnel_id = tunnel_id
        self.setWindowTitle(f"Tunnel Information: {tunnel_id}")
        self.resize(700, 600)
        
        layout = QVBoxLayout()
        
        # Create tab widget for different sections
        self.tab_widget = QTabWidget()
        
        # Basic Info Tab
        basic_info_tab = QWidget()
        basic_info_layout = QVBoxLayout()
        
        # Tunnel ID and basic info
        basic_info_group = QGroupBox("Basic Information")
        basic_info_group.setObjectName("basic_info_group")  # Set object name for finding later
        basic_info_form = QFormLayout()
        
        # Extract basic info
        if tunnel_info:
            try:
                # Try to parse as JSON first
                try:
                    info_data = json.loads(tunnel_info) if isinstance(tunnel_info, str) else tunnel_info
                    
                    if isinstance(info_data, dict):
                        for key, value in info_data.items():
                            label = QLabel(str(value))
                            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                            basic_info_form.addRow(f"{key}:", label)
                    else:
                        # Display as text
                        info_text = QTextEdit()
                        info_text.setReadOnly(True)
                        info_text.setPlainText(str(tunnel_info))
                        basic_info_form.addRow(info_text)
                except json.JSONDecodeError:
                    # Not JSON, parse as text
                    lines = tunnel_info.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                            
                        if ':' in line:
                            key, value = line.split(':', 1)
                            label = QLabel(value.strip())
                            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                            basic_info_form.addRow(f"{key.strip()}:", label)
                        elif 'CONNECTOR ID' in line:
                            # This is a header for the connectors table
                            connector_label = QLabel("<b>" + line + "</b>")
                            connector_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                            basic_info_form.addRow("", connector_label)
                        else:
                            # Add as a plain line
                            label = QLabel(line)
                            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                            basic_info_form.addRow("", label)
            except Exception as e:
                error_label = QLabel(f"Error parsing tunnel info: {e}")
                basic_info_form.addRow(error_label)
                
                # Show raw info
                raw_text = QTextEdit()
                raw_text.setReadOnly(True)
                raw_text.setPlainText(str(tunnel_info))
                basic_info_form.addRow("Raw Info:", raw_text)
        else:
            loading_label = QLabel("Loading tunnel information...")
            basic_info_form.addRow(loading_label)
        
        basic_info_group.setLayout(basic_info_form)
        basic_info_layout.addWidget(basic_info_group)
        basic_info_tab.setLayout(basic_info_layout)
        
        # DNS Records Tab
        dns_tab = QWidget()
        dns_layout = QVBoxLayout()
        
        self.dns_records_group = QGroupBox("DNS Records")
        self.dns_records_group.setObjectName("dns_records_group")
        dns_records_layout = QVBoxLayout()
        
        # Add a refresh button
        refresh_dns_btn = QPushButton("Refresh DNS Records")
        refresh_dns_btn.clicked.connect(lambda: self.parent().fetch_dns_records(self.tunnel_id, self))
        dns_records_layout.addWidget(refresh_dns_btn)
        
        # Add a table for DNS records
        self.dns_records_table = QTableWidget()
        self.dns_records_table.setColumnCount(3)
        self.dns_records_table.setHorizontalHeaderLabels(["Hostname", "Type", "Target"])
        self.dns_records_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        dns_records_layout.addWidget(self.dns_records_table)
        
        # Add a label for loading/no records
        self.dns_status_label = QLabel("Loading DNS records...")
        dns_records_layout.addWidget(self.dns_status_label)
        
        self.dns_records_group.setLayout(dns_records_layout)
        dns_layout.addWidget(self.dns_records_group)
        dns_tab.setLayout(dns_layout)
        
        # Config Tab
        config_tab = QWidget()
        config_layout = QVBoxLayout()
        
        config_group = QGroupBox("Configuration")
        config_inner_layout = QVBoxLayout()
        
        self.config_text = QTextEdit()
        self.config_text.setReadOnly(True)
        self.config_text.setPlainText("Loading configuration...")
        config_inner_layout.addWidget(self.config_text)
        
        config_group.setLayout(config_inner_layout)
        config_layout.addWidget(config_group)
        config_tab.setLayout(config_layout)
        
        # Add tabs to tab widget
        self.tab_widget.addTab(basic_info_tab, "Basic Info")
        self.tab_widget.addTab(dns_tab, "DNS Records")
        self.tab_widget.addTab(config_tab, "Configuration")
        
        layout.addWidget(self.tab_widget)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        # Initial DNS records fetch
        if tunnel_id and parent:
            parent.fetch_dns_records(tunnel_id, self)
    
    def set_config_content(self, content):
        self.config_text.setPlainText(content)

class CreateTunnelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Tunnel")
        self.resize(500, 400)
        
        layout = QVBoxLayout()
        
        # Tunnel name
        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        form_layout.addRow("Tunnel Name:", self.name_input)
        
        # URL
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("e.g., http://localhost:8000")
        form_layout.addRow("Application URL (optional):", self.url_input)
        
        # Warp routing
        self.warp_routing = QCheckBox("Enable warp-routing for private network")
        form_layout.addRow("", self.warp_routing)
        
        # Hostname
        self.hostname_input = QLineEdit()
        self.hostname_input.setPlaceholderText("e.g., app.example.com")
        form_layout.addRow("Hostname for DNS routing (optional):", self.hostname_input)
        
        # IP/CIDR
        self.ip_cidr_input = QLineEdit()
        self.ip_cidr_input.setPlaceholderText("e.g., 10.0.0.0/24")
        form_layout.addRow("IP/CIDR for IP routing (optional):", self.ip_cidr_input)
        
        # Service options
        self.copy_for_service = QCheckBox("Copy/symlink config and credentials for service")
        self.copy_for_service.setChecked(True)
        form_layout.addRow("", self.copy_for_service)
        
        self.restart_service = QCheckBox("Restart service to apply new tunnel config")
        self.restart_service.setChecked(True)
        form_layout.addRow("", self.restart_service)
        
        # Run now
        self.run_now = QCheckBox("Run tunnel now")
        form_layout.addRow("", self.run_now)
        
        layout.addLayout(form_layout)
        
        # Status output
        self.status_output = QTextEdit()
        self.status_output.setReadOnly(True)
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self.status_output)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def get_values(self):
        return {
            "name": self.name_input.text(),
            "url": self.url_input.text() if self.url_input.text() else None,
            "warp_routing": self.warp_routing.isChecked(),
            "hostname": self.hostname_input.text() if self.hostname_input.text() else None,
            "ip_cidr": self.ip_cidr_input.text() if self.ip_cidr_input.text() else None,
            "copy_for_service": self.copy_for_service.isChecked(),
            "restart_service": self.restart_service.isChecked(),
            "run_now": self.run_now.isChecked()
        }
    
    def add_status(self, text):
        self.status_output.append(text)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cloudflare Argo Tunnel Manager")
        self.resize(800, 600)
        
        # Keep references to active threads
        self.active_threads = []
        
        # Track running tunnels
        self.running_tunnels = {}
        
        # Check if cloudflared is installed
        self.cloudflared_installed = check_cloudflared_installed()
        
        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Create tabs
        self.tabs = QTabWidget()
        
        # Dashboard tab
        dashboard_tab = QWidget()
        dashboard_layout = QVBoxLayout()
        
        # Status section
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("Cloudflared Status: " + 
                                   ("Installed" if self.cloudflared_installed else "Not Installed"))
        status_layout.addWidget(self.status_label)
        
        self.service_status_label = QLabel("Service Status: Checking...")
        status_layout.addWidget(self.service_status_label)
        
        status_buttons = QHBoxLayout()
        self.refresh_status_btn = QPushButton("Refresh Status")
        self.refresh_status_btn.clicked.connect(self.refresh_status)
        status_buttons.addWidget(self.refresh_status_btn)
        
        if not self.cloudflared_installed:
            self.install_btn = QPushButton("Install Cloudflared")
            self.install_btn.clicked.connect(self.install_cloudflared)
            status_buttons.addWidget(self.install_btn)
        
        status_layout.addLayout(status_buttons)
        status_group.setLayout(status_layout)
        dashboard_layout.addWidget(status_group)
        
        # Service control section
        service_group = QGroupBox("Service Control")
        service_layout = QHBoxLayout()
        
        self.start_service_btn = QPushButton("Start Service")
        self.start_service_btn.clicked.connect(self.start_service)
        service_layout.addWidget(self.start_service_btn)
        
        self.stop_service_btn = QPushButton("Stop Service")
        self.stop_service_btn.clicked.connect(self.stop_service)
        service_layout.addWidget(self.stop_service_btn)
        
        self.restart_service_btn = QPushButton("Restart Service")
        self.restart_service_btn.clicked.connect(self.restart_service)
        service_layout.addWidget(self.restart_service_btn)
        
        service_group.setLayout(service_layout)
        dashboard_layout.addWidget(service_group)
        
        # Output console
        console_group = QGroupBox("Console Output")
        console_layout = QVBoxLayout()
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        console_layout.addWidget(self.console_output)
        console_group.setLayout(console_layout)
        dashboard_layout.addWidget(console_group)
        
        dashboard_tab.setLayout(dashboard_layout)
        
        # Tunnels tab
        tunnels_tab = QWidget()
        tunnels_layout = QVBoxLayout()
        
        # Tunnel controls
        tunnel_controls = QHBoxLayout()
        
        self.refresh_tunnels_btn = QPushButton("Refresh Tunnels")
        self.refresh_tunnels_btn.clicked.connect(self.refresh_tunnels)
        tunnel_controls.addWidget(self.refresh_tunnels_btn)
        
        self.create_tunnel_btn = QPushButton("Create Tunnel")
        self.create_tunnel_btn.clicked.connect(self.show_create_tunnel_dialog)
        tunnel_controls.addWidget(self.create_tunnel_btn)
        
        self.delete_tunnel_btn = QPushButton("Delete Selected Tunnel")
        self.delete_tunnel_btn.clicked.connect(self.delete_selected_tunnel)
        tunnel_controls.addWidget(self.delete_tunnel_btn)
        
        tunnels_layout.addLayout(tunnel_controls)
        
        # Tunnels table
        self.tunnels_table = QTableWidget()
        self.tunnels_table.setColumnCount(5)
        self.tunnels_table.setHorizontalHeaderLabels(["ID", "Name", "Created", "Status", "Actions"])
        self.tunnels_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tunnels_layout.addWidget(self.tunnels_table)
        
        tunnels_tab.setLayout(tunnels_layout)
        
        # Advanced tab
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout()
        
        # Service installation
        install_service_group = QGroupBox("Service Installation")
        install_service_layout = QVBoxLayout()
        
        self.install_service_btn = QPushButton("Install as Service")
        self.install_service_btn.clicked.connect(self.install_service)
        install_service_layout.addWidget(self.install_service_btn)
        
        self.uninstall_service_btn = QPushButton("Uninstall Service")
        self.uninstall_service_btn.clicked.connect(self.uninstall_service)
        install_service_layout.addWidget(self.uninstall_service_btn)
        
        self.clean_service_files_btn = QPushButton("Clean Service Files")
        self.clean_service_files_btn.clicked.connect(self.clean_service_files)
        install_service_layout.addWidget(self.clean_service_files_btn)
        
        install_service_group.setLayout(install_service_layout)
        advanced_layout.addWidget(install_service_group)
        
        # Diagnostics
        diagnostics_group = QGroupBox("Diagnostics")
        diagnostics_layout = QVBoxLayout()
        
        self.diagnose_btn = QPushButton("Diagnose Service Config")
        self.diagnose_btn.clicked.connect(self.diagnose_service_config)
        diagnostics_layout.addWidget(self.diagnose_btn)
        
        diagnostics_group.setLayout(diagnostics_layout)
        advanced_layout.addWidget(diagnostics_group)
        
        advanced_tab.setLayout(advanced_layout)
        
        # Add tabs to tab widget
        self.tabs.addTab(dashboard_tab, "Dashboard")
        self.tabs.addTab(tunnels_tab, "Tunnels")
        self.tabs.addTab(advanced_tab, "Advanced")
        
        main_layout.addWidget(self.tabs)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Initialize status
        self.refresh_status()
        self.refresh_tunnels()
    
    def log(self, message):
        """Add message to console output"""
        self.console_output.append(message)
    
    def refresh_status(self):
        """Refresh cloudflared and service status"""
        self.cloudflared_installed = check_cloudflared_installed()
        self.status_label.setText("Cloudflared Status: " + 
                                  ("Installed" if self.cloudflared_installed else "Not Installed"))
        
        # Check service status in a thread
        thread = CommandThread(manager.is_service_running)
        thread.output_ready.connect(lambda result: 
            self.service_status_label.setText(f"Service Status: {'Running' if result.strip().lower() == 'true' else 'Not Running'}"))
        self.active_threads.append(thread)  # Keep reference
        thread.start()
    
    def install_cloudflared(self):
        """Install cloudflared"""
        self.log("Installing cloudflared...")
        thread = CommandThread(download_and_install_cloudflared)
        thread.output_ready.connect(self.log)
        thread.finished_with_status.connect(lambda success, error: 
            self.refresh_status() if success else self.log(f"Error: {error}"))
        self.active_threads.append(thread)  # Keep reference
        thread.start()
    
    def start_service(self):
        """Start cloudflared service"""
        self.log("Starting service...")
        thread = CommandThread(manager.start_service)
        thread.output_ready.connect(self.log)
        thread.finished_with_status.connect(lambda success, error: 
            self.refresh_status() if success else self.log(f"Error: {error}"))
        self.active_threads.append(thread)  # Keep reference
        thread.start()
    
    def stop_service(self):
        """Stop cloudflared service"""
        self.log("Stopping service...")
        thread = CommandThread(manager.stop_service)
        thread.output_ready.connect(self.log)
        thread.finished_with_status.connect(lambda success, error: 
            self.refresh_status() if success else self.log(f"Error: {error}"))
        self.active_threads.append(thread)  # Keep reference
        thread.start()
    
    def restart_service(self):
        """Restart cloudflared service"""
        self.log("Restarting service...")
        thread = CommandThread(manager.restart_service)
        thread.output_ready.connect(self.log)
        thread.finished_with_status.connect(lambda success, error: 
            self.refresh_status() if success else self.log(f"Error: {error}"))
        self.active_threads.append(thread)  # Keep reference
        thread.start()
    
    def refresh_tunnels(self):
        """Refresh tunnels list"""
        self.log("Refreshing tunnels...")
        thread = CommandThread(manager.list_tunnels)
        thread.output_ready.connect(self.update_tunnels_table)
        self.active_threads.append(thread)  # Keep reference
        thread.start()
    
    def update_tunnels_table(self, tunnels_json):
        """Update tunnels table with data"""
        try:
            tunnels = json.loads(tunnels_json)
            self.tunnels_table.setRowCount(len(tunnels))
            
            for row, tunnel in enumerate(tunnels):
                tunnel_id = tunnel.get('id', 'N/A')
                
                # ID
                id_item = QTableWidgetItem(tunnel_id)
                self.tunnels_table.setItem(row, 0, id_item)
                
                # Name
                name_item = QTableWidgetItem(tunnel.get('name', 'N/A'))
                self.tunnels_table.setItem(row, 1, name_item)
                
                # Created
                created_item = QTableWidgetItem(tunnel.get('created_at', 'N/A'))
                self.tunnels_table.setItem(row, 2, created_item)
                
                # Status
                is_running = tunnel_id in self.running_tunnels
                status_item = QTableWidgetItem("Running" if is_running else "Stopped")
                if is_running:
                    status_item.setForeground(Qt.GlobalColor.green)
                self.tunnels_table.setItem(row, 3, status_item)
                
                # Actions
                actions_widget = QWidget()
                actions_layout = QHBoxLayout()
                actions_layout.setContentsMargins(0, 0, 0, 0)
                
                if is_running:
                    # Show Stop button for running tunnels
                    stop_btn = QPushButton("Stop")
                    stop_btn.clicked.connect(lambda checked, tid=tunnel_id: self.stop_tunnel(tid))
                    actions_layout.addWidget(stop_btn)
                else:
                    # Show Run button for stopped tunnels
                    run_btn = QPushButton("Run")
                    run_btn.clicked.connect(lambda checked, tid=tunnel_id: self.run_tunnel(tid))
                    actions_layout.addWidget(run_btn)
                
                info_btn = QPushButton("Info")
                info_btn.clicked.connect(lambda checked, tid=tunnel_id: self.show_tunnel_info(tid))
                actions_layout.addWidget(info_btn)
                
                actions_widget.setLayout(actions_layout)
                self.tunnels_table.setCellWidget(row, 4, actions_widget)
            
            self.log(f"Found {len(tunnels)} tunnels")
        except Exception as e:
            self.log(f"Error parsing tunnels: {e}")
            if not tunnels_json or tunnels_json.strip() == "":
                self.log("No tunnels found or cloudflared not installed correctly")
                self.tunnels_table.setRowCount(0)
    
    def show_create_tunnel_dialog(self):
        """Show dialog to create a new tunnel"""
        dialog = CreateTunnelDialog(self)
        if dialog.exec():
            values = dialog.get_values()
            self.create_tunnel(values, dialog)
    
    def create_tunnel(self, values, dialog=None):
        """Create a new tunnel with the given values"""
        name = values["name"]
        if not name:
            self.log("Error: Tunnel name is required")
            return
        
        self.log(f"Creating tunnel '{name}'...")
        
        # Create tunnel
        thread = CommandThread(manager.create_tunnel, name)
        thread.output_ready.connect(self.log)
        thread.finished_with_status.connect(lambda success, error: 
            self.process_tunnel_creation(values, success, error, dialog))
        self.active_threads.append(thread)  # Keep reference
        thread.start()
    
    def process_tunnel_creation(self, values, success, error, dialog=None):
        """Process tunnel creation result and continue with configuration"""
        if not success:
            self.log(f"Error creating tunnel: {error}")
            return
        
        # Get tunnel UUID from tunnel list
        self.log("Getting tunnel details...")
        thread = CommandThread(manager.list_tunnels)
        thread.output_ready.connect(lambda tunnels_json: 
            self.configure_tunnel(values, tunnels_json, dialog))
        self.active_threads.append(thread)  # Keep reference
        thread.start()
    
    def configure_tunnel(self, values, tunnels_json, dialog=None):
        """Configure the newly created tunnel"""
        try:
            tunnels = json.loads(tunnels_json)
            tunnel = next((t for t in tunnels if t['name'] == values["name"]), None)
            
            if not tunnel:
                self.log("Tunnel creation failed or tunnel not found.")
                return
            
            tunnel_id = tunnel['id']
            credentials_file = tunnel.get('credentials_file', 
                                         os.path.expanduser(f"~/.cloudflared/{tunnel_id}.json"))
            
            url = values["url"]
            warp_routing = values["warp_routing"]
            
            # Create config file
            self.log(f"Creating config file for tunnel {tunnel_id}...")
            thread = CommandThread(
                manager.create_config_file, 
                tunnel_id, 
                credentials_file, 
                url, 
                warp_routing
            )
            thread.output_ready.connect(lambda config_path: 
                self.log(f"Config file created at: {config_path}"))
            thread.finished_with_status.connect(lambda success, error:
                self.process_config_creation(values, tunnel_id, credentials_file, success, error, dialog))
            self.active_threads.append(thread)  # Keep reference
            thread.start()
            
        except Exception as e:
            self.log(f"Error configuring tunnel: {e}")
    
    def process_config_creation(self, values, tunnel_id, credentials_file, success, error, dialog=None):
        """Process config creation and continue with service setup if needed"""
        if not success:
            self.log(f"Error creating config file: {error}")
            return
        
        # Copy/symlink config and credentials for service if requested
        if values["copy_for_service"]:
            self.log("Copying/symlinking config and credentials for service...")
            src_config = os.path.expanduser("~/.cloudflared/config.yml")
            thread = CommandThread(
                manager.copy_or_symlink_config_and_creds,
                src_config,
                credentials_file
            )
            thread.output_ready.connect(lambda result: 
                self.log("Config and credentials copied/symlinked to service directory"))
            thread.finished_with_status.connect(lambda success, error:
                self.update_service_config(values, tunnel_id, credentials_file, success, error, dialog))
            self.active_threads.append(thread)  # Keep reference
            thread.start()
        else:
            # Skip to DNS/IP routing
            self.setup_routing(values, tunnel_id, dialog)
    
    def update_service_config(self, values, tunnel_id, credentials_file, success, error, dialog=None):
        """Update service config with new tunnel"""
        if not success:
            self.log(f"Error copying/symlinking config: {error}")
            return
        
        self.log("Updating service config with new tunnel...")
        thread = CommandThread(
            manager.update_service_config,
            tunnel_id,
            credentials_file,
            values["url"]
        )
        thread.output_ready.connect(lambda result: 
            self.log("Service config updated with new tunnel."))
        thread.finished_with_status.connect(lambda success, error:
            self.restart_service_if_needed(values, tunnel_id, success, error, dialog))
        self.active_threads.append(thread)  # Keep reference
        thread.start()
    
    def restart_service_if_needed(self, values, tunnel_id, success, error, dialog=None):
        """Restart service if requested"""
        if not success:
            self.log(f"Error updating service config: {error}")
            return
        
        if values["restart_service"]:
            self.log("Restarting service to apply new tunnel config...")
            thread = CommandThread(manager.restart_service)
            thread.output_ready.connect(lambda result: 
                self.log("Service restarted with new tunnel config."))
            thread.finished_with_status.connect(lambda success, error:
                self.setup_routing(values, tunnel_id, dialog))
            self.active_threads.append(thread)  # Keep reference
            thread.start()
        else:
            # Skip to DNS/IP routing
            self.setup_routing(values, tunnel_id, dialog)
    
    def setup_routing(self, values, tunnel_id, dialog=None):
        """Setup DNS and IP routing if provided"""
        # Add DNS route if hostname provided
        hostname = values["hostname"]
        if hostname:
            self.log(f"Adding DNS route for {hostname}...")
            
            # Use a more direct approach for DNS route creation
            def add_dns_route_task():
                try:
                    result = manager.add_dns_route(tunnel_id, hostname)
                    return f"DNS route added successfully: {hostname} -> tunnel {tunnel_id}"
                except Exception as e:
                    return f"Error adding DNS route: {e}"
            
            thread = CommandThread(add_dns_route_task)
            thread.output_ready.connect(self.log)
            thread.finished_with_status.connect(lambda success, error: 
                self.log(f"DNS route status: {'Success' if success else f'Failed: {error}'}")
            )
            self.active_threads.append(thread)  # Keep reference
            thread.start()
        
        # Add IP route if CIDR provided
        ip_cidr = values["ip_cidr"]
        if ip_cidr:
            self.log(f"Adding IP route for {ip_cidr}...")
            
            # Use a more direct approach for IP route creation
            def add_ip_route_task():
                try:
                    result = manager.add_ip_route(ip_cidr, tunnel_id)
                    return f"IP route added successfully: {ip_cidr} -> tunnel {tunnel_id}"
                except Exception as e:
                    return f"Error adding IP route: {e}"
            
            thread = CommandThread(add_ip_route_task)
            thread.output_ready.connect(self.log)
            thread.finished_with_status.connect(lambda success, error: 
                self.log(f"IP route status: {'Success' if success else f'Failed: {error}'}")
            )
            self.active_threads.append(thread)  # Keep reference
            thread.start()
        
        # Run tunnel if requested
        if values["run_now"]:
            self.run_tunnel(tunnel_id)
        
        # Refresh tunnels list
        self.refresh_tunnels()
    
    def delete_selected_tunnel(self):
        """Delete the selected tunnel"""
        selected_items = self.tunnels_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select a tunnel to delete")
            return
        
        tunnel_id = self.tunnels_table.item(selected_items[0].row(), 0).text()
        
        reply = QMessageBox.question(
            self, 
            "Confirm Deletion", 
            f"Are you sure you want to delete tunnel {tunnel_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log(f"Deleting tunnel {tunnel_id}...")
            thread = CommandThread(manager.delete_tunnel, tunnel_id)
            thread.output_ready.connect(lambda result: self.log(f"Tunnel {tunnel_id} deleted"))
            thread.finished_with_status.connect(lambda success, error: 
                self.refresh_tunnels() if success else self.log(f"Error: {error}"))
            self.active_threads.append(thread)  # Keep reference
            thread.start()
    
    def run_tunnel(self, tunnel_id):
        """Run the specified tunnel"""
        # Check if tunnel is already running
        if tunnel_id in self.running_tunnels:
            QMessageBox.information(self, "Tunnel Running", f"Tunnel {tunnel_id} is already running.")
            return
            
        self.log(f"Running tunnel {tunnel_id}...")
        
        # Create a process to run the tunnel
        import subprocess
        import platform
        import os
        
        try:
            # Start the tunnel process
            if platform.system().lower() == "windows":
                # Use CREATE_NEW_CONSOLE to create a new window for the tunnel
                from subprocess import CREATE_NEW_CONSOLE
                process = subprocess.Popen(
                    ["cloudflared", "tunnel", "run", tunnel_id],
                    creationflags=CREATE_NEW_CONSOLE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            else:
                # For non-Windows platforms
                process = subprocess.Popen(
                    ["cloudflared", "tunnel", "run", tunnel_id],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
            # Store the process
            self.running_tunnels[tunnel_id] = process
            self.log(f"Tunnel {tunnel_id} started with PID {process.pid}")
            
            # Update the UI to show the tunnel is running
            self.refresh_tunnels()
            
        except Exception as e:
            self.log(f"Error starting tunnel: {e}")
    
    def stop_tunnel(self, tunnel_id):
        """Stop a running tunnel"""
        if tunnel_id not in self.running_tunnels:
            self.log(f"Tunnel {tunnel_id} is not running")
            return
            
        process = self.running_tunnels[tunnel_id]
        self.log(f"Stopping tunnel {tunnel_id} (PID {process.pid})...")
        
        try:
            import signal
            import platform
            
            if platform.system().lower() == "windows":
                import subprocess
                # On Windows, we need to use taskkill
                subprocess.run(["taskkill", "/F", "/PID", str(process.pid)])
            else:
                # On Unix-like systems, we can use the kill signal
                process.send_signal(signal.SIGTERM)
                
            # Remove from running tunnels
            del self.running_tunnels[tunnel_id]
            self.log(f"Tunnel {tunnel_id} stopped")
            
            # Update the UI
            self.refresh_tunnels()
            
        except Exception as e:
            self.log(f"Error stopping tunnel: {e}")
    
    def show_tunnel_info(self, tunnel_id):
        """Show information about the specified tunnel in a modal dialog"""
        self.log(f"Getting info for tunnel {tunnel_id}...")
        
        # Create and show the dialog
        info_dialog = TunnelInfoDialog(self, tunnel_id)
        
        # Get tunnel info in a thread
        thread = CommandThread(manager.tunnel_info, tunnel_id)
        thread.output_ready.connect(lambda info: self.update_tunnel_info_dialog(info_dialog, info))
        self.active_threads.append(thread)  # Keep reference
        thread.start()
        
        # Try to get config file content
        config_thread = CommandThread(self.get_tunnel_config, tunnel_id)
        config_thread.output_ready.connect(lambda config: info_dialog.set_config_content(config))
        self.active_threads.append(config_thread)  # Keep reference
        config_thread.start()
        
        # Show the dialog
        info_dialog.exec()
    
    def update_tunnel_info_dialog(self, dialog, info):
        """Update the tunnel info dialog with the retrieved information"""
        try:
            # Parse the tunnel info
            parsed_info = self.parse_tunnel_info(info)
            
            # Update the dialog directly instead of creating a new one
            dialog.setWindowTitle(f"Tunnel Information: {parsed_info.get('id', 'Unknown')}")
            
            # Clear existing widgets in the basic info layout
            basic_info_layout = dialog.findChild(QGroupBox, "basic_info_group").layout()
            while basic_info_layout.count():
                item = basic_info_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # Add the parsed info
            for key, value in parsed_info.items():
                label = QLabel(str(value))
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                basic_info_layout.addRow(f"{key}:", label)
        except Exception as e:
            # If parsing fails, just show the raw info
            info_text = QTextEdit()
            info_text.setReadOnly(True)
            info_text.setPlainText(str(info))
            
            # Clear existing widgets in the basic info layout
            basic_info_layout = dialog.findChild(QGroupBox, "basic_info_group").layout()
            while basic_info_layout.count():
                item = basic_info_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                    
            basic_info_layout.addRow("Error parsing info:", QLabel(str(e)))
            basic_info_layout.addRow(info_text)
    
    def parse_tunnel_info(self, info_text):
        """Parse the tunnel info text into a structured format"""
        result = {}
        
        # Check if it's a CompletedProcess result
        if "CompletedProcess" in info_text:
            # Just return the raw text for now
            result["raw_output"] = info_text
            return result
        
        lines = info_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if ':' in line:
                key, value = line.split(':', 1)
                result[key.strip().lower()] = value.strip()
            elif 'CONNECTOR ID' in line:
                # Start of connector table
                result["connectors"] = "Found in output"
        
        return result
    
    def get_tunnel_config(self, tunnel_id):
        """Get the configuration for a tunnel"""
        try:
            # Try to find the config file
            config_path = os.path.expanduser(f"~/.cloudflared/config.yml")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config_content = f.read()
                return config_content
            
            # Try to find the credentials file
            creds_path = os.path.expanduser(f"~/.cloudflared/{tunnel_id}.json")
            if os.path.exists(creds_path):
                with open(creds_path, 'r') as f:
                    creds_content = f.read()
                return f"Credentials file:\n{creds_content}"
            
            return "No configuration found for this tunnel."
        except Exception as e:
            return f"Error reading configuration: {e}"
    
    def fetch_dns_records(self, tunnel_id, dialog):
        """Fetch DNS records for a tunnel and update the dialog"""
        dialog.dns_status_label.setText("Fetching DNS records...")
        
        def get_dns_records():
            try:
                # Run cloudflared tunnel route ip list
                import subprocess
                result = subprocess.run(
                    ["cloudflared", "tunnel", "route", "dns", "list", "--output", "json"],
                    capture_output=True, text=True, check=True
                )
                
                if result.stdout.strip():
                    records = json.loads(result.stdout)
                    # Filter records for this tunnel
                    tunnel_records = [r for r in records if r.get('tunnel_id') == tunnel_id]
                    return tunnel_records
                return []
            except subprocess.CalledProcessError as e:
                return f"Error: {e.stderr if e.stderr else str(e)}"
            except Exception as e:
                return f"Error: {str(e)}"
        
        thread = CommandThread(get_dns_records)
        thread.output_ready.connect(lambda result: self.update_dns_records_table(result, dialog))
        self.active_threads.append(thread)
        thread.start()
    
    def update_dns_records_table(self, records, dialog):
        """Update the DNS records table in the dialog"""
        try:
            if isinstance(records, list):
                dialog.dns_records_table.setRowCount(len(records))
                
                if not records:
                    dialog.dns_status_label.setText("No DNS records found for this tunnel.")
                    return
                
                for row, record in enumerate(records):
                    # Hostname
                    hostname = record.get('hostname', 'N/A')
                    hostname_item = QTableWidgetItem(hostname)
                    dialog.dns_records_table.setItem(row, 0, hostname_item)
                    
                    # Type (always CNAME for tunnel DNS records)
                    type_item = QTableWidgetItem("CNAME")
                    dialog.dns_records_table.setItem(row, 1, type_item)
                    
                    # Target
                    target = record.get('cname', 'N/A')
                    target_item = QTableWidgetItem(target)
                    dialog.dns_records_table.setItem(row, 2, target_item)
                
                dialog.dns_status_label.setText(f"Found {len(records)} DNS records")
            else:
                # Error message
                dialog.dns_status_label.setText(str(records))
                dialog.dns_records_table.setRowCount(0)
        except Exception as e:
            dialog.dns_status_label.setText(f"Error updating DNS records: {e}")
            dialog.dns_records_table.setRowCount(0)
    
    def install_service(self):
        """Install cloudflared as a service"""
        self.log("Installing cloudflared as a service...")
        thread = CommandThread(manager.install_service)
        thread.output_ready.connect(self.log)
        thread.finished_with_status.connect(lambda success, error: 
            self.refresh_status() if success else self.log(f"Error: {error}"))
        self.active_threads.append(thread)  # Keep reference
        thread.start()
    
    def uninstall_service(self):
        """Uninstall cloudflared service"""
        reply = QMessageBox.question(
            self, 
            "Confirm Uninstall", 
            "Are you sure you want to uninstall the cloudflared service?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log("Uninstalling cloudflared service...")
            thread = CommandThread(manager.uninstall_service)
            thread.output_ready.connect(self.log)
            thread.finished_with_status.connect(lambda success, error: 
                self.refresh_status() if success else self.log(f"Error: {error}"))
            self.active_threads.append(thread)  # Keep reference
            thread.start()
    
    def clean_service_files(self):
        """Clean service files"""
        reply = QMessageBox.question(
            self, 
            "Confirm Cleanup", 
            "Are you sure you want to remove all service config files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log("Cleaning service files...")
            thread = CommandThread(manager.clean_service_files)
            thread.output_ready.connect(self.log)
            thread.finished_with_status.connect(lambda success, error: 
                self.log("Service files cleaned") if success else self.log(f"Error: {error}"))
            self.active_threads.append(thread)  # Keep reference
            thread.start()
    
    def diagnose_service_config(self):
        """Diagnose service configuration"""
        self.log("Diagnosing service configuration...")
        thread = CommandThread(manager.diagnose_service_config)
        thread.output_ready.connect(self.log)
        self.active_threads.append(thread)  # Keep reference
        thread.start()

    def closeEvent(self, event):
        """Handle window close event - clean up threads and processes"""
        try:
            # Stop all running tunnels
            running_tunnel_ids = list(self.running_tunnels.keys())
            for tunnel_id in running_tunnel_ids:
                try:
                    self.stop_tunnel(tunnel_id)
                except Exception as e:
                    print(f"Error stopping tunnel {tunnel_id}: {e}")
        except Exception as e:
            print(f"Error stopping tunnels: {e}")
        
        # Accept the close event
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
