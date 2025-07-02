#!/usr/bin/env python3
"""
Package the Amplitude Bulk Annotation Maker for distribution.

This module handles creating distribution packages (ZIP files and executables)
for easy sharing of the application.
"""
import os
import shutil
import zipfile
import logging
from datetime import datetime
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import constants if available, otherwise define defaults
try:
    from constants import DISTRIBUTION_FILES, DISTRIBUTION_DIR, DISTRIBUTION_INSTRUCTIONS_FILE
except ImportError:
    DISTRIBUTION_FILES = [
        'amplitude_bulk_annotator.py',
        'amplitude_api.py',
        'requirements.txt',
        'README.md',
        'run.bat',
        'run.sh',
        '.gitignore',
        'SETUP_ENVIRONMENT.md',
        'constants.py'
    ]
    DISTRIBUTION_DIR = 'dist'
    DISTRIBUTION_INSTRUCTIONS_FILE = 'DISTRIBUTION_INSTRUCTIONS.txt'


def create_distribution_package() -> str:
    """
    Create a zip file with all necessary files for distribution.
    
    Returns:
        Path to the created ZIP file
        
    Raises:
        IOError: If file operations fail
    """
    # Create distribution directory
    if os.path.exists(DISTRIBUTION_DIR):
        shutil.rmtree(DISTRIBUTION_DIR)
    os.makedirs(DISTRIBUTION_DIR)
    
    # Create timestamp for filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_filename = f'amplitude_bulk_annotator_{timestamp}.zip'
    zip_path = os.path.join(DISTRIBUTION_DIR, zip_filename)
    
    # Track missing files
    missing_files: List[str] = []
    
    # Create zip file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in DISTRIBUTION_FILES:
            if os.path.exists(file):
                zipf.write(file, file)
                logger.info(f"Added: {file}")
            else:
                missing_files.append(file)
                logger.warning(f"File not found: {file}")
    
    if missing_files:
        logger.warning(f"Missing {len(missing_files)} files: {', '.join(missing_files)}")
    
    logger.info(f"Distribution package created: {zip_path}")
    logger.info(f"Size: {os.path.getsize(zip_path) / 1024:.1f} KB")
    
    # Create instructions file
    instructions_path = os.path.join(DISTRIBUTION_DIR, DISTRIBUTION_INSTRUCTIONS_FILE)
    with open(instructions_path, 'w') as f:
        f.write("""Amplitude Bulk Annotation Maker - Distribution Instructions
==========================================================

To share this application:

1. Send the ZIP file to your colleagues
2. They should extract all files to a folder
3. They need Python 3.13+ installed
4. Run the application:
   - Windows: Double-click run.bat
   - Mac/Linux: Run ./run.sh
   - Or: python amplitude_bulk_annotator.py

Each user will need to provide their own Amplitude API keys.

For detailed instructions, see README.md after extraction.
""")
    
    logger.info(f"Instructions file created: {instructions_path}")
    
    return zip_path


def create_pyinstaller_package() -> bool:
    """
    Create a standalone executable using PyInstaller (optional).
    
    Returns:
        True if successful, False otherwise
    """
    try:
        import PyInstaller.__main__
        
        logger.info("Creating standalone executable...")
        
        PyInstaller.__main__.run([
            'amplitude_bulk_annotator.py',
            '--onefile',
            '--windowed',
            '--name=AmplitudeBulkAnnotator',
            f'--distpath={DISTRIBUTION_DIR}/standalone',
            '--add-data=README.md:.',
            '--clean'
        ])
        
        logger.info(f"Standalone executable created in {DISTRIBUTION_DIR}/standalone/")
        return True
        
    except ImportError:
        logger.warning("PyInstaller not installed")
        print("\nPyInstaller not installed. To create standalone executable:")
        print("1. pip install pyinstaller")
        print("2. Run this script again")
        return False
    except Exception as e:
        logger.error(f"Error creating executable: {e}")
        return False


def main() -> None:
    """Main entry point for the distribution packager."""
    print("Amplitude Bulk Annotation Maker - Distribution Packager")
    print("=" * 50)
    
    try:
        # Create ZIP distribution
        zip_path = create_distribution_package()
        
        # Optionally create standalone executable
        print("\nWould you like to create a standalone executable? (y/n)")
        response = input("> ").lower().strip()
        
        if response == 'y':
            if create_pyinstaller_package():
                print("\n✅ Standalone executable created successfully!")
            else:
                print("\n❌ Failed to create standalone executable")
        
        print("\nPackaging complete!")
        print("\nTo distribute:")
        print(f"1. Share the ZIP file: {zip_path}")
        print("2. Or use the standalone executable (if created)")
        print("\nRemember: Each user needs their own Amplitude API keys!")
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        logger.exception("Unexpected error during packaging")
        print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    main() 