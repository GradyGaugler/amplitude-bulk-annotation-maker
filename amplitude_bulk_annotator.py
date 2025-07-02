#!/usr/bin/env python3
"""
Amplitude Bulk Annotation Maker
A GUI application for applying annotations to multiple Amplitude charts at once.
"""
import sys
import json
import os
from datetime import date
from typing import List, Dict, Optional, Set
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

from amplitude_api import AmplitudeAPIClient

# Environment variable names for Amplitude credentials
ENV_API_KEY = "AMPLITUDE_API_KEY"
ENV_SECRET_KEY = "AMPLITUDE_SECRET_KEY"
ENV_PROJECT_ID = "AMPLITUDE_PROJECT_ID"
ENV_REGION = "AMPLITUDE_REGION"


class APIWorker(QThread):
    """Worker thread for API operations"""
    finished = Signal(bool, str)
    progress = Signal(int, int)
    
    def __init__(self, api_client, operation, *args, **kwargs):
        super().__init__()
        self.api_client = api_client
        self.operation = operation
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            if self.operation == "test_connection":
                success, message = self.api_client.test_connection()
                self.finished.emit(success, message)
            elif self.operation == "bulk_annotate":
                results = self.api_client.bulk_annotate(
                    *self.args,
                    progress_callback=lambda curr, total: self.progress.emit(curr, total),
                    **self.kwargs
                )
                # Summarize results
                success_count = sum(1 for _, success, _ in results if success)
                total_count = len(results)
                message = f"Completed: {success_count}/{total_count} successful"
                self.finished.emit(success_count == total_count, message)
        except Exception as e:
            self.finished.emit(False, str(e))


class ConfigTab(QWidget):
    """Configuration tab for API settings"""
    configValid = Signal(bool)
    
    def __init__(self):
        super().__init__()
        self.api_client = None
        self.config_file = "amplitude_preferences.json"  # Only for non-sensitive preferences
        self.credentials_from_env = False
        self.init_ui()
        self.load_config()
        
        # Auto-test connection if environment variables are complete
        if self.has_complete_env_config():
            QTimer.singleShot(500, self.auto_test_connection)
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # API Configuration group
        api_group = QGroupBox("API Configuration")
        api_layout = QFormLayout()
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Your Amplitude API Key")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow("API Key:", self.api_key_input)
        
        self.secret_key_input = QLineEdit()
        self.secret_key_input.setPlaceholderText("Your Amplitude Secret Key")
        self.secret_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow("Secret Key:", self.secret_key_input)
        
        self.region_combo = QComboBox()
        self.region_combo.addItems(["US", "EU"])
        api_layout.addRow("Region:", self.region_combo)
        
        self.project_id_input = QLineEdit()
        self.project_id_input.setPlaceholderText("e.g., 123456")
        api_layout.addRow("Project ID:", self.project_id_input)
        
        # Help text
        help_label = QLabel("Find your API keys and Project ID in Amplitude Settings > Projects")
        help_label.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        api_layout.addRow("", help_label)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # Test connection button
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self.test_connection)
        layout.addWidget(self.test_btn)
        
        # Status text
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        layout.addWidget(self.status_text)
        
        layout.addStretch()
        
        # Save preferences button
        self.save_config_btn = QPushButton("Save Preferences")
        self.save_config_btn.clicked.connect(self.save_config)
        layout.addWidget(self.save_config_btn)
    
    def load_config(self):
        """Load configuration from environment variables first, then file for preferences"""
        # Check for environment variables first (recommended approach)
        env_api_key = os.getenv(ENV_API_KEY)
        env_secret_key = os.getenv(ENV_SECRET_KEY)
        env_project_id = os.getenv(ENV_PROJECT_ID)
        env_region = os.getenv(ENV_REGION, 'US')
        
        if env_api_key and env_secret_key:
            # Credentials found in environment variables
            self.credentials_from_env = True
            self.api_key_input.setText("••••••••••••••••")  # Show masked placeholder
            self.api_key_input.setEnabled(False)
            self.api_key_input.setToolTip("API Key loaded from environment variable")
            
            self.secret_key_input.setText("••••••••••••••••")  # Show masked placeholder
            self.secret_key_input.setEnabled(False)
            self.secret_key_input.setToolTip("Secret Key loaded from environment variable")
            
            if env_project_id:
                self.project_id_input.setText(env_project_id)
                self.project_id_input.setEnabled(False)
                self.project_id_input.setToolTip("Project ID loaded from environment variable")
            
            self.region_combo.setCurrentText(env_region)
            
            # Show status
            self.status_text.setText("✅ Using environment variables - auto-testing connection...")
        else:
            # No environment variables, allow manual input
            self.credentials_from_env = False
            self.api_key_input.setEnabled(True)
            self.secret_key_input.setEnabled(True)
            self.project_id_input.setEnabled(True)
            
            # Load preferences from file (non-sensitive settings only)
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, 'r') as f:
                        config = json.load(f)
                        self.region_combo.setCurrentText(config.get('region', 'US'))
                        
                        # Only load project_id from file if not in environment
                        if not env_project_id:
                            self.project_id_input.setText(config.get('project_id', ''))
                except Exception as e:
                    self.status_text.setText(f"Error loading preferences: {str(e)}")
            
            # Show ready status for manual input
            self.status_text.setText("Ready for manual credential input")
    
    def save_config(self):
        """Save non-sensitive preferences only"""
        if self.credentials_from_env:
            self.status_text.append("ℹ️  Credentials are from environment variables - only saving preferences")
        
        # Only save non-sensitive preferences
        config = {
            'region': self.region_combo.currentText(),
        }
        
        # Only save project_id if it's not from environment variables
        if not os.getenv(ENV_PROJECT_ID) and self.project_id_input.text():
            config['project_id'] = self.project_id_input.text()
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            self.status_text.append("✅ Preferences saved successfully")
        except Exception as e:
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
        self.test_btn.setText("Testing...")
        self.status_text.setText("Testing connection...")
    
    def on_test_complete(self, success, message):
        """Handle test completion"""
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Test Connection")
        
        if success:
            self.status_text.setText(f"✅ {message}")
            
            # Check if project ID is provided (from environment or manual input)
            project_id = self.get_selected_project_id()
            if project_id:
                self.status_text.append(f"Project ID: {project_id}")
                self.configValid.emit(True)
            else:
                self.status_text.append("❌ Please provide a valid Project ID")
                self.configValid.emit(False)
        else:
            self.status_text.setText(f"❌ {message}")
            self.configValid.emit(False)
    
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
        if self.api_client:
            extracted_ids = self.api_client.extract_chart_ids(input_text)
        else:
            # Fallback extraction if no API client
            from amplitude_api import AmplitudeAPIClient
            extracted_ids = AmplitudeAPIClient.extract_chart_ids(input_text)
        
        if not extracted_ids:
            self.results_text.setText("❌ No valid chart IDs or URLs found in input")
            self.summary_label.setText("No valid charts found")
            self.valid_chart_ids = []
            self.selectionComplete.emit(False)
            return
        
        # Validate chart IDs
        if self.api_client:
            valid_ids, invalid_ids = self.api_client.validate_chart_ids(extracted_ids)
        else:
            from amplitude_api import AmplitudeAPIClient
            valid_ids, invalid_ids = AmplitudeAPIClient.validate_chart_ids(extracted_ids)
        
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