# Environment Variables Setup Guide

For security best practices, this application uses environment variables to store sensitive API credentials instead of plain text files.

## Required Environment Variables

Set these environment variables with your Amplitude credentials:

### 1. API Keys (Required)
```bash
export AMPLITUDE_API_KEY="your_api_key_here"
export AMPLITUDE_SECRET_KEY="your_secret_key_here"
```

**How to get these:**
1. Log into your Amplitude account
2. Go to **Settings** → **Projects**
3. Select your project
4. Navigate to **General** → **API Keys**
5. Copy your **API Key** and **Secret Key**

### 2. Project ID (Required)
```bash
export AMPLITUDE_PROJECT_ID="123456"
```

**How to find this:**
1. In Amplitude, go to **Settings** → **Projects**
2. Your Project ID is the numeric identifier shown

### 3. Region (Optional)
```bash
export AMPLITUDE_REGION="US"  # or "EU"
```

## Setup Methods

### Option 1: Using .env file (Recommended)

1. Create a `.env` file in the project root:
```bash
# .env file (no quotes needed)
AMPLITUDE_API_KEY=your_actual_api_key
AMPLITUDE_SECRET_KEY=your_actual_secret_key
AMPLITUDE_PROJECT_ID=123456
AMPLITUDE_REGION=US
```

2. **That's it!** The application automatically loads `.env` files when it starts.
   - No need to manually export variables
   - Just run the application and it will use your `.env` file

### Option 2: System Environment Variables

Add to your shell profile (e.g., `~/.bashrc`, `~/.zshrc`):
```bash
export AMPLITUDE_API_KEY="your_api_key_here"
export AMPLITUDE_SECRET_KEY="your_secret_key_here"
export AMPLITUDE_PROJECT_ID="123456"
export AMPLITUDE_REGION="US"
```

Then reload your shell:
```bash
source ~/.bashrc  # or ~/.zshrc
```

### Option 3: Temporary Session Variables

For a single session:
```bash
export AMPLITUDE_API_KEY="your_api_key_here"
export AMPLITUDE_SECRET_KEY="your_secret_key_here"
export AMPLITUDE_PROJECT_ID="123456"
export AMPLITUDE_REGION="US"

# Then run the application
python amplitude_bulk_annotator.py
```

## Verification

Run the application and check the Configuration tab:
- ✅ If environment variables are detected, you'll see masked credentials and a green "loaded from environment variables" message
- ⚠️ If not detected, you'll see a warning and can enter them manually (not recommended)

## Security Notes

- **Never commit `.env` files** to version control (they're in `.gitignore`)
- **Never share your API keys** in plain text
- **Use environment variables** for production environments
- The application will prioritize environment variables over manual input

## Troubleshooting

**Q: Environment variables not detected?**
- Verify they're set: `echo $AMPLITUDE_API_KEY`
- Restart your terminal/application
- Check for typos in variable names

**Q: Still seeing manual input fields?**
- Variables must be set before launching the application
- Variable names are case-sensitive
- Both API_KEY and SECRET_KEY must be set for auto-detection

**Q: Application won't connect?**
- Verify credentials in Amplitude dashboard
- Check your region setting (US vs EU)
- Test connection button will show specific error messages 