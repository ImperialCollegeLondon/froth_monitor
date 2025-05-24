# Building Froth Monitor Executable

This document provides instructions for building a standalone executable of the
Froth Monitor application using PyInstaller.

## Prerequisites

- Python 3.12 or newer installed
- pip package manager

## Building the Executable

### Automatic Build (Recommended)

1. Run the build script:

   ```bash
   python build.py
   ```

2. The script will:
   - Check if PyInstaller is installed and install it if needed
   - Build the executable using the provided spec file
   - Place the executable in the `dist` folder

### Manual Build

If you prefer to build manually:

1. Install PyInstaller if not already installed:

   ```bash
   pip install pyinstaller
   ```

2. Run PyInstaller with the spec file:

   ```bash
   pyinstaller froth_monitor.spec
   ```

3. The executable will be created in the `dist` folder

## Distribution

After building, you can distribute the executable by:

1. Sharing the entire `dist/froth_monitor` folder (contains the executable and all dependencies)
2. Creating a zip archive of the `dist/froth_monitor` folder

## Troubleshooting

If you encounter issues during the build process:

1. Ensure all dependencies are installed:

   ```bash
   pip install -r requirements.txt
   ```

2. Check for any error messages in the build output

3. Try running PyInstaller with the `--debug=all` flag for more detailed
   output:

   ```bash
   pyinstaller --debug=all froth_monitor.spec
   ```

## Notes

- The executable is configured to run in windowed mode (no console)
- All necessary dependencies and data files should be included automatically
- If you modify the application, you may need to update the spec file accordingly
