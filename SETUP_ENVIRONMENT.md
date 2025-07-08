# Environment Configuration Guide

This guide explains how to securely configure the Amplitude Bulk Annotation Maker using environment variables - the recommended approach for handling sensitive credentials.

## Table of Contents

- [Why Environment Variables?](#why-environment-variables)
- [Required Configuration](#required-configuration)
- [Setup Methods](#setup-methods)
- [Verification](#verification)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)

## Why Environment Variables?

Environment variables provide several security and usability advantages:

- **🔐 Security**: Credentials never stored in files or version control
- **🔄 Flexibility**: Same application works across different environments
- **👥 Team-friendly**: Each developer uses their own credentials
- **💾 No persistence**: Sensitive data doesn't remain on disk
- **🎯 Separation**: Configuration separated from application code

## Required Configuration

The application requires **Python 3.9+** and these environment variables for Amplitude API access:

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `AMPLITUDE_API_KEY` | Your Amplitude API key | `abc123def456` | ✅ Yes |
| `AMPLITUDE_SECRET_KEY` | Your Amplitude secret key | `xyz789uvw012` | ✅ Yes |
| `AMPLITUDE_PROJECT_ID` | Your Amplitude project ID | `123456` | ✅ Yes |
| `AMPLITUDE_REGION` | Your Amplitude region | `US` or `EU` | ❌ No (defaults to US) |

### How to Obtain These Values

#### 1. API Keys
1. Log into your Amplitude account
2. Navigate to **Settings** → **Projects**
3. Select your project
4. Go to **General** → **API Keys**
5. Copy your **API Key** and **Secret Key**

#### 2. Project ID
1. In Amplitude, go to **Settings** → **Projects**
2. Your Project ID is the numeric identifier displayed

#### 3. Region
- **US**: Default for most users (app.amplitude.com)
- **EU**: For European users (analytics.eu.amplitude.com)

## Setup Methods

Choose the method that best fits your workflow:

### Method 1: `.env` File (Recommended)

**Best for**: Individual developers, local development, simplified setup

#### Using the Application Menu

1. **Launch the application**
   ```bash
   python3 amplitude_bulk_annotator.py
   ```

2. **Create template file**
   - Go to **File** → **Create .env Template File**
   - This creates a `.env` file with placeholder values

3. **Edit with your credentials**
   - Use **File** → **Edit .env File** to open in your default editor
   - Or manually edit with any text editor:

   ```env
   # .env file - no quotes needed around values
   AMPLITUDE_API_KEY=your_actual_api_key_here
   AMPLITUDE_SECRET_KEY=your_actual_secret_key_here
   AMPLITUDE_PROJECT_ID=123456
   AMPLITUDE_REGION=US
   ```

4. **Restart the application**
   - Close and relaunch the application
   - Environment variables are automatically loaded

#### Manual Creation

Create a `.env` file in the project root directory:

```bash
# Create the file
touch .env

# Edit with your preferred editor
nano .env
# or
vim .env
# or
code .env
```

**Content**:
```env
AMPLITUDE_API_KEY=your_actual_api_key
AMPLITUDE_SECRET_KEY=your_actual_secret_key
AMPLITUDE_PROJECT_ID=123456
AMPLITUDE_REGION=US
```

**Important**: Never commit `.env` files to version control!

### Method 2: System Environment Variables

**Best for**: Production environments, CI/CD, permanent local setup

#### macOS/Linux

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, `~/.profile`):

```bash
# Amplitude configuration
export AMPLITUDE_API_KEY="your_api_key_here"
export AMPLITUDE_SECRET_KEY="your_secret_key_here"
export AMPLITUDE_PROJECT_ID="123456"
export AMPLITUDE_REGION="US"
```

**Apply changes**:
```bash
# Reload your shell configuration
source ~/.bashrc  # or ~/.zshrc

# Verify variables are set
echo $AMPLITUDE_API_KEY
```

#### Windows

**Option A: Command Prompt (Temporary)**
```cmd
set AMPLITUDE_API_KEY=your_api_key_here
set AMPLITUDE_SECRET_KEY=your_secret_key_here
set AMPLITUDE_PROJECT_ID=123456
set AMPLITUDE_REGION=US
```

**Option B: PowerShell (Temporary)**
```powershell
$env:AMPLITUDE_API_KEY="your_api_key_here"
$env:AMPLITUDE_SECRET_KEY="your_secret_key_here"
$env:AMPLITUDE_PROJECT_ID="123456"
$env:AMPLITUDE_REGION="US"
```

**Option C: System Environment Variables (Permanent)**
1. Open **System Properties** → **Advanced** → **Environment Variables**
2. Add new **User variables**:
   - `AMPLITUDE_API_KEY` = `your_api_key_here`
   - `AMPLITUDE_SECRET_KEY` = `your_secret_key_here`
   - `AMPLITUDE_PROJECT_ID` = `123456`
   - `AMPLITUDE_REGION` = `US`
3. Restart your terminal/application

### Method 3: Temporary Session Variables

**Best for**: Testing, one-time use, demonstration

```bash
# Set variables for current session only
export AMPLITUDE_API_KEY="your_api_key_here"
export AMPLITUDE_SECRET_KEY="your_secret_key_here"
export AMPLITUDE_PROJECT_ID="123456"
export AMPLITUDE_REGION="US"

# Run the application in same session
python3 amplitude_bulk_annotator.py
```

## Verification

### Application Interface

When you launch the application, you'll see different interfaces based on your configuration:

#### ✅ Environment Variables Detected
- **Status**: Green message: "🔒 Configuration loaded from .env file" or "🔒 Configuration loaded from system environment variables"
- **Fields**: Credential fields show `••••••••` and are read-only
- **Behavior**: Automatic connection test on startup
- **Menu**: .env file management options available if using `.env` method

#### ❌ No Environment Variables
- **Status**: Blue message: "💡 Enter your Amplitude credentials below"
- **Fields**: Empty, editable credential input fields
- **Behavior**: Manual entry required, manual connection test

#### ⚠️ Invalid Configuration
- **Status**: Yellow warning about existing but invalid `.env` file
- **Options**: Edit existing `.env` file or enter credentials manually

### Command Line Verification

**Check if variables are set**:
```bash
# macOS/Linux
echo $AMPLITUDE_API_KEY
echo $AMPLITUDE_PROJECT_ID

# Windows Command Prompt
echo %AMPLITUDE_API_KEY%
echo %AMPLITUDE_PROJECT_ID%

# Windows PowerShell
echo $env:AMPLITUDE_API_KEY
echo $env:AMPLITUDE_PROJECT_ID
```

**Expected output**: Your actual values (not empty)

## Security Best Practices

### Do ✅

- **Use environment variables** for sensitive credentials
- **Use unique API keys** for each team member
- **Rotate API keys** periodically
- **Limit API key permissions** to necessary scopes only
- **Use `.env` files** for local development
- **Keep `.env` files** out of version control
- **Set appropriate file permissions** (600) on `.env` files

### Don't ❌

- **Never commit** `.env` files to Git/SVN
- **Never share** API keys in plain text
- **Never hardcode** credentials in source code
- **Never include** credentials in screenshots or logs
- **Never use production keys** for development/testing

### File Permissions

Secure your `.env` file:
```bash
# macOS/Linux: Make file readable only by owner
chmod 600 .env

# Verify permissions
ls -la .env
# Should show: -rw------- (600)
```

### `.gitignore` Configuration

Ensure your `.gitignore` file includes:
```gitignore
# Environment variables
.env
.env.local
.env.production
.env.*.local

# Configuration files
amplitude_config.json
amplitude_preferences.json
```

## Troubleshooting

### Environment Variables Not Detected

**Symptoms**: Application shows manual entry form despite setting variables

**Solutions**:
1. **Check variable names** (case-sensitive):
   ```bash
   # Correct
   AMPLITUDE_API_KEY=abc123
   
   # Incorrect
   amplitude_api_key=abc123
   Amplitude_API_Key=abc123
   ```

2. **Verify variables are set**:
   ```bash
   # Should return your values, not blank
   echo $AMPLITUDE_API_KEY
   echo $AMPLITUDE_SECRET_KEY
   echo $AMPLITUDE_PROJECT_ID
   ```

3. **Restart terminal/application** after setting variables

4. **Check shell profile** is being loaded:
   ```bash
   # Reload manually
   source ~/.bashrc  # or ~/.zshrc
   ```

### `.env` File Not Working

**Symptoms**: Variables from `.env` file not loaded

**Solutions**:
1. **Check file location**: Must be in same directory as application
2. **Check file name**: Must be exactly `.env` (with the dot)
3. **Check file format**:
   ```env
   # Correct format
   AMPLITUDE_API_KEY=abc123
   AMPLITUDE_SECRET_KEY=xyz789
   
   # Incorrect - no quotes, spaces, or export
   export AMPLITUDE_API_KEY="abc123"
   AMPLITUDE_API_KEY = abc123
   ```

4. **Check file permissions**: File must be readable
   ```bash
   ls -la .env
   # If not readable:
   chmod 600 .env
   ```

### Connection Still Fails

**After environment variables are correctly set**:

1. **Verify credentials in Amplitude**:
   - API keys are active and not expired
   - Project ID is correct
   - Account has annotation permissions

2. **Check region setting**:
   - US region: app.amplitude.com users
   - EU region: analytics.eu.amplitude.com users

3. **Test with manual entry**:
   - Temporarily enter credentials manually
   - Use "Test Connection" to verify

### Python/Application Issues

**Application doesn't start**:
```bash
# Check Python version
python3 --version

# Install missing dependencies
pip install -r requirements.txt

# Check for errors
python3 amplitude_bulk_annotator.py
```

**Dependencies missing**:
```bash
# Install python-dotenv for .env support
pip install python-dotenv

# Or install all requirements
pip install -r requirements.txt
```

### Getting Help

If you continue to experience issues:

1. **Check application logs**: `amplitude_bulk_annotator.log`
2. **Verify Amplitude service status**: Check Amplitude's status page
3. **Test with minimal configuration**: Use only required variables
4. **Contact support**: Provide sanitized error messages (never include API keys)

## Advanced Configuration

### Multiple Projects

For users working with multiple Amplitude projects:

**Option 1: Switch `.env` files**
```bash
# Rename current .env
mv .env .env.project1

# Create new .env for different project
cp .env.project1 .env.project2
# Edit .env.project2 with different PROJECT_ID

# Switch between projects
cp .env.project1 .env  # Use project 1
cp .env.project2 .env  # Use project 2
```

**Option 2: Use shell functions**
```bash
# Add to ~/.bashrc or ~/.zshrc
amp_project1() {
    export AMPLITUDE_PROJECT_ID="123456"
    echo "Switched to Project 1"
}

amp_project2() {
    export AMPLITUDE_PROJECT_ID="789012"
    echo "Switched to Project 2"
}
```

### CI/CD Integration

For automated environments:
```yaml
# Example GitHub Actions
env:
  AMPLITUDE_API_KEY: ${{ secrets.AMPLITUDE_API_KEY }}
  AMPLITUDE_SECRET_KEY: ${{ secrets.AMPLITUDE_SECRET_KEY }}
  AMPLITUDE_PROJECT_ID: ${{ secrets.AMPLITUDE_PROJECT_ID }}
  AMPLITUDE_REGION: "US"
```

This configuration ensures your Amplitude Bulk Annotation Maker operates securely and efficiently across different environments while maintaining the highest security standards. 