#!/usr/bin/env python3
"""
Amplitude Bulk Annotation Maker.

A GUI application for applying annotations to multiple Amplitude charts at once.
Built with Python 3.9+ and PySide6, following best practices for code organization,
error handling, and user experience.
"""
import sys
import json
import os
import logging
import subprocess
import platform
from datetime import date
from typing import List, Dict, Optional, Set, Tuple, Any
from functools import lru_cache

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QTextEdit,
    QGroupBox, QComboBox, QDateEdit, QMessageBox, QProgressDialog,
    QFormLayout, QFileDialog, QMenuBar
)
from PySide6.QtCore import Qt, QDate, Signal, QThread, QTimer
from PySide6.QtGui import QFont, QAction

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()  # This loads .env file automatically
except ImportError:
    pass  # python-dotenv not installed, skip

from amplitude_api import AmplitudeAPIClient, AmplitudeAPIError
from constants import (
    ENV_API_KEY, ENV_SECRET_KEY, ENV_PROJECT_ID, ENV_REGION,
    CONFIG_FILE, DEFAULT_REGION, VALID_REGIONS,
    STATUS_TEXT_MAX_HEIGHT, DESCRIPTION_MAX_HEIGHT,
    CHART_INPUT_MIN_HEIGHT, RESULTS_TEXT_MAX_HEIGHT,
    MASKED_CREDENTIAL_DISPLAY,
    AUTO_TEST_DELAY, AUTO_TEST_DELAY_FAST
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('amplitude_bulk_annotator.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class APIWorker(QThread):
    """
    Worker thread for API operations.
    
    This thread handles long-running API operations to prevent UI freezing.
    Emits progress updates and completion status.
    """
    
    # Signals
    finished = Signal(bool, str)  # success, message
    progress = Signal(int, int)   # current, total
    
    def __init__(
        self,
        api_client: AmplitudeAPIClient,
        operation: str,
        *args: Any,
        **kwargs: Any
    ) -> None:
        """
        Initialize the API worker thread.
        
        Args:
            api_client: AmplitudeAPIClient instance
            operation: Operation to perform ('test_connection' or 'bulk_annotate')
            *args: Positional arguments for the operation
            **kwargs: Keyword arguments for the operation
        """
        super().__init__()
        self.api_client = api_client
        self.operation = operation
        self.args = args
        self.kwargs = kwargs
        self._is_cancelled = False
    
    def run(self) -> None:
        """Execute the API operation in a separate thread."""
        try:
            if self.operation == "test_connection":
                self._handle_test_connection()
            elif self.operation == "bulk_annotate":
                self._handle_bulk_annotate()
            else:
                logger.error(f"Unknown operation: {self.operation}")
                self.finished.emit(False, f"Unknown operation: {self.operation}")
                
        except AmplitudeAPIError as e:
            logger.error(f"API error in worker: {e}")
            self.finished.emit(False, f"API Error: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error in API worker")
            self.finished.emit(False, f"Unexpected error: {str(e)}")
    
    def _handle_test_connection(self) -> None:
        """Handle test connection operation."""
        success, message = self.api_client.test_connection()
        self.finished.emit(success, message)
    
    def _handle_bulk_annotate(self) -> None:
        """Handle bulk annotation operation."""
        results = self.api_client.bulk_annotate(
            *self.args,
            progress_callback=lambda curr, total: self.progress.emit(curr, total),
            **self.kwargs
        )
        
        # Summarize results
        success_count = sum(1 for _, success, _ in results if success)
        total_count = len(results)
        
        if total_count == 0:
            message = "No charts to annotate"
        elif success_count == total_count:
            message = f"✅ All {total_count} annotations successful"
        else:
            message = f"⚠️ Completed: {success_count}/{total_count} successful"
            
        self.finished.emit(success_count == total_count, message)


class ConfigTab(QWidget):
    """
    Configuration tab for API settings.
    
    Handles API credential input, validation, and connection testing.
    Prioritizes environment variables over manual input for security.
    """
    
    # Signals
    configValid = Signal(bool)
    
    def __init__(self) -> None:
        """Initialize the configuration tab."""
        super().__init__()
        self.api_client: Optional[AmplitudeAPIClient] = None
        self.credentials_from_env: bool = False
        self.worker: Optional[APIWorker] = None
        
        self.init_ui()
        self.load_config()
        
        # Auto-test connection if environment variables are complete
        if self.has_complete_env_config():
            QTimer.singleShot(AUTO_TEST_DELAY, self.auto_test_connection)
    
    def init_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        
        # Environment status info with optional edit button
        self.env_status_widget = QWidget()
        self.env_status_layout = QHBoxLayout(self.env_status_widget)
        self.env_status_layout.setContentsMargins(0, 0, 0, 0)
        self.env_status_layout.setSpacing(8)
        
        self.env_status_label = QLabel()
        self.env_status_label.setWordWrap(True)
        self.env_status_label.setStyleSheet("QLabel { background-color: #e8f4fd; padding: 8px; border-radius: 4px; border-left: 4px solid #0078d4; }")
        self.env_status_layout.addWidget(self.env_status_label, 1)  # Give it stretch factor of 1 to take most space
        
        # Edit .env file button (only shown when .env file exists) - compact like Continue button
        self.edit_env_btn = QPushButton("Edit .env File")
        self.edit_env_btn.clicked.connect(self.open_env_file)
        self.edit_env_btn.setStyleSheet("QPushButton { padding: 6px 12px; font-size: 11px; background-color: #0078d4; color: white; border: none; border-radius: 3px; min-width: 80px; max-width: 120px; } QPushButton:hover { background-color: #106ebe; }")
        self.edit_env_btn.setSizePolicy(self.edit_env_btn.sizePolicy().horizontalPolicy(), self.edit_env_btn.sizePolicy().verticalPolicy())
        self.env_status_layout.addWidget(self.edit_env_btn, 0)  # No stretch - keep it compact
        
        layout.addWidget(self.env_status_widget)
        
        # .env file management note (only shown when .env file exists)
        self.env_note_layout = QHBoxLayout()
        
        self.env_file_note = QLabel()
        self.env_file_note.setWordWrap(True)
        self.env_file_note.setStyleSheet("QLabel { color: #666; font-size: 11px; font-style: italic; padding: 4px; }")
        self.env_note_layout.addWidget(self.env_file_note)
        
        self.env_note_layout.addStretch()
        # Don't add to layout yet - will be added conditionally in load_config
        
        # API Configuration group
        api_group = QGroupBox("API Configuration")
        api_layout = QFormLayout()
        
        # Help text
        help_label = QLabel("To find your project details navigate to: Amplitude → Settings → Projects → Select your project")
        help_label.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        help_label.setWordWrap(True)
        api_layout.addRow("", help_label)
        
        # Project ID
        self.project_id_input = QLineEdit()
        self.project_id_input.setPlaceholderText("e.g., 123456")
        api_layout.addRow("Project ID:", self.project_id_input)
        
        # Region
        self.region_combo = QComboBox()
        self.region_combo.addItems(VALID_REGIONS)
        api_layout.addRow("Region:", self.region_combo)
        
        # API Key
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Your Amplitude API Key")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addRow("API Key:", self.api_key_input)
        
        # Secret Key
        self.secret_key_input = QLineEdit()
        self.secret_key_input.setPlaceholderText("Your Amplitude Secret Key")
        self.secret_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addRow("Secret Key:", self.secret_key_input)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # Test connection and save button (combined)
        self.test_btn = QPushButton("Test Connection and Save")
        self.test_btn.clicked.connect(self.test_connection)
        self.test_btn.setStyleSheet("QPushButton { padding: 8px 16px; font-weight: bold; }")
        self.test_btn.setEnabled(False)  # Start disabled
        layout.addWidget(self.test_btn)
        
        # Connect input validation
        self.api_key_input.textChanged.connect(self._validate_inputs)
        self.secret_key_input.textChanged.connect(self._validate_inputs)
        self.project_id_input.textChanged.connect(self._validate_inputs)
        
        layout.addStretch()
    
    def load_config(self) -> None:
        """
        Load configuration from environment variables first, then file for preferences.
        
        Prioritizes environment variables for security. Falls back to manual input
        if environment variables are not found.
        """
        # Check for environment variables first (recommended approach)
        env_api_key = os.getenv(ENV_API_KEY)
        env_secret_key = os.getenv(ENV_SECRET_KEY)
        env_project_id = os.getenv(ENV_PROJECT_ID)
        env_region = os.getenv(ENV_REGION, DEFAULT_REGION)
        
        if env_api_key and env_secret_key:
            # Credentials found in environment variables
            self.credentials_from_env = True
            self._setup_env_credentials(env_api_key, env_secret_key, env_project_id, env_region)
            logger.info("Using credentials from environment variables")
        else:
            # No environment variables, allow manual input
            self.credentials_from_env = False
            self._setup_manual_credentials(env_project_id)
            logger.info("No environment credentials found, using manual input")
        
        # Show/hide edit .env file button based on file existence
        self._update_env_button_visibility()
        
        # Validate inputs to set initial button state
        self._validate_inputs()
    
    def _env_file_exists(self) -> bool:
        """Check if .env file exists in the current directory."""
        return os.path.exists('.env')
    
    def _update_env_button_visibility(self) -> None:
        """Show/hide the edit .env file button based on file existence."""
        if self._env_file_exists():
            self.edit_env_btn.show()
        else:
            self.edit_env_btn.hide()
    
    def _update_status_bar(self, message: str, status_type: str = "info") -> None:
        """Update the status bar with a message and appropriate styling."""
        self.env_status_label.setText(message)
        self.env_status_widget.show()
        
        if status_type == "success":
            self.env_status_label.setStyleSheet("QLabel { background-color: #d4edda; padding: 8px; border-radius: 4px; border-left: 4px solid #28a745; }")
        elif status_type == "error":
            self.env_status_label.setStyleSheet("QLabel { background-color: #f8d7da; padding: 8px; border-radius: 4px; border-left: 4px solid #dc3545; }")
        elif status_type == "warning":
            self.env_status_label.setStyleSheet("QLabel { background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 4px solid #ffc107; }")
        else:  # info
            self.env_status_label.setStyleSheet("QLabel { background-color: #e8f4fd; padding: 8px; border-radius: 4px; border-left: 4px solid #0078d4; }")
    
    def _validate_inputs(self) -> None:
        """Validate input fields and enable/disable the Test Connection button."""
        if self.credentials_from_env:
            # Using environment variables - always enable if we have env credentials
            self.test_btn.setEnabled(True)
            return
        
        # Manual input validation
        api_key = self.api_key_input.text().strip()
        secret_key = self.secret_key_input.text().strip()
        project_id = self.project_id_input.text().strip()
        
        # Check if all required fields are filled
        has_credentials = bool(api_key and secret_key)
        has_project_id = bool(project_id and project_id.isdigit())
        
        # Enable button only if all requirements are met
        self.test_btn.setEnabled(has_credentials and has_project_id)
    
    def _refresh_env_variables(self) -> None:
        """Refresh environment variables by reloading the .env file."""
        try:
            from dotenv import load_dotenv
            # Reload the .env file, overriding existing environment variables
            load_dotenv(override=True)
            
            # Check if we now have valid credentials
            env_api_key = os.getenv(ENV_API_KEY)
            env_secret_key = os.getenv(ENV_SECRET_KEY)
            env_project_id = os.getenv(ENV_PROJECT_ID)
            env_region = os.getenv(ENV_REGION, DEFAULT_REGION)
            
            # If we now have credentials from the .env file, update the UI
            if env_api_key and env_secret_key:
                if not self.credentials_from_env:
                    # Switch from manual to env credentials
                    self.credentials_from_env = True
                    self._setup_env_credentials(env_api_key, env_secret_key, env_project_id, env_region)
                    logger.info("Switched to environment credentials after .env file update")
                else:
                    # Just update the existing env credentials
                    logger.info("Refreshed environment credentials from .env file")
            else:
                # .env file exists but doesn't have valid credentials
                if self.credentials_from_env:
                    # Switch from env to manual credentials
                    self.credentials_from_env = False
                    self._setup_manual_credentials(env_project_id)
                    logger.info("Switched to manual credentials after .env file became invalid")
                    
        except ImportError:
            # python-dotenv not installed, can't refresh
            logger.warning("python-dotenv not available, cannot refresh .env file")
        except Exception as e:
            logger.error(f"Error refreshing .env file: {e}")
    
    def create_env_template(self) -> None:
        """Create a .env template file with placeholders."""
        template_content = f"""{ENV_API_KEY}=your_api_key_here
{ENV_SECRET_KEY}=your_secret_key_here
{ENV_PROJECT_ID}=123456
{ENV_REGION}=US
"""
        
        try:
            with open('.env', 'w') as f:
                f.write(template_content)
            
            # Status will be shown in the main status bar
            
            # Update status label
            self.env_status_label.setText("📄 .env file created! Add your credentials and restart the application.")
            self.env_status_label.setStyleSheet("QLabel { background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 4px solid #ffc107; }")
            self.env_status_widget.show()
            
            # Note: Removed light bulb emoji text as requested
            
            # Update button visibility after creating .env file
            self._update_env_button_visibility()
            
            logger.info(".env template file created successfully")
            
        except IOError as e:
            logger.error(f"Error creating .env file: {e}")
            self._update_status_bar(f"❌ Error creating .env file: {str(e)}", "error")
            QMessageBox.critical(self, "Error", f"Failed to create .env file:\n{str(e)}")
    
    def open_env_file(self) -> None:
        """Open the .env file with the system's default editor."""
        env_path = '.env'
        
        if not os.path.exists(env_path):
            QMessageBox.warning(self, "File Not Found", "The .env file does not exist.")
            return
        
        try:
            # Get the absolute path for better reliability
            abs_path = os.path.abspath(env_path)
            
            # Use platform-specific command to open file
            system = platform.system().lower()
            if system == 'darwin':  # macOS
                subprocess.run(['open', abs_path], check=True)
            elif system == 'windows':
                os.startfile(abs_path)
            else:  # Linux and other Unix-like systems
                subprocess.run(['xdg-open', abs_path], check=True)
            
            # File opened successfully - no need to show status
            logger.info(f"Opened .env file: {abs_path}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error opening .env file: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open .env file:\n{str(e)}")
        except FileNotFoundError:
            logger.error("System command not found for opening files")
            QMessageBox.critical(self, "Error", "Could not find system command to open files.\nPlease open the .env file manually in your text editor.")
        except Exception as e:
            logger.error(f"Unexpected error opening .env file: {e}")
            QMessageBox.critical(self, "Error", f"Unexpected error opening .env file:\n{str(e)}")
    
    def _setup_env_credentials(
        self,
        env_api_key: str,
        env_secret_key: str,
        env_project_id: Optional[str],
        env_region: str
    ) -> None:
        """Set up UI for environment variable credentials."""
        # Update status and note based on .env file existence
        if self._env_file_exists():
            self.env_status_label.setText("🔒 Configuration loaded from .env file")
            self.env_status_widget.show()
            # Note: Removed light bulb emoji text as requested
        else:
            # Environment variables are from system environment, not .env file
            self.env_status_label.setText("🔒 Configuration loaded from system environment variables")
            self.env_status_widget.show()
            # Don't show .env file note when using system environment variables
        
        self.env_status_label.setStyleSheet("QLabel { background-color: #d4edda; padding: 8px; border-radius: 4px; border-left: 4px solid #28a745; }")
        
        # Setup API Key
        self.api_key_input.setText(MASKED_CREDENTIAL_DISPLAY)
        self.api_key_input.setEnabled(False)
        self.api_key_input.setToolTip("API Key loaded from environment variable - fields are read-only")
        
        # Setup Secret Key
        self.secret_key_input.setText(MASKED_CREDENTIAL_DISPLAY)
        self.secret_key_input.setEnabled(False)
        self.secret_key_input.setToolTip("Secret Key loaded from environment variable - fields are read-only")
        
        # Setup Region
        self.region_combo.setCurrentText(env_region)
        self.region_combo.setEnabled(False)
        self.region_combo.setToolTip("Region loaded from environment variable - fields are read-only")
        
        # Setup Project ID
        if env_project_id:
            self.project_id_input.setText(env_project_id)
            self.project_id_input.setEnabled(False)
            self.project_id_input.setToolTip("Project ID loaded from environment variable - fields are read-only")
        
        self._update_status_bar("✅ Using environment variables - auto-testing connection...", "success")
        
        # Validate inputs to enable test button
        self._validate_inputs()
    
    def _setup_manual_credentials(self, env_project_id: Optional[str]) -> None:
        """Set up UI for manual credential input."""
        # Update status and note based on .env file existence
        if self._env_file_exists():
            self.env_status_label.setText("📄 .env file exists but contains invalid credentials - edit the file or enter credentials manually below")
            self.env_status_label.setStyleSheet("QLabel { background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 4px solid #ffc107; }")
            self.env_status_widget.show()
            # Note: Removed light bulb emoji text as requested
        else:
            # Hide the entire status widget when no .env file exists and no environment variables are set
            self.env_status_widget.hide()
            # Don't show .env file note when no .env file exists
        
        # Enable all fields for manual input
        self.api_key_input.setEnabled(True)
        self.secret_key_input.setEnabled(True)
        self.project_id_input.setEnabled(True)
        self.region_combo.setEnabled(True)
        
        # Load preferences from file (non-sensitive settings only)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.region_combo.setCurrentText(config.get('region', DEFAULT_REGION))
                    
                    # Only load project_id from file if not in environment
                    if not env_project_id:
                        self.project_id_input.setText(config.get('project_id', ''))
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in config file: {e}")
                # Don't show error in status bar for preference loading issues
            except IOError as e:
                logger.error(f"Error reading config file: {e}")
                # Don't show error in status bar for preference loading issues
    
    def save_config(self) -> None:
        """
        Save non-sensitive preferences only.
        
        Never saves API keys or secrets to disk for security reasons.
        """
        # Only save non-sensitive preferences
        config: Dict[str, str] = {
            'region': self.region_combo.currentText(),
        }
        
        # Only save project_id if it's not from environment variables
        if not os.getenv(ENV_PROJECT_ID) and self.project_id_input.text():
            config['project_id'] = self.project_id_input.text()
        
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info("Preferences saved to file")
        except IOError as e:
            logger.error(f"Error saving preferences: {e}")
    
    def test_connection(self):
        """Test the API connection"""
        # Refresh environment variables if .env file exists (in case user edited it)
        if self._env_file_exists():
            self._refresh_env_variables()
        
        # Get credentials from environment or manual input
        if self.credentials_from_env:
            api_key = os.getenv(ENV_API_KEY)
            secret_key = os.getenv(ENV_SECRET_KEY)
        else:
            api_key = self.api_key_input.text()
            secret_key = self.secret_key_input.text()
        
        if not api_key or not secret_key:
            self._update_status_bar("❌ Please provide both API key and secret key", "error")
            return
        
        # Create API client
        self.api_client = AmplitudeAPIClient(
            api_key=api_key,
            secret_key=secret_key,
            region=self.region_combo.currentText()
        )
        
        # Test connection in worker thread
        self.worker = APIWorker(self.api_client, "test_connection")
        self.worker.finished.connect(self.on_test_complete)
        self.worker.start()
        
        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing Connection...")
        self._update_status_bar("Testing connection...", "info")
    
    def on_test_complete(self, success, message):
        """Handle test completion and save preferences if successful"""
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Test Connection and Save")
        
        if success:
            # Check if project ID is provided (from environment or manual input)
            project_id = self.get_selected_project_id()
            if project_id:
                # Show success message with .env file indicator if applicable
                if self.credentials_from_env and self._env_file_exists():
                    self._update_status_bar("✅ Connection successful (using .env file)", "success")
                else:
                    self._update_status_bar("✅ Connection successful", "success")
                
                # Automatically save preferences on successful connection
                self._save_preferences_after_test()
                
                self.configValid.emit(True)
            else:
                self._update_status_bar("❌ Please provide a valid Project ID", "error")
                self.configValid.emit(False)
        else:
            # Parse error message to provide better explanations
            error_explanation = self._get_error_explanation(message)
            if error_explanation:
                self._update_status_bar(f"❌ {message} - {error_explanation}", "error")
            else:
                self._update_status_bar(f"❌ {message}", "error")
            self.configValid.emit(False)
    
    def _save_preferences_after_test(self):
        """Save preferences after successful connection test"""
        # Call the existing save_config method
        self.save_config()
    
    def _get_error_explanation(self, message: str) -> Optional[str]:
        """
        Get a user-friendly explanation for common API errors.
        
        Args:
            message: The error message from the API
            
        Returns:
            Human-readable explanation or None if no specific explanation available
        """
        message_lower = message.lower()
        
        # HTTP status code explanations
        if "401" in message or "authentication failed" in message_lower:
            return "Invalid API key or secret key. Check your credentials in Amplitude settings."
        elif "403" in message or "forbidden" in message_lower:
            return "Access denied. Your API key may be invalid or may not have annotation permissions."
        elif "404" in message or "not found" in message_lower:
            return "API endpoint not found. Check your region setting (US vs EU)."
        elif "429" in message or "rate limit" in message_lower:
            return "Too many requests. Wait a moment and try again."
        elif "500" in message or "internal server error" in message_lower:
            return "Amplitude server error. Try again in a few minutes."
        elif "502" in message or "bad gateway" in message_lower:
            return "Amplitude service temporarily unavailable. Try again later."
        elif "503" in message or "service unavailable" in message_lower:
            return "Amplitude service is down for maintenance. Try again later."
        elif "timeout" in message_lower:
            return "Connection timed out. Check your internet connection."
        elif "connection" in message_lower and "error" in message_lower:
            return "Network connection issue. Check your internet connection."
        elif "ssl" in message_lower or "certificate" in message_lower:
            return "SSL/Certificate error. Check your system date and network settings."
        
        # Return None if no specific explanation is available
        return None
    
    def get_api_client(self):
        return self.api_client if hasattr(self, 'api_client') else None
    
    def get_selected_project_id(self):
        """Get the selected project ID from environment or manual input"""
        env_project_id = os.getenv(ENV_PROJECT_ID)
        if env_project_id and env_project_id.isdigit():
            return int(env_project_id)
        
        project_id = self.project_id_input.text().strip()
        return int(project_id) if project_id.isdigit() else None
    
    @lru_cache(maxsize=1)
    def has_complete_env_config(self) -> bool:
        """Check if all required environment variables are set"""
        return (os.getenv(ENV_API_KEY) is not None and 
                os.getenv(ENV_SECRET_KEY) is not None and 
                os.getenv(ENV_PROJECT_ID) is not None)
    
    def auto_test_connection(self):
        """Automatically test connection when environment variables are complete"""
        if self.has_complete_env_config():
            self.test_connection()
    



class SelectionTab(QWidget):
    """Tab for inputting chart IDs or URLs"""
    selectionComplete = Signal(bool)
    
    def __init__(self):
        super().__init__()
        self.api_client = None
        self.project_id = None
        self.valid_chart_ids = []
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Status bar (same design as ConfigTab)
        self.status_widget = QWidget()
        self.status_layout = QHBoxLayout(self.status_widget)
        self.status_layout.setContentsMargins(0, 0, 0, 0)
        self.status_layout.setSpacing(8)
        
        self.status_label = QLabel("Ready to validate chart IDs")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("QLabel { background-color: #e8f4fd; padding: 8px; border-radius: 4px; border-left: 4px solid #0078d4; }")
        self.status_layout.addWidget(self.status_label, 1)
        
        layout.addWidget(self.status_widget)
        
        # Instructions
        instructions = QLabel(
            "Enter chart IDs or URLs below (one per line):\n\n"
            "• Chart ID: ez25o7zy\n"
            "• Full URL: https://app.amplitude.com/analytics/demo/chart/ez25o7zy\n"
            "• You can mix both formats and enter multiple charts"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }")
        layout.addWidget(instructions)
        
        # Chart input area
        input_group = QGroupBox("Chart IDs / URLs")
        input_layout = QVBoxLayout()
        
        self.chart_input = QTextEdit()
        self.chart_input.setPlaceholderText(
            "Enter chart IDs or URLs here...\n\n"
            "Examples:\n"
            "ez25o7zy\n"
            "abc123\n"
            "https://app.amplitude.com/analytics/demo/chart/xyz789\n"
            "def456, ghi789\n\n"
        )
        self.chart_input.setMinimumHeight(200)
        self.chart_input.textChanged.connect(self.on_text_changed)
        input_layout.addWidget(self.chart_input)
        
        # Parse button
        self.parse_btn = QPushButton("Validate Chart IDs")
        self.parse_btn.clicked.connect(self.parse_input)
        input_layout.addWidget(self.parse_btn)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        layout.addStretch()
    
    def _update_status_bar(self, message: str, status_type: str = "info") -> None:
        """Update the status bar with a message and appropriate styling."""
        self.status_label.setText(message)
        self.status_widget.show()
        
        if status_type == "success":
            self.status_label.setStyleSheet("QLabel { background-color: #d4edda; padding: 8px; border-radius: 4px; border-left: 4px solid #28a745; }")
        elif status_type == "error":
            self.status_label.setStyleSheet("QLabel { background-color: #f8d7da; padding: 8px; border-radius: 4px; border-left: 4px solid #dc3545; }")
        elif status_type == "warning":
            self.status_label.setStyleSheet("QLabel { background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 4px solid #ffc107; }")
        else:  # info
            self.status_label.setStyleSheet("QLabel { background-color: #e8f4fd; padding: 8px; border-radius: 4px; border-left: 4px solid #0078d4; }")
    
    def set_api_client(self, api_client, project_id):
        """Set API client and project ID"""
        self.api_client = api_client
        self.project_id = project_id
    
    def on_text_changed(self):
        """Handle text changes in the input area"""
        has_input = bool(self.chart_input.toPlainText().strip())
        if has_input:
            self._update_status_bar("Input detected - click 'Validate Chart IDs' to process", "info")
        else:
            self._update_status_bar("Ready to validate chart IDs", "info")
            self.valid_chart_ids = []
            self.selectionComplete.emit(False)
    
    def parse_input(self):
        """Parse and validate the input text with inline emoji indicators"""
        input_text = self.chart_input.toPlainText()
        
        if not input_text.strip():
            self._update_status_bar("No charts to process", "warning")
            self.valid_chart_ids = []
            self.selectionComplete.emit(False)
            return
        
        # Check if API client is available for real validation
        if not self.api_client or not self.project_id:
            self._update_status_bar("❌ API client not configured - cannot validate chart existence", "error")
            return
        
        # Temporarily disconnect the text changed signal to avoid recursion
        self.chart_input.textChanged.disconnect()
        
        try:
            # First, extract and format-validate chart IDs
            lines = input_text.strip().split('\n')
            format_validated_lines = []
            candidate_chart_ids = []
            
            for line in lines:
                original_line = line.strip()
                if not original_line:
                    format_validated_lines.append("")
                    continue
                
                # Remove any existing emoji indicators
                clean_line = original_line
                for emoji in ['✅', '❌', '⏳']:
                    clean_line = clean_line.replace(f' {emoji}', '').replace(f'{emoji} ', '').replace(emoji, '')
                clean_line = clean_line.strip()
                
                # Extract chart IDs from this line
                from utils.validators import extract_chart_ids, validate_chart_ids
                line_chart_ids = extract_chart_ids(clean_line)
                
                if line_chart_ids:
                    # Format validate the extracted IDs
                    valid_format_ids, invalid_format_ids = validate_chart_ids(line_chart_ids)
                    
                    if valid_format_ids and not invalid_format_ids:
                        # All IDs in this line have valid format - mark for API validation
                        format_validated_lines.append(f"⏳ {clean_line}")
                        candidate_chart_ids.extend(valid_format_ids)
                    else:
                        # Invalid format - mark as invalid immediately
                        format_validated_lines.append(f"❌ {clean_line}")
                else:
                    # No chart IDs found
                    format_validated_lines.append(f"❌ {clean_line}")
            
            # Show format validation results first
            new_text = '\n'.join(format_validated_lines)
            self.chart_input.setPlainText(new_text)
            
            # If we have candidates, perform API validation
            if candidate_chart_ids:
                unique_candidates = list(set(candidate_chart_ids))  # Remove duplicates
                self._update_status_bar(f"⏳ Validating {len(unique_candidates)} chart{'s' if len(unique_candidates) != 1 else ''} with Amplitude API...", "info")
                
                # Perform API validation
                validation_results = self.api_client.bulk_validate_charts(
                    self.project_id,
                    unique_candidates
                )
                
                # Create mapping of chart_id -> exists
                chart_exists_map = {chart_id: exists for chart_id, exists, _ in validation_results}
                
                # Update lines with API validation results
                final_lines = []
                all_valid_chart_ids = []
                
                for line in format_validated_lines:
                    if line.startswith("⏳ "):
                        # This line was pending API validation
                        clean_line = line[2:]  # Remove "⏳ " prefix
                        
                        # Extract chart IDs from this line again
                        line_chart_ids = extract_chart_ids(clean_line)
                        
                        # Check if all chart IDs in this line exist
                        all_exist = all(chart_exists_map.get(chart_id, False) for chart_id in line_chart_ids)
                        
                        if all_exist:
                            final_lines.append(f"✅ {clean_line}")
                            all_valid_chart_ids.extend(line_chart_ids)
                        else:
                            final_lines.append(f"❌ {clean_line}")
                    else:
                        # This line was already marked as invalid during format validation
                        final_lines.append(line)
                
                # Update the text area with final results
                final_text = '\n'.join(final_lines)
                cursor_position = self.chart_input.textCursor().position()
                self.chart_input.setPlainText(final_text)
                
                # Restore cursor position (approximately)
                cursor = self.chart_input.textCursor()
                cursor.setPosition(min(cursor_position, len(final_text)))
                self.chart_input.setTextCursor(cursor)
                
                # Update summary and signal
                self.valid_chart_ids = list(set(all_valid_chart_ids))  # Remove duplicates
                
                # Count total input lines with content (excluding empty lines)
                total_input_lines = sum(1 for line in final_lines if line.strip() and not line.strip().startswith(""))
                valid_count = len(self.valid_chart_ids)
                invalid_count = sum(1 for line in final_lines if line.startswith("❌ "))
                
                if valid_count > 0 and invalid_count > 0:
                    # Mixed results - show warning
                    self._update_status_bar(f"⚠️ {valid_count} valid chart{'s' if valid_count != 1 else ''} ready for annotation, {invalid_count} invalid chart{'s' if invalid_count != 1 else ''} will not be updated", "warning")
                    self.selectionComplete.emit(True)  # Still allow continuation with valid charts
                elif valid_count > 0:
                    # All valid
                    self._update_status_bar(f"✅ {valid_count} valid chart{'s' if valid_count != 1 else ''} ready for annotation", "success")
                    self.selectionComplete.emit(True)
                else:
                    # No valid charts
                    self._update_status_bar("❌ No valid charts found", "error")
                    self.selectionComplete.emit(False)
            else:
                # No candidates passed format validation
                self._update_status_bar("❌ No valid chart formats found", "error")
                self.valid_chart_ids = []
                self.selectionComplete.emit(False)
                
        except Exception as e:
            logger.exception("Error during chart validation")
            self._update_status_bar(f"❌ Validation error: {str(e)}", "error")
            self.valid_chart_ids = []
            self.selectionComplete.emit(False)
        finally:
            # Reconnect the text changed signal
            self.chart_input.textChanged.connect(self.on_text_changed)
    
    def get_selected_chart_ids(self):
        """Get list of valid chart IDs"""
        return self.valid_chart_ids.copy()


class AnnotationTab(QWidget):
    """Tab for creating the annotation"""
    annotationReady = Signal(bool)
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Status bar (same design as other tabs)
        self.status_widget = QWidget()
        self.status_layout = QHBoxLayout(self.status_widget)
        self.status_layout.setContentsMargins(0, 0, 0, 0)
        self.status_layout.setSpacing(8)
        
        self.status_label = QLabel("Enter annotation details to continue")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("QLabel { background-color: #e8f4fd; padding: 8px; border-radius: 4px; border-left: 4px solid #0078d4; }")
        self.status_layout.addWidget(self.status_label, 1)
        
        layout.addWidget(self.status_widget)
        
        # Annotation form
        form_group = QGroupBox("Annotation Details")
        form_layout = QFormLayout()
        
        # Date selector
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        form_layout.addRow("Affected Date:", self.date_edit)
        
        # Annotation name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Version 2.4 Release")
        self.name_input.textChanged.connect(self.validate_form)
        form_layout.addRow("Annotation Name:", self.name_input)
        
        # Description
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Optional description...")
        self.description_input.setMaximumHeight(100)
        form_layout.addRow("Description:", self.description_input)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        layout.addStretch()
    
    def _update_status_bar(self, message: str, status_type: str = "info") -> None:
        """Update the status bar with a message and appropriate styling."""
        self.status_label.setText(message)
        self.status_widget.show()
        
        if status_type == "success":
            self.status_label.setStyleSheet("QLabel { background-color: #d4edda; padding: 8px; border-radius: 4px; border-left: 4px solid #28a745; }")
        elif status_type == "error":
            self.status_label.setStyleSheet("QLabel { background-color: #f8d7da; padding: 8px; border-radius: 4px; border-left: 4px solid #dc3545; }")
        elif status_type == "warning":
            self.status_label.setStyleSheet("QLabel { background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 4px solid #ffc107; }")
        else:  # info
            self.status_label.setStyleSheet("QLabel { background-color: #e8f4fd; padding: 8px; border-radius: 4px; border-left: 4px solid #0078d4; }")
    
    def validate_form(self):
        """Check if form is valid"""
        is_valid = bool(self.name_input.text().strip())
        
        if is_valid:
            self._update_status_bar("✅ Annotation ready", "success")
        else:
            self._update_status_bar("Enter annotation details to continue", "info")
            
        self.annotationReady.emit(is_valid)
    

    
    def get_annotation_data(self):
        """Get annotation data"""
        return {
            'date': self.date_edit.date().toPython(),
            'label': self.name_input.text(),
            'details': self.description_input.toPlainText()
        }



class AmplitudeBulkAnnotator(QMainWindow):
    """Main application window"""
    
    def __init__(self) -> None:
        super().__init__()
        self.api_client: Optional[AmplitudeAPIClient] = None
        self.worker: Optional[APIWorker] = None
        self.init_ui()
    
    def init_ui(self) -> None:
        self.setWindowTitle("Amplitude Bulk Annotation Maker")
        self.setGeometry(100, 100, 900, 700)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.config_tab = ConfigTab()
        self.selection_tab = SelectionTab()
        self.annotation_tab = AnnotationTab()
        
        # Add tabs
        self.tab_widget.addTab(self.config_tab, "1. Configuration")
        self.tab_widget.addTab(self.selection_tab, "2. Select Charts")
        self.tab_widget.addTab(self.annotation_tab, "3. Create Annotation")
        
        # Initially disable tabs except config
        for i in range(1, 3):
            self.tab_widget.setTabEnabled(i, False)
        
        # Connect to tab changes to update button text
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        main_layout.addWidget(self.tab_widget)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        # Open Amplitude button (always visible)
        self.open_amplitude_btn = QPushButton("Open Amplitude")
        self.open_amplitude_btn.setStyleSheet("QPushButton { padding: 8px 16px; font-size: 11px; background-color: #0078d4; color: white; border: none; border-radius: 3px; } QPushButton:hover { background-color: #106ebe; }")
        self.open_amplitude_btn.clicked.connect(self.open_amplitude)
        button_layout.addWidget(self.open_amplitude_btn)
        
        button_layout.addStretch()
        
        self.apply_btn = QPushButton("Continue")
        self.apply_btn.clicked.connect(self.on_main_button_clicked)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setStyleSheet("QPushButton { padding: 10px 20px; }")
        button_layout.addWidget(self.apply_btn)
        
        main_layout.addLayout(button_layout)
        
        # Connect signals for tab progression
        self.config_tab.configValid.connect(self.on_config_valid)
        self.selection_tab.selectionComplete.connect(self.on_selection_complete)
        self.annotation_tab.annotationReady.connect(self.on_annotation_ready)
        
        # Auto-skip config tab if environment variables are complete
        if self.config_tab.has_complete_env_config():
            # Visual feedback that config is being auto-completed
            QTimer.singleShot(100, self.show_auto_config_status)
    
    def create_menu_bar(self) -> None:
        """Create the application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('&File')
        
        # Create .env template action
        create_env_action = QAction('&Create .env Template File', self)
        create_env_action.setStatusTip('Create a template .env file for easier credential management')
        create_env_action.triggered.connect(self.create_env_template_from_menu)
        file_menu.addAction(create_env_action)
        
        # Update menu item availability based on .env file existence
        self.update_menu_actions()
    
    def update_menu_actions(self) -> None:
        """Update menu actions based on current state."""
        # Note: Edit .env File moved to GUI, no longer in menu
        pass
    
    def create_env_template_from_menu(self) -> None:
        """Create .env template file from menu action."""
        if self.config_tab:
            self.config_tab.create_env_template()
            # Note: Edit .env File moved to GUI, no longer in menu
    

    
    def show_auto_config_status(self) -> None:
        """Show visual feedback for auto-configuration"""
        # Update window title temporarily
        original_title = self.windowTitle()
        self.setWindowTitle("Amplitude Bulk Annotation Maker - Auto-configuring...")
        
        # Restore original title after a brief moment
        QTimer.singleShot(2000, lambda: self.setWindowTitle(original_title))
    
    def open_amplitude(self) -> None:
        """Open Amplitude in the default browser"""
        import webbrowser
        
        # Just open the main Amplitude dashboard
        amplitude_url = "https://app.amplitude.com"
        
        try:
            webbrowser.open(amplitude_url)
            logger.info(f"Opened Amplitude URL: {amplitude_url}")
        except Exception as e:
            logger.error(f"Error opening Amplitude: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open browser:\n{str(e)}")
    
    def on_tab_changed(self, index: int) -> None:
        """Handle tab changes to update the main button text and state."""
        # Update button state based on current tab
        if index == 0:  # Configuration tab
            # Enable based on config validity
            config_valid = self.tab_widget.isTabEnabled(1)  # If next tab is enabled, config is valid
            self.apply_btn.setEnabled(config_valid)
        elif index == 1:  # Selection tab
            # Enable based on actual selection state from SelectionTab
            has_valid_charts = bool(self.selection_tab.valid_chart_ids)
            self.apply_btn.setEnabled(has_valid_charts)
        elif index == 2:  # Annotation tab
            # Enable based on annotation readiness (will be updated by annotation validation)
            self.apply_btn.setEnabled(False)  # Start disabled, will be enabled by validation
        
        self.update_main_button()
    
    def update_main_button(self) -> None:
        """Update the main button text and styling based on current tab and state."""
        current_index = self.tab_widget.currentIndex()
        
        if current_index == 0:  # Configuration tab
            self.apply_btn.setText("Continue")
            # Check if config is valid to determine styling
            is_enabled = self.apply_btn.isEnabled()
            if is_enabled:
                self.apply_btn.setStyleSheet("QPushButton { padding: 10px 20px; background-color: #4CAF50; color: white; font-weight: bold; }")
            else:
                self.apply_btn.setStyleSheet("QPushButton { padding: 10px 20px; }")
        elif current_index == 1:  # Selection tab
            self.apply_btn.setText("Continue")
            # Check if selection is complete to determine styling
            is_enabled = self.apply_btn.isEnabled()
            if is_enabled:
                self.apply_btn.setStyleSheet("QPushButton { padding: 10px 20px; background-color: #4CAF50; color: white; font-weight: bold; }")
            else:
                self.apply_btn.setStyleSheet("QPushButton { padding: 10px 20px; }")
        elif current_index == 2:  # Annotation tab
            self.apply_btn.setText("Apply Annotations")
            # Check if annotation is ready to determine styling
            is_enabled = self.apply_btn.isEnabled()
            if is_enabled:
                self.apply_btn.setStyleSheet("QPushButton { padding: 10px 20px; background-color: #4CAF50; color: white; font-weight: bold; }")
            else:
                self.apply_btn.setStyleSheet("QPushButton { padding: 10px 20px; }")
    
    def on_main_button_clicked(self) -> None:
        """Handle the main button click based on the current tab."""
        current_index = self.tab_widget.currentIndex()
        
        if current_index == 0:  # Configuration tab - continue to step 2
            if self.tab_widget.isTabEnabled(1):
                self.tab_widget.setCurrentIndex(1)
        elif current_index == 1:  # Selection tab - continue to step 3
            if self.tab_widget.isTabEnabled(2):
                self.tab_widget.setCurrentIndex(2)
        elif current_index == 2:  # Annotation tab - apply annotations
            self.apply_annotations()
    
    def on_config_valid(self, valid: bool) -> None:
        """Handle configuration validation"""
        self.tab_widget.setTabEnabled(1, valid)
        
        # Only enable Continue button if we're on the config tab and config is valid
        current_index = self.tab_widget.currentIndex()
        if current_index == 0:  # Configuration tab
            self.apply_btn.setEnabled(valid)
        
        self.update_main_button()
        
        if valid:
            # Pass API client to selection tab
            self.api_client = self.config_tab.get_api_client()
            project_id = self.config_tab.get_selected_project_id()
            self.selection_tab.set_api_client(self.api_client, project_id)
    
    def on_selection_complete(self, has_selection: bool) -> None:
        """Handle selection completion"""
        self.tab_widget.setTabEnabled(2, has_selection)
        current_index = self.tab_widget.currentIndex()
        if current_index == 1:  # Only enable button if we're on the selection tab
            self.apply_btn.setEnabled(has_selection)
        self.update_main_button()
        
        # Note: Removed auto-progression - users now manually click Continue
    
    def on_annotation_ready(self, ready: bool) -> None:
        """Handle annotation readiness"""
        current_index = self.tab_widget.currentIndex()
        if current_index == 2:  # Only enable button if we're on the annotation tab
            self.apply_btn.setEnabled(ready and self.tab_widget.isTabEnabled(2))
        self.update_main_button()
    
    def apply_annotations(self) -> None:
        """Apply annotations to selected charts"""
        # Validate API client is available
        if not self.api_client:
            QMessageBox.critical(self, "Error", "API client not configured. Please configure API settings first.")
            return
        
        # Get data with validation
        project_id = self.config_tab.get_selected_project_id()
        if not project_id:
            QMessageBox.critical(self, "Error", "Invalid project ID. Please check your configuration.")
            return
            
        chart_ids = self.selection_tab.get_selected_chart_ids()
        if not chart_ids:
            QMessageBox.critical(self, "Error", "No valid chart IDs selected. Please select charts first.")
            return
            
        annotation_data = self.annotation_tab.get_annotation_data()
        if not annotation_data.get('label', '').strip():
            QMessageBox.critical(self, "Error", "Annotation name is required.")
            return
        
        # Show progress dialog
        progress = QProgressDialog("Applying annotations...", "Cancel", 0, len(chart_ids), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        # Create worker thread
        self.worker = APIWorker(
            self.api_client,
            "bulk_annotate",
            project_id,
            chart_ids,
            annotation_data['date'],
            annotation_data['label'],
            annotation_data['details']
        )
        
        # Connect signals
        self.worker.progress.connect(lambda curr, total: progress.setValue(curr))
        self.worker.finished.connect(lambda success, message: self.on_annotations_complete(success, message, progress))
        
        # Handle progress dialog cancellation
        progress.canceled.connect(self.worker.terminate)
        
        # Start worker
        try:
            self.worker.start()
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Failed to start annotation process: {str(e)}")
            logger.exception("Failed to start worker thread")
    
    def on_annotations_complete(self, success: bool, message: str, progress_dialog: QProgressDialog) -> None:
        """Handle annotation completion"""
        progress_dialog.close()
        
        # Clean up worker thread
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        
        # Show success/completion popup with custom buttons
        if success:
            self.show_completion_dialog(
                "Success! ✅",
                f"{message}\n\nYour annotations have been applied to the selected charts. "
                f"You can view them in Amplitude."
            )
        else:
            self.show_completion_dialog(
                "Partial Success ⚠️",
                f"{message}\n\nSome annotations may have failed. "
                f"Please check your charts in Amplitude and retry if needed."
            )
    
    def show_completion_dialog(self, title: str, message: str) -> None:
        """Show completion dialog with custom action buttons."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        dialog.setIcon(QMessageBox.Icon.Information)
        
        # Create custom buttons
        create_another_btn = dialog.addButton("Create Another Annotation", QMessageBox.ButtonRole.AcceptRole)
        new_charts_btn = dialog.addButton("Enter New Charts", QMessageBox.ButtonRole.ActionRole)
        close_app_btn = dialog.addButton("Close App", QMessageBox.ButtonRole.RejectRole)
        
        # Set the primary/default button (highlighted)
        dialog.setDefaultButton(create_another_btn)
        
        # Show dialog and handle response
        dialog.exec()
        clicked_button = dialog.clickedButton()
        
        if clicked_button == create_another_btn:
            # Create another annotation - just stay in current tab (Step 3)
            # Reset the apply button to be ready for next annotation
            self.update_main_button()
        elif clicked_button == new_charts_btn:
            # Enter new charts - return to Step 2
            self.tab_widget.setCurrentIndex(1)
            # Button state will be updated by tab change and selection state
        elif clicked_button == close_app_btn:
            # Close app
            self.close()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    
    window = AmplitudeBulkAnnotator()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 