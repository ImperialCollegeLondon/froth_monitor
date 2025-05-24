"""Build script for creating a standalone executable of the Froth Monitor application."""

import os
import sys
import subprocess
import platform

def check_pyinstaller():
    """Check if PyInstaller is installed, install if not."""
    try:
        import PyInstaller
        print("PyInstaller is already installed.")
        return True
    except ImportError:
        print("PyInstaller is not installed. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("PyInstaller installed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to install PyInstaller: {e}")
            return False

def build_executable():
    """Build the executable using PyInstaller."""
    if not check_pyinstaller():
        return False
    
    print("Building executable with PyInstaller...")
    try:
        # Use the spec file for building
        subprocess.check_call([sys.executable, "-m", "PyInstaller", "froth_monitor.spec"])
        
        # Get the path to the executable
        dist_dir = os.path.join(os.getcwd(), "dist")
        exe_name = "froth_monitor.exe" if platform.system() == "Windows" else "froth_monitor"
        exe_path = os.path.join(dist_dir, exe_name)
        
        if os.path.exists(exe_path):
            print(f"\nBuild successful! Executable created at: {exe_path}")
            return True
        else:
            print("\nBuild completed but executable not found.")
            return False
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed: {e}")
        return False

def main():
    """Main function to build the executable."""
    print("=== Froth Monitor Executable Builder ===")
    success = build_executable()
    
    if success:
        print("\nYou can now distribute the executable from the 'dist' folder.")
    else:
        print("\nBuild process failed. Please check the error messages above.")

if __name__ == "__main__":
    main()