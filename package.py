import PyInstaller.__main__
import os
import sys
from pathlib import Path

def create_exe():
    # Get the current directory
    current_dir = Path.cwd()
    
    # Define the output directory for the executable
    dist_dir = current_dir / "dist"
    
    # Create version info file
    version_info = '''
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u''),
         StringStruct(u'FileDescription', u'IDF File Processor'),
         StringStruct(u'FileVersion', u'1.0.0'),
         StringStruct(u'InternalName', u'idf_processor'),
         StringStruct(u'LegalCopyright', u''),
         StringStruct(u'OriginalFilename', u'IDF-Processor.exe'),
         StringStruct(u'ProductName', u'IDF File Processor'),
         StringStruct(u'ProductVersion', u'1.0.0')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''
    
    version_file = current_dir / "version_info.txt"
    with open(version_file, "w") as f:
        f.write(version_info)

    # PyInstaller arguments
    args = [
        'gui.py',  # Main script
        '--name=IDF-Processor',
        '--onefile',  # Create single executable
        '--noconsole',  # Don't show console window
        '--clean',  # Clean PyInstaller cache
        # Add required data files
        '--add-data=settings.json;.' if os.path.exists('settings.json') else None,
        # Add version info and application configuration
        f'--version-file={version_file}',
        '--uac-admin',  # Request admin privileges for long path support
        # Hidden imports for dependencies
        '--hidden-import=customtkinter',
        '--hidden-import=eppy',
        '--hidden-import=reportlab',
        '--collect-all=customtkinter',  # Ensure all customtkinter resources are included
        # Optimization and stability options
        '--noupx',  # Disable UPX compression for better stability
        '--noconfirm',  # Replace existing build without asking
    ]
    
    # Filter out None values
    args = [arg for arg in args if arg is not None]
    
    try:
        print("Starting build process...")
        PyInstaller.__main__.run(args)
        print("\nBuild completed successfully!")
        print(f"\nExecutable created at: {dist_dir / 'IDF-Processor.exe'}")
        
        # Cleanup version info file
        version_file.unlink()
        
    except Exception as e:
        print(f"Error during build process: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    create_exe()