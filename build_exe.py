"""
Build Script for SignalGen Desktop Application
Build the application into a standalone .exe file using PyInstaller
"""

import os
import subprocess
import sys
import shutil
from pathlib import Path

def clean_build_folders():
    """Remove old build artifacts"""
    folders_to_clean = ['build', 'dist']
    for folder in folders_to_clean:
        if os.path.exists(folder):
            print(f"Cleaning {folder}/ directory...")
            shutil.rmtree(folder)
            print(f"✓ {folder}/ removed")

def build_exe():
    """Build the executable using PyInstaller"""
    print("\n" + "="*60)
    print("Building SignalGen Desktop Application")
    print("="*60 + "\n")
    
    # Clean previous builds
    clean_build_folders()
    
    # Run PyInstaller
    print("Running PyInstaller...")
    spec_file = "signalgen.spec"
    
    if not os.path.exists(spec_file):
        print(f"ERROR: {spec_file} not found!")
        sys.exit(1)
    
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", spec_file]
    
    try:
        result = subprocess.run(cmd, check=True)
        
        print("\n" + "="*60)
        print("BUILD SUCCESSFUL!")
        print("="*60)
        print(f"\nExecutable location: dist\\SignalGen\\SignalGen.exe")
        print("\nYou can now run the application by executing:")
        print("  dist\\SignalGen\\SignalGen.exe")
        print("\nTo distribute the app, copy the entire 'dist\\SignalGen' folder")
        print("="*60 + "\n")
        
    except subprocess.CalledProcessError as e:
        print("\n" + "="*60)
        print("BUILD FAILED!")
        print("="*60)
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_exe()
