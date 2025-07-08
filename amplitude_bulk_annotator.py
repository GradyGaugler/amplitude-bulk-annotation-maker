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
        
        # Environment status info
        self.env_status_label = QLabel()
        self.env_status_label.setWordWrap(True)
        self.env_status_label.setStyleSheet("QLabel { background-color: #e8f4fd; padding: 8px; border-radius: 4px; border-left: 4px solid #0078d4; }")
        layout.addWidget(self.env_status_label)
        
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
            
            # Update status label
            self.env_status_label.setText("📄 .env file created! Use File → Edit .env File to add your credentials, then restart the application.")
            self.env_status_label.setStyleSheet("QLabel { background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 4px solid #ffc107; }")
            
            # Update the file note and add to layout if not already present
            self.env_file_note.setText("💡 Use File → Edit .env File to modify your credentials")
            
            # Check if env_note_layout is already in the main layout
            main_layout = self.layout()
            if isinstance(main_layout, QVBoxLayout):
                # Check if the note layout is already added (avoid duplicates)
                layout_found = False
                for i in range(main_layout.count()):
                    if main_layout.itemAt(i).layout() == self.env_note_layout:
                        layout_found = True
                        break
                
                if not layout_found:
                    main_layout.insertLayout(1, self.env_note_layout)
            
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
        # Update status and note based on .env file existence
        if self._env_file_exists():
            self.env_status_label.setText("🔒 Configuration loaded from .env file")
            self.env_file_note.setText("💡 Use File → Edit .env File to modify credentials")
            # Add the note layout since .env file exists
            main_layout = self.layout()
            if isinstance(main_layout, QVBoxLayout):
                main_layout.insertLayout(1, self.env_note_layout)
        else:
            # Environment variables are from system environment, not .env file
            self.env_status_label.setText("🔒 Configuration loaded from system environment variables")
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
        
        self.status_text.setText("✅ Using environment variables - auto-testing connection...")
    
    def _setup_manual_credentials(self, env_project_id: Optional[str]) -> None:
        """Set up UI for manual credential input."""
        # Update status and note based on .env file existence
        if self._env_file_exists():
            self.env_status_label.setText("📄 .env file exists but contains no valid credentials - edit the file or enter credentials manually below")
            self.env_status_label.setStyleSheet("QLabel { background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 4px solid #ffc107; }")
            self.env_file_note.setText("💡 Use File → Edit .env File to update credentials")
            # Add the note layout since .env file exists
            main_layout = self.layout()
            if isinstance(main_layout, QVBoxLayout):
                main_layout.insertLayout(1, self.env_note_layout)
        else:
            self.env_status_label.setText("💡 Enter your Amplitude credentials below")
            self.env_status_label.setStyleSheet("QLabel { background-color: #cce5ff; padding: 8px; border-radius: 4px; border-left: 4px solid #007bff; }")
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
                self.status_text.setText("⚠️ Error loading preferences (invalid format)")
            except IOError as e:
                logger.error(f"Error reading config file: {e}")
                self.status_text.setText("⚠️ Error loading preferences")
        
        # Show ready status for manual input
        if self._env_file_exists():
            self.status_text.setText("Ready for manual credential input (use File → Edit .env File or enter credentials manually)")
        else:
            self.status_text.setText("Ready for manual credential input")
    
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
            "Validation indicators will appear inline: ✅ valid, ❌ invalid"
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
        
        # Summary
        self.summary_label = QLabel("Ready to parse chart input")
        self.summary_label.setStyleSheet("QLabel { font-weight: bold; }")
        layout.addWidget(self.summary_label)
        
        layout.addStretch()
    
    def set_api_client(self, api_client, project_id):
        """Set API client and project ID"""
        self.api_client = api_client
        self.project_id = project_id
    
    def on_text_changed(self):
        """Handle text changes in the input area"""
        has_input = bool(self.chart_input.toPlainText().strip())
        if has_input:
            self.summary_label.setText("Input detected - click 'Validate Chart IDs' to process")
        else:
            self.summary_label.setText("Ready to parse chart input")
            self.valid_chart_ids = []
            self.selectionComplete.emit(False)
    
    def parse_input(self):
        """Parse and validate the input text with inline emoji indicators"""
        input_text = self.chart_input.toPlainText()
        
        if not input_text.strip():
            self.summary_label.setText("No charts to process")
            self.valid_chart_ids = []
            self.selectionComplete.emit(False)
            return
        
        # Temporarily disconnect the text changed signal to avoid recursion
        self.chart_input.textChanged.disconnect()
        
        try:
            # Split input into lines for processing
            lines = input_text.strip().split('\n')
            processed_lines = []
            all_chart_ids = []
            
            for line in lines:
                original_line = line.strip()
                if not original_line:
                    processed_lines.append("")
                    continue
                
                # Remove any existing emoji indicators
                clean_line = original_line
                for emoji in ['✅', '❌']:
                    clean_line = clean_line.replace(f' {emoji}', '').replace(f'{emoji} ', '').replace(emoji, '')
                clean_line = clean_line.strip()
                
                # Extract chart IDs from this line
                from utils.validators import extract_chart_ids, validate_chart_ids
                line_chart_ids = extract_chart_ids(clean_line)
                
                if line_chart_ids:
                    # Validate the extracted IDs
                    valid_ids, invalid_ids = validate_chart_ids(line_chart_ids)
                    all_chart_ids.extend(valid_ids)
                    
                    # Add emoji indicator based on validation
                    if valid_ids and not invalid_ids:
                        # All IDs in this line are valid
                        processed_lines.append(f"{clean_line} ✅")
                    elif invalid_ids and not valid_ids:
                        # All IDs in this line are invalid
                        processed_lines.append(f"{clean_line} ❌")
                    else:
                        # Mixed results - show both
                        processed_lines.append(f"{clean_line} ✅❌")
                else:
                    # No chart IDs found
                    processed_lines.append(f"{clean_line} ❌")
            
            # Update the text area with indicators
            new_text = '\n'.join(processed_lines)
            cursor_position = self.chart_input.textCursor().position()
            self.chart_input.setPlainText(new_text)
            
            # Restore cursor position (approximately)
            cursor = self.chart_input.textCursor()
            cursor.setPosition(min(cursor_position, len(new_text)))
            self.chart_input.setTextCursor(cursor)
            
            # Update summary and signal
            self.valid_chart_ids = list(set(all_chart_ids))  # Remove duplicates
            if self.valid_chart_ids:
                count = len(self.valid_chart_ids)
                self.summary_label.setText(f"✅ Ready to annotate {count} chart{'s' if count != 1 else ''}")
                self.selectionComplete.emit(True)
            else:
                self.summary_label.setText("❌ No valid charts to process")
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
        
        # Header
        header_label = QLabel("Amplitude Bulk Annotation Tool")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header_label)
        
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
        
        # Open .env file action (if it exists)
        self.open_env_action = QAction('&Edit .env File', self)
        self.open_env_action.setStatusTip('Edit the existing .env file')
        self.open_env_action.triggered.connect(self.open_env_file_from_menu)
        file_menu.addAction(self.open_env_action)
        
        # Update menu item availability based on .env file existence
        self.update_menu_actions()
    
    def update_menu_actions(self) -> None:
        """Update menu actions based on current state."""
        env_exists = os.path.exists('.env')
        self.open_env_action.setEnabled(env_exists)
    
    def create_env_template_from_menu(self) -> None:
        """Create .env template file from menu action."""
        if self.config_tab:
            self.config_tab.create_env_template()
            # Update menu after creating file
            self.update_menu_actions()
    
    def open_env_file_from_menu(self) -> None:
        """Open .env file from menu action."""
        if self.config_tab:
            self.config_tab.open_env_file()
    
    def show_auto_config_status(self) -> None:
        """Show visual feedback for auto-configuration"""
        # Update window title temporarily
        original_title = self.windowTitle()
        self.setWindowTitle("Amplitude Bulk Annotation Maker - Auto-configuring...")
        
        # Restore original title after a brief moment
        QTimer.singleShot(2000, lambda: self.setWindowTitle(original_title))
    
    def on_tab_changed(self, index: int) -> None:
        """Handle tab changes to update the main button text."""
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
        self.apply_btn.setEnabled(valid)
        self.update_main_button()
        
        if valid:
            # Pass API client to selection tab
            self.api_client = self.config_tab.get_api_client()
            project_id = self.config_tab.get_selected_project_id()
            self.selection_tab.set_api_client(self.api_client, project_id)
            
            # Auto-progress to next tab (faster if using env vars)
            delay = 200 if self.config_tab.has_complete_env_config() else 500
            QTimer.singleShot(delay, lambda: self.tab_widget.setCurrentIndex(1))
    
    def on_selection_complete(self, has_selection: bool) -> None:
        """Handle selection completion"""
        self.tab_widget.setTabEnabled(2, has_selection)
        current_index = self.tab_widget.currentIndex()
        if current_index == 1:  # Only enable button if we're on the selection tab
            self.apply_btn.setEnabled(has_selection)
        self.update_main_button()
        
        if has_selection:
            # Auto-progress to next tab
            QTimer.singleShot(100, lambda: self.tab_widget.setCurrentIndex(2))
    
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