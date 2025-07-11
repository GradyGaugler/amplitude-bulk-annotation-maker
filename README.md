# Amplitude Bulk Annotation Maker

A Python GUI application for efficiently applying annotations to multiple Amplitude charts simultaneously. Built with Python 3.9+ and PySide6, following modern security and usability best practices.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage Guide](#usage-guide)
- [Security](#security)
- [Distribution](#distribution)
- [Troubleshooting](#troubleshooting)
- [Technical Details](#technical-details)

## Features

- **🔄 Bulk Operations**: Apply identical annotations to multiple charts in one operation
- **🔗 Flexible Input**: Accept chart IDs directly or extract from full Amplitude URLs
- **✅ Smart Validation**: Real-time validation of chart IDs and URLs with visual feedback
- **🔐 Secure Configuration**: Environment variable support with `.env` file integration
- **🎯 Guided Workflow**: Step-by-step interface with manual progression control
- **💾 Preference Storage**: Save non-sensitive settings for future sessions
- **🔄 Auto-Configuration**: Seamless setup when environment variables are detected
- **🎨 Modern Interface**: Clean, intuitive GUI built with PySide6
- **📊 Chart Validation**: API-based validation to ensure charts exist before annotation
- **🔄 Retry Logic**: Built-in retry mechanism with exponential backoff for reliability
- **📝 .env File Management**: Built-in tools to create and edit environment files

## Quick Start

For users who want to get started immediately:

### Windows
```bash
# Download and extract the application files
# Install Python 3.9+ if not already installed
run.bat
```

### macOS/Linux
```bash
# Download and extract the application files
chmod +x run.sh
./run.sh
```

The launch scripts automatically handle dependency installation and environment setup.

## Installation

### Prerequisites

- **Python 3.9+** (recommended: latest stable version)
- **PySide6 6.5.0+** (Qt 6 GUI framework)
- **Valid Amplitude account** with API credentials

### Why Python 3.9+?

This application uses modern Python features including:
- PEP 585 generic types (`list[str]` syntax)
- Advanced typing annotations with `Final`
- PySide6 which requires Python 3.9+

### Method 1: Automated Setup (Recommended)

1. **Download the application**
   ```bash
   # Extract all files to a folder of your choice
   cd amplitude-bulk-annotation-maker
   ```

2. **Run the launch script**
   - **Windows**: Double-click `run.bat` or run in terminal
   - **macOS/Linux**: Run `./run.sh` in terminal

   The script automatically:
   - Creates a virtual environment
   - Installs all dependencies
   - Launches the application

### Method 2: Manual Setup

1. **Clone or download the repository**
   ```bash
   git clone <repository-url>
   cd amplitude-bulk-annotation-maker
   ```

2. **(Optional) Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # macOS/Linux
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch application**
   ```bash
   python3 amplitude_bulk_annotator.py
   ```

### Dependencies

The application uses these key libraries:
- `PySide6` - Modern Qt-based GUI framework (6.5.0+)
- `requests` - HTTP client for Amplitude API (2.31.0+)
- `python-dotenv` - Environment variable management (1.0.0+)
- `python-dateutil` - Date handling utilities (2.8.2+)
- `typing-extensions` - Type hints for Python compatibility (4.7.0+)
- `urllib3` - HTTP retry utilities (1.26.0+, included with requests)

All dependencies are automatically installed when using the launch scripts (`run.bat` or `run.sh`).

## Configuration

The application supports multiple configuration methods, prioritizing security:

### 🔒 Recommended: Environment Variables

**Option A: `.env` File (Easiest)**
1. Launch the application
2. Go to **File** → **Create .env Template File**
3. Edit the created `.env` file with your credentials:
   ```env
   AMPLITUDE_API_KEY=your_actual_api_key
   AMPLITUDE_SECRET_KEY=your_actual_secret_key
   AMPLITUDE_PROJECT_ID=123456
   AMPLITUDE_REGION=US
   ```
4. Restart the application - credentials load automatically

**Built-in .env File Tools**:
- **Create Template**: Menu option to create a `.env` file with placeholders
- **Edit Button**: Direct access to edit the `.env` file from the Configuration tab
- **Auto-Detection**: Application automatically detects and loads `.env` files
- **Validation**: Clear status messages when `.env` files are invalid or missing values

**Option B: System Environment Variables**
```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
export AMPLITUDE_API_KEY="your_api_key"
export AMPLITUDE_SECRET_KEY="your_secret_key"
export AMPLITUDE_PROJECT_ID="123456"
export AMPLITUDE_REGION="US"  # Optional: US or EU
```

### 📝 Alternative: Manual Entry

If no environment variables are detected, the application provides a clean form for manual credential entry.

### Getting Your Amplitude Credentials

1. **API Keys**:
   - Log into Amplitude
   - Settings → Projects → [Your Project] → API Keys
   - Copy API Key and Secret Key

2. **Project ID**:
   - Settings → Projects
   - Note the numeric Project ID

3. **Region**: 
   - Usually "US" unless you specifically use EU servers

## Usage Guide

### Step 1: Configuration
- **With environment variables**: Credentials load automatically with secure display
- **Manual entry**: Enter credentials and test connection
- The interface adapts based on your setup method

### Step 2: Select Charts

Enter chart information in any of these formats:

**Chart IDs**:
```
ez25o7zy
abc123def
xyz789
```

**Full URLs**:
```
https://app.amplitude.com/analytics/demo/chart/ez25o7zy
https://app.amplitude.com/analytics/yourproject/chart/abc123def
```

**Mixed formats** (one per line):
```
ez25o7zy
https://app.amplitude.com/analytics/demo/chart/abc123def
xyz789, def456
```

**Real-time validation** provides immediate feedback with visual indicators:
- ⏳ Charts being validated with Amplitude API
- ✅ Valid chart IDs confirmed to exist
- ❌ Invalid or non-existent charts

The application validates both format and existence using the Amplitude API to ensure annotations will be successfully applied.

### Step 3: Create Annotation

1. **Select date**: Choose the date for your annotation
2. **Enter name**: Provide a descriptive annotation title (required)
3. **Add description**: Optional detailed description
4. **Apply**: Process all selected charts with progress tracking

### Results

The application provides detailed feedback:
- Progress bar during processing
- Success/failure status for each chart
- Completion dialog with options to:
  - Create another annotation (same charts)
  - Enter new charts
  - Close the application

### Workflow Features

**Manual Progression**: Users control when to move between steps using the "Continue" button
**Smart Validation**: Each step validates input before allowing progression
**Flexible Restart**: After completion, users can easily restart from any step
**Progress Persistence**: Chart selections and configuration remain available for creating multiple annotations

## Security

### 🔒 Security Best Practices

This application follows enterprise-grade security practices:

- **Environment Variables**: Sensitive credentials never stored in files
- **Masked Display**: API keys shown as `••••••••` in the interface
- **Read-only Fields**: Environment-loaded credentials cannot be accidentally modified
- **No Plain Text**: Manual entries are never saved to disk
- **Secure Transmission**: HTTPS-only API communication

### Important Security Notes

- **Never commit** `.env` files to version control (automatically ignored)
- **Never share** API keys in plain text or screenshots
- **Use environment variables** for production environments
- **Each user** needs their own Amplitude API credentials

## Distribution

### Sharing with Colleagues

```bash
python3 package_for_distribution.py
```

This creates a timestamped ZIP file with all necessary files:
- Application source code
- Dependencies list
- Documentation
- Launch scripts
- Setup instructions

**Important**: Recipients need their own Amplitude API keys.

### What's Included

- Complete application files
- Installation scripts for all platforms
- Comprehensive documentation
- Environment setup templates

## Troubleshooting

### Connection Issues

**Symptoms**: "Connection failed" or authentication errors
- ✅ Verify API keys are correct (copy-paste from Amplitude)
- ✅ Confirm region setting (US vs EU)
- ✅ Ensure Project ID is numeric
- ✅ Check API key permissions include annotation access

### Chart ID Issues

**Symptoms**: "Invalid chart ID" or validation failures
- ✅ Chart IDs are alphanumeric (may include dashes/underscores)
- ✅ URLs contain `/chart/` in the path
- ✅ Chart IDs are at least 3 characters long
- ✅ Remove extra spaces or characters

### Environment Variable Issues

**Symptoms**: Manual entry form appears despite setting variables
- ✅ Restart terminal/application after setting variables
- ✅ Check variable names (case-sensitive):
  - `AMPLITUDE_API_KEY`
  - `AMPLITUDE_SECRET_KEY`
  - `AMPLITUDE_PROJECT_ID`
  - `AMPLITUDE_REGION`
- ✅ Verify variables are set: `echo $AMPLITUDE_API_KEY`
- ✅ Try using `.env` file method instead

### Python Issues

**Windows**: "python: command not found"
- Install Python from [python.org](https://python.org)
- Check "Add to PATH" during installation
- Use `run.bat` script for automatic setup

**macOS/Linux**: Version compatibility
- Use `python3` instead of `python`
- Install Python 3.9+ if needed
- Use `run.sh` script for automatic setup

### Application Issues

**GUI doesn't appear**:
- Check Python version: `python3 --version`
- Install missing dependencies: `pip install -r requirements.txt`
- Check logs: `amplitude_bulk_annotator.log`

**Slow performance**:
- Limit chart selections to reasonable numbers (< 100 at once)
- Check internet connection stability
- Verify Amplitude service status

**Unexpected errors**:
- Check the log file `amplitude_bulk_annotator.log` for detailed error information
- Look for specific error messages and stack traces
- Common issues include network connectivity, API rate limits, and invalid credentials

### Log File Analysis

The application creates a detailed log file `amplitude_bulk_annotator.log` in the same directory. This file contains:

- **Connection attempts**: API connection tests and results
- **Validation results**: Chart ID validation and API responses
- **Error details**: Full error messages and stack traces
- **Performance metrics**: Request timing and success rates

**Reading the log file**:
```bash
# View recent log entries
tail -50 amplitude_bulk_annotator.log

# Search for specific errors
grep -i "error" amplitude_bulk_annotator.log

# View connection attempts
grep -i "connection" amplitude_bulk_annotator.log
```

## Technical Details

### Architecture
- **GUI Framework**: PySide6 (Qt for Python)
- **API Client**: Custom implementation with retry logic
- **Threading**: Non-blocking UI with worker threads
- **Configuration**: Environment-first with file fallback
- **Validation**: Real-time input validation with visual feedback
- **Error Handling**: Comprehensive error reporting with user-friendly explanations
- **Logging**: Detailed logging to file and console for debugging

### API Integration
- **Endpoint**: Amplitude Chart Annotations API
- **Authentication**: HTTP Basic Authentication
- **Rate Limiting**: Built-in retry logic with exponential backoff
- **Error Handling**: Comprehensive error reporting and recovery
- **Status Codes**: Detailed HTTP status code explanations for users

### Error Handling Features
- **Smart Error Messages**: Automatic translation of API errors to user-friendly explanations
- **Status Indicators**: Visual feedback with color-coded status bars across all tabs
- **Progress Tracking**: Real-time progress updates during bulk operations
- **Graceful Degradation**: Partial success handling for bulk operations
- **Logging**: Comprehensive logging to `amplitude_bulk_annotator.log` for troubleshooting

### Supported Platforms
- **Windows** 10/11
- **macOS** 10.14+
- **Linux** distributions with Python 3.9+

### File Structure
```
amplitude-bulk-annotation-maker/
├── amplitude_bulk_annotator.py  # Main application
├── amplitude_api.py             # API client
├── config_manager.py           # Configuration handling
├── constants.py                # Application constants
├── requirements.txt            # Python dependencies
├── run.bat                     # Windows launcher
├── run.sh                      # macOS/Linux launcher
├── package_for_distribution.py # Distribution packager
├── utils/
│   ├── __init__.py             # Utility module init
│   └── validators.py           # Input validation utilities
├── README.md                   # This file
└── SETUP_ENVIRONMENT.md        # Environment setup guide
```

### Contributing

This application is designed for enterprise use with a focus on:
- Security best practices
- User experience optimization
- Error handling and recovery
- Cross-platform compatibility

For technical questions or feature requests, refer to the application logs and error messages for detailed debugging information. 