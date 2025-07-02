# Amplitude Bulk Annotation Maker

A Python GUI application for applying annotations to multiple Amplitude charts at once. Built with Python 3.13 and PySide6.

## Features

- **Bulk Annotations**: Apply the same annotation to multiple charts at once
- **Chart ID & URL Input**: Enter chart IDs directly or paste full Amplitude URLs
- **URL Parsing**: Automatically extracts chart IDs from Amplitude URLs
- **Input Validation**: Validates chart IDs before processing
- **Automatic Tab Progression**: Seamlessly move through the workflow
- **Configuration Saving**: Save your API keys and project settings for future use
- **Modern GUI**: Clean, intuitive interface built with PySide6

## Installation

### Requirements
- Python 3.13 or later
- pip (Python package manager)

### Setup

1. **Download the application**
   - Download all files to a folder on your computer

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   
   **Windows:**
   ```bash
   run.bat
   ```
   
   **Mac/Linux:**
   ```bash
   ./run.sh
   ```

## How to Use

### 1. Configuration

**🔒 Recommended: Use Environment Variables** (see [SETUP_ENVIRONMENT.md](SETUP_ENVIRONMENT.md))
- Create a `.env` file with your credentials - the app loads it automatically
- Or set `AMPLITUDE_API_KEY`, `AMPLITUDE_SECRET_KEY`, `AMPLITUDE_PROJECT_ID` environment variables
- Application will automatically detect and use these securely

**Alternative: Manual Entry**
- Enter your Amplitude API Key and Secret Key
- Select your region (US or EU)  
- Enter your Project ID (found in Amplitude Settings > Projects)
- Test the connection

### 2. Select Charts
Enter chart IDs or URLs in the text area. You can:
- **Enter chart IDs directly**: `ez25o7zy`
- **Paste full URLs**: `https://app.amplitude.com/analytics/demo/chart/ez25o7zy`
- **Mix both formats**
- **Enter multiple charts** (one per line)

Examples:
```
ez25o7zy
abc123
https://app.amplitude.com/analytics/demo/chart/xyz789
def456, ghi789
```

Click "Parse and Validate" to process your input.

### 3. Create Annotation
- Select the affected date
- Enter annotation name (required)
- Add optional description
- Preview your annotation

### 4. Apply & Review
- Click "Apply Annotations" to process all charts
- View results in the Results tab
- Export results if needed

## Security & API Keys

### 🔒 Security Best Practices

This application follows security best practices by using **environment variables** for sensitive credentials instead of storing them in files.

**See [SETUP_ENVIRONMENT.md](SETUP_ENVIRONMENT.md) for detailed setup instructions.**

### Getting Your Amplitude Credentials

1. **API Keys**: Go to Amplitude Settings → Projects → API Keys
2. **Project ID**: Go to Amplitude Settings → Projects (numeric ID)
3. **Region**: Usually "US" unless you specifically use EU servers

**Important**: Never commit API keys to version control or share them in plain text!

## Getting Chart IDs

### From Chart URLs
Chart IDs are at the end of Amplitude chart URLs:
```
https://app.amplitude.com/analytics/yourproject/chart/ez25o7zy
                                                       ^^^^^^^^
                                                     Chart ID
```

### From Multiple Charts
1. Open each chart in Amplitude
2. Copy the URL or just the chart ID from the URL
3. Paste all IDs/URLs into the application (one per line)

## Distribution

To package for colleagues:
```bash
python package_for_distribution.py
```

This creates a zip file with all necessary files that can be shared with colleagues.

**Important**: Each user needs their own Amplitude API keys!

## Troubleshooting

### Connection Issues
- Verify your API keys are correct
- Check if your region (US/EU) is correct
- Ensure your Project ID is a number

### Chart ID Issues
- Make sure chart IDs are alphanumeric (may include dashes/underscores)
- Verify URLs contain `/chart/` in the path
- Check that chart IDs are at least 3 characters long

### Permission Issues
- Ensure your API keys have annotation permissions
- Verify you have access to the specified project

## Technical Details

- **API Documentation**: Uses Amplitude Chart Annotations API
- **GUI Framework**: PySide6 (Qt for Python)
- **Supported Platforms**: Windows, macOS, Linux
- **Python Version**: 3.13+ recommended

## Files

- `amplitude_bulk_annotator.py` - Main GUI application
- `amplitude_api.py` - Amplitude API client
- `requirements.txt` - Python dependencies
- `run.bat` / `run.sh` - Launch scripts
- `package_for_distribution.py` - Distribution packager
- `SETUP_ENVIRONMENT.md` - Environment variables setup guide 