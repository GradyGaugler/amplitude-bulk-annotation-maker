#!/usr/bin/env python3
"""
Amplitude Bulk Annotation Maker.

A GUI application for applying annotations to multiple Amplitude charts at once.
Built with Python 3.13 and PySide6, following best practices for code organization,
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

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QTextEdit,
    QGroupBox, QComboBox, QListWidget, QListWidgetItem,
    QCompleter, QDateEdit, QMessageBox, QProgressDialog,
    QSplitter, QTreeWidget, QTreeWidgetItem, QCheckBox,
    QFormLayout, QDialogButtonBox, QDialog, QFileDialog
)
from PySide6.QtCore import Qt, QDate, Signal, QThread, QTimer, QStringListModel
from PySide6.QtGui import QIcon, QFont

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()  # This loads .env file automatically
except ImportError:
    pass  # python-dotenv not installed, skip

from amplitude_api import AmplitudeAPIClient, AmplitudeAPIError
from constants import (
    APP_NAME, APP_VERSION,
    ENV_API_KEY, ENV_SECRET_KEY, ENV_PROJECT_ID, ENV_REGION,
    CONFIG_FILE, DEFAULT_REGION, VALID_REGIONS,
    WINDOW_WIDTH, WINDOW_HEIGHT,
    STATUS_TEXT_MAX_HEIGHT, DESCRIPTION_MAX_HEIGHT,
    CHART_INPUT_MIN_HEIGHT, RESULTS_TEXT_MAX_HEIGHT,
    MASKED_CREDENTIAL_DISPLAY, DATE_FORMAT,
    AUTO_TEST_DELAY, AUTO_TEST_DELAY_FAST, AUTO_PROGRESS_DELAY,
    STATUS_DISPLAY_DURATION,
    TAB_CONFIG, TAB_SELECTION, TAB_ANNOTATION, TAB_RESULTS
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
        
        # Environment status info
        self.env_status_label = QLabel()
        self.env_status_label.setWordWrap(True)
        self.env_status_label.setStyleSheet("QLabel { background-color: #e8f4fd; padding: 8px; border-radius: 4px; border-left: 4px solid #0078d4; }")
        layout.addWidget(self.env_status_label)
        
        # .env file management buttons
        env_buttons_layout = QHBoxLayout()
        
        # Create .env button (only shown when no .env file exists)
        self.create_env_btn = QPushButton("📄 Create .env Template File")
        self.create_env_btn.clicked.connect(self.create_env_template)
        self.create_env_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; padding: 8px; font-weight: bold; }")
        env_buttons_layout.addWidget(self.create_env_btn)
        
        # Open .env button (only shown when .env file exists)
        self.open_env_btn = QPushButton("📝 Edit .env File")
        self.open_env_btn.clicked.connect(self.open_env_file)
        self.open_env_btn.setStyleSheet("QPushButton { background-color: #17a2b8; color: white; padding: 8px; font-weight: bold; }")
        env_buttons_layout.addWidget(self.open_env_btn)
        
        env_buttons_layout.addStretch()  # Push buttons to the left
        layout.addLayout(env_buttons_layout)
        
        # API Configuration group
        api_group = QGroupBox("API Configuration")
        api_layout = QFormLayout()
        
        # API Key
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Your Amplitude API Key")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow("API Key:", self.api_key_input)
        
        # Secret Key
        self.secret_key_input = QLineEdit()
        self.secret_key_input.setPlaceholderText("Your Amplitude Secret Key")
        self.secret_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow("Secret Key:", self.secret_key_input)
        
        # Region
        self.region_combo = QComboBox()
        self.region_combo.addItems(VALID_REGIONS)
        api_layout.addRow("Region:", self.region_combo)
        
        # Project ID
        self.project_id_input = QLineEdit()
        self.project_id_input.setPlaceholderText("e.g., 123456")
        api_layout.addRow("Project ID:", self.project_id_input)
        
        # Help text
        help_label = QLabel("Find your API keys and Project ID in Amplitude Settings > Projects")
        help_label.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        api_layout.addRow("", help_label)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # Test connection and save button (combined)
        self.test_btn = QPushButton("Test Connection and Save")
        self.test_btn.clicked.connect(self.test_connection)
        self.test_btn.setStyleSheet("QPushButton { padding: 8px 16px; font-weight: bold; }")
        layout.addWidget(self.test_btn)
        
        # Status text
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(STATUS_TEXT_MAX_HEIGHT)
        layout.addWidget(self.status_text)
        
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
    
    def _env_file_exists(self) -> bool:
        """Check if .env file exists in the current directory."""
        return os.path.exists('.env')
    
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
            
            self.status_text.setText("✅ .env template file created successfully!\n\n"
                                   "📝 Please edit the .env file with your actual Amplitude credentials, "
                                   "then restart the application.")
            
            # Update button visibility - hide create, show edit
            self.create_env_btn.hide()
            self.open_env_btn.show()
            
            # Update status label
            self.env_status_label.setText("📄 .env file created! Click 'Edit .env File' to add your credentials, then restart the application.")
            self.env_status_label.setStyleSheet("QLabel { background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 4px solid #ffc107; }")
            
            logger.info(".env template file created successfully")
            
        except IOError as e:
            logger.error(f"Error creating .env file: {e}")
            self.status_text.setText(f"❌ Error creating .env file: {str(e)}")
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
            
            self.status_text.append(f"\n📝 Opened .env file in default editor")
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
        # Show edit button if .env file exists, hide create button
        if self._env_file_exists():
            self.create_env_btn.hide()
            self.open_env_btn.show()
            self.env_status_label.setText("🔒 Configuration loaded from .env file - click 'Edit .env File' to modify credentials")
        else:
            # Environment variables are from system environment, not .env file
            self.create_env_btn.hide()
            self.open_env_btn.hide()
            self.env_status_label.setText("🔒 Configuration loaded from system environment variables")
        
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
        
        self.status_text.setText("✅ Using environment variables - auto-testing connection...")
    
    def _setup_manual_credentials(self, env_project_id: Optional[str]) -> None:
        """Set up UI for manual credential input."""
        # Show appropriate buttons based on .env file existence
        if self._env_file_exists():
            self.create_env_btn.hide()
            self.open_env_btn.show()
            self.env_status_label.setText("📄 .env file exists but contains no valid credentials - edit the file or enter credentials manually below")
            self.env_status_label.setStyleSheet("QLabel { background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 4px solid #ffc107; }")
        else:
            self.create_env_btn.show()
            self.open_env_btn.hide()
            self.env_status_label.setText("💡 No .env file found - you can create one for easier credential management, or enter credentials manually below")
            self.env_status_label.setStyleSheet("QLabel { background-color: #cce5ff; padding: 8px; border-radius: 4px; border-left: 4px solid #007bff; }")
        
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
                self.status_text.setText("⚠️ Error loading preferences (invalid format)")
            except IOError as e:
                logger.error(f"Error reading config file: {e}")
                self.status_text.setText("⚠️ Error loading preferences")
        
        # Show ready status for manual input
        if self._env_file_exists():
            self.status_text.setText("Ready for manual credential input (click 'Edit .env File' or enter credentials manually)")
        else:
            self.status_text.setText("Ready for manual credential input (click 'Create .env Template File' for easier management)")
    
    def save_config(self) -> None:
        """
        Save non-sensitive preferences only.
        
        Never saves API keys or secrets to disk for security reasons.
        """
        if self.credentials_from_env:
            self.status_text.append("ℹ️  Credentials are from environment variables - only saving preferences")
        
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
            self.status_text.append("✅ Preferences saved successfully")
            logger.info("Preferences saved to file")
        except IOError as e:
            logger.error(f"Error saving preferences: {e}")
            self.status_text.append(f"❌ Error saving preferences: {str(e)}")
    
    def test_connection(self):
        """Test the API connection"""
        # Get credentials from environment or manual input
        if self.credentials_from_env:
            api_key = os.getenv(ENV_API_KEY)
            secret_key = os.getenv(ENV_SECRET_KEY)
        else:
            api_key = self.api_key_input.text()
            secret_key = self.secret_key_input.text()
        
        if not api_key or not secret_key:
            self.status_text.setText("❌ Please provide both API key and secret key")
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
        self.status_text.setText("Testing connection...")
    
    def on_test_complete(self, success, message):
        """Handle test completion and save preferences if successful"""
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Test Connection and Save")
        
        if success:
            self.status_text.setText(f"✅ {message}")
            
            # Check if project ID is provided (from environment or manual input)
            project_id = self.get_selected_project_id()
            if project_id:
                self.status_text.append(f"Project ID: {project_id}")
                
                # Automatically save preferences on successful connection
                self.status_text.append("\n📝 Saving preferences...")
                self._save_preferences_after_test()
                
                self.configValid.emit(True)
            else:
                self.status_text.append("❌ Please provide a valid Project ID")
                self.configValid.emit(False)
        else:
            self.status_text.setText(f"❌ {message}")
            self.status_text.append("⚠️ Preferences not saved due to connection failure")
            self.configValid.emit(False)
    
    def _save_preferences_after_test(self):
        """Save preferences after successful connection test"""
        # Call the existing save_config method but suppress duplicate status messages
        original_text = self.status_text.toPlainText()
        self.save_config()
        
        # Remove any duplicate "saved successfully" messages that might have been added
        current_text = self.status_text.toPlainText()
        if "✅ Preferences saved successfully" in current_text and original_text.count("✅ Preferences saved successfully") < current_text.count("✅ Preferences saved successfully"):
            # The save_config method added a success message, we're good
            pass
    
    def get_api_client(self):
        return self.api_client if hasattr(self, 'api_client') else None
    
    def get_selected_project_id(self):
        """Get the selected project ID from environment or manual input"""
        env_project_id = os.getenv(ENV_PROJECT_ID)
        if env_project_id and env_project_id.isdigit():
            return int(env_project_id)
        
        project_id = self.project_id_input.text().strip()
        return int(project_id) if project_id.isdigit() else None
    
    def has_complete_env_config(self):
        """Check if all required environment variables are set"""
        return (os.getenv(ENV_API_KEY) and 
                os.getenv(ENV_SECRET_KEY) and 
                os.getenv(ENV_PROJECT_ID))
    
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
        
        # Instructions
        instructions = QLabel(
            "Enter chart IDs or URLs below (one per line):\n\n"
            "• Chart ID: ez25o7zy\n"
            "• Full URL: https://app.amplitude.com/analytics/gitkraken/chart/ez25o7zy\n"
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
            "def456, ghi789"
        )
        self.chart_input.setMinimumHeight(150)
        self.chart_input.textChanged.connect(self.validate_input)
        input_layout.addWidget(self.chart_input)
        
        # Parse button
        self.parse_btn = QPushButton("Parse and Validate Chart IDs")
        self.parse_btn.clicked.connect(self.parse_input)
        input_layout.addWidget(self.parse_btn)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # Validation results
        results_group = QGroupBox("Validation Results")
        results_layout = QVBoxLayout()
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(150)
        results_layout.addWidget(self.results_text)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # Summary
        self.summary_label = QLabel("Ready to parse chart input")
        self.summary_label.setStyleSheet("QLabel { font-weight: bold; }")
        layout.addWidget(self.summary_label)
        
        layout.addStretch()
    
    def set_api_client(self, api_client, project_id):
        """Set API client and project ID"""
        self.api_client = api_client
        self.project_id = project_id
    
    def validate_input(self):
        """Check if there's any input to parse"""
        has_input = bool(self.chart_input.toPlainText().strip())
        if has_input:
            self.summary_label.setText("Input detected - click 'Parse and Validate' to process")
        else:
            self.summary_label.setText("Ready to parse chart input")
            self.results_text.clear()
            self.valid_chart_ids = []
            self.selectionComplete.emit(False)
    
    def parse_input(self):
        """Parse and validate the input text"""
        input_text = self.chart_input.toPlainText()
        
        if not input_text.strip():
            self.results_text.setText("No input provided")
            self.summary_label.setText("No charts to process")
            self.valid_chart_ids = []
            self.selectionComplete.emit(False)
            return
        
        # Extract chart IDs from input
        from utils.validators import extract_chart_ids
        extracted_ids = extract_chart_ids(input_text)
        
        if not extracted_ids:
            self.results_text.setText("❌ No valid chart IDs or URLs found in input")
            self.summary_label.setText("No valid charts found")
            self.valid_chart_ids = []
            self.selectionComplete.emit(False)
            return
        
        # Validate chart IDs
        from utils.validators import validate_chart_ids
        valid_ids, invalid_ids = validate_chart_ids(extracted_ids)
        
        # Build results text
        results = []
        
        if valid_ids:
            results.append(f"✅ Valid Chart IDs ({len(valid_ids)}):")
            for chart_id in valid_ids:
                results.append(f"   • {chart_id}")
        
        if invalid_ids:
            results.append(f"\n❌ Invalid Chart IDs ({len(invalid_ids)}):")
            for chart_id in invalid_ids:
                results.append(f"   • {chart_id}")
        
        if not valid_ids and not invalid_ids:
            results.append("No chart IDs found")
        
        self.results_text.setText("\n".join(results))
        
        # Update summary and signal
        self.valid_chart_ids = valid_ids
        if valid_ids:
            count = len(valid_ids)
            self.summary_label.setText(f"✅ Ready to annotate {count} chart{'s' if count != 1 else ''}")
            self.selectionComplete.emit(True)
        else:
            self.summary_label.setText("❌ No valid charts to process")
            self.selectionComplete.emit(False)
    
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
        
        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(100)
        preview_layout.addWidget(self.preview_text)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        layout.addStretch()
        
        # Update preview on changes
        self.name_input.textChanged.connect(self.update_preview)
        self.description_input.textChanged.connect(self.update_preview)
        self.date_edit.dateChanged.connect(self.update_preview)
        
        self.update_preview()
    
    def validate_form(self):
        """Check if form is valid"""
        is_valid = bool(self.name_input.text().strip())
        self.annotationReady.emit(is_valid)
    
    def update_preview(self):
        """Update the preview"""
        preview = f"Date: {self.date_edit.date().toString('yyyy-MM-dd')}\n"
        preview += f"Name: {self.name_input.text() or '(empty)'}\n"
        if self.description_input.toPlainText():
            preview += f"Description: {self.description_input.toPlainText()}"
        self.preview_text.setText(preview)
    
    def get_annotation_data(self):
        """Get annotation data"""
        return {
            'date': self.date_edit.date().toPython(),
            'label': self.name_input.text(),
            'details': self.description_input.toPlainText()
        }


class ResultsTab(QWidget):
    """Tab for showing results"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Results summary
        self.summary_label = QLabel("No annotations applied yet")
        self.summary_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.summary_label)
        
        # Results text
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)
        
        # Export button
        self.export_btn = QPushButton("Export Results")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)
    
    def set_results(self, results_text, summary):
        """Set the results"""
        self.summary_label.setText(summary)
        self.results_text.setText(results_text)
        self.export_btn.setEnabled(True)
    
    def export_results(self):
        """Export results to file"""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Results",
            "annotation_results.txt",
            "Text Files (*.txt)"
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.results_text.toPlainText())
                QMessageBox.information(self, "Success", "Results exported successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")


class AmplitudeBulkAnnotator(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.api_client = None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Amplitude Bulk Annotation Maker")
        self.setGeometry(100, 100, 900, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Header
        header_label = QLabel("Amplitude Bulk Annotation Tool")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header_label)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.config_tab = ConfigTab()
        self.selection_tab = SelectionTab()
        self.annotation_tab = AnnotationTab()
        self.results_tab = ResultsTab()
        
        # Add tabs
        self.tab_widget.addTab(self.config_tab, "1. Configuration")
        self.tab_widget.addTab(self.selection_tab, "2. Select Charts")
        self.tab_widget.addTab(self.annotation_tab, "3. Create Annotation")
        self.tab_widget.addTab(self.results_tab, "4. Results")
        
        # Initially disable tabs except config
        for i in range(1, 4):
            self.tab_widget.setTabEnabled(i, False)
        
        main_layout.addWidget(self.tab_widget)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.apply_btn = QPushButton("Apply Annotations")
        self.apply_btn.clicked.connect(self.apply_annotations)
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
    
    def show_auto_config_status(self):
        """Show visual feedback for auto-configuration"""
        # Update window title temporarily
        original_title = self.windowTitle()
        self.setWindowTitle("Amplitude Bulk Annotation Maker - Auto-configuring...")
        
        # Restore original title after a brief moment
        QTimer.singleShot(2000, lambda: self.setWindowTitle(original_title))
    
    def on_config_valid(self, valid):
        """Handle configuration validation"""
        self.tab_widget.setTabEnabled(1, valid)
        if valid:
            # Pass API client to selection tab
            self.api_client = self.config_tab.get_api_client()
            project_id = self.config_tab.get_selected_project_id()
            self.selection_tab.set_api_client(self.api_client, project_id)
            
            # Auto-progress to next tab (faster if using env vars)
            delay = 200 if self.config_tab.has_complete_env_config() else 500
            QTimer.singleShot(delay, lambda: self.tab_widget.setCurrentIndex(1))
    
    def on_selection_complete(self, has_selection):
        """Handle selection completion"""
        self.tab_widget.setTabEnabled(2, has_selection)
        if has_selection:
            # Auto-progress to next tab
            QTimer.singleShot(100, lambda: self.tab_widget.setCurrentIndex(2))
    
    def on_annotation_ready(self, ready):
        """Handle annotation readiness"""
        self.apply_btn.setEnabled(ready and self.tab_widget.isTabEnabled(2))
    
    def apply_annotations(self):
        """Apply annotations to selected charts"""
        # Get data
        project_id = self.config_tab.get_selected_project_id()
        chart_ids = self.selection_tab.get_selected_chart_ids()
        annotation_data = self.annotation_tab.get_annotation_data()
        
        # Show progress dialog
        progress = QProgressDialog("Applying annotations...", "Cancel", 0, len(chart_ids), self)
        progress.setWindowModality(Qt.WindowModal)
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
        
        # Start worker
        self.worker.start()
    
    def on_annotations_complete(self, success, message, progress_dialog):
        """Handle annotation completion"""
        progress_dialog.close()
        
        # Show results
        self.tab_widget.setTabEnabled(3, True)
        self.tab_widget.setCurrentIndex(3)
        
        # Update results tab
        results_text = f"Annotation Results\n{'='*50}\n\n"
        results_text += f"Status: {'Success' if success else 'Partial Success'}\n"
        results_text += f"Summary: {message}\n\n"
        results_text += "Details:\n"
        results_text += "- Check Amplitude for the applied annotations\n"
        
        self.results_tab.set_results(results_text, message)
        
        # Show message box
        if success:
            QMessageBox.information(self, "Success", "All annotations applied successfully!")
        else:
            QMessageBox.warning(self, "Partial Success", message)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    
    window = AmplitudeBulkAnnotator()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 