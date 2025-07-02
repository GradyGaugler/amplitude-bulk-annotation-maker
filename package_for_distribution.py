#!/usr/bin/env python3
"""
Package the Amplitude Bulk Annotation Maker for distribution
"""
import os
import shutil
import zipfile
from datetime import datetime


def create_distribution_package():
    """Create a zip file with all necessary files for distribution"""
    
    # Files to include in the distribution
    files_to_include = [
        'amplitude_bulk_annotator.py',
        'amplitude_api.py',
        'requirements.txt',
        'README.md',
        'run.bat',
        'run.sh',
        '.gitignore'
    ]
    
    # Create distribution directory
    dist_dir = 'dist'
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(dist_dir)
    
    # Create timestamp for filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_filename = f'amplitude_bulk_annotator_{timestamp}.zip'
    zip_path = os.path.join(dist_dir, zip_filename)
    
    # Create zip file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in files_to_include:
            if os.path.exists(file):
                zipf.write(file, file)
                print(f"Added: {file}")
            else:
                print(f"Warning: {file} not found, skipping...")
    
    print(f"\nDistribution package created: {zip_path}")
    print(f"Size: {os.path.getsize(zip_path) / 1024:.1f} KB")
    
    # Create instructions file
    instructions_path = os.path.join(dist_dir, 'DISTRIBUTION_INSTRUCTIONS.txt')
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
    
    print(f"\nInstructions file created: {instructions_path}")
    
    return zip_path


def create_pyinstaller_package():
    """Create a standalone executable using PyInstaller (optional)"""
    try:
        import PyInstaller.__main__
        
        print("\nCreating standalone executable...")
        
        PyInstaller.__main__.run([
            'amplitude_bulk_annotator.py',
            '--onefile',
            '--windowed',
            '--name=AmplitudeBulkAnnotator',
            '--distpath=dist/standalone',
            '--add-data=README.md:.',
            '--clean'
        ])
        
        print("\nStandalone executable created in dist/standalone/")
        
    except ImportError:
        print("\nPyInstaller not installed. To create standalone executable:")
        print("1. pip install pyinstaller")
        print("2. Run this script again")


if __name__ == "__main__":
    print("Amplitude Bulk Annotation Maker - Distribution Packager")
    print("=" * 50)
    
    # Create ZIP distribution
    zip_path = create_distribution_package()
    
    # Optionally create standalone executable
    print("\nWould you like to create a standalone executable? (y/n)")
    response = input("> ").lower().strip()
    
    if response == 'y':
        create_pyinstaller_package()
    
    print("\nPackaging complete!")
    print("\nTo distribute:")
    print(f"1. Share the ZIP file: {zip_path}")
    print("2. Or use the standalone executable (if created)")
    print("\nRemember: Each user needs their own Amplitude API keys!") 