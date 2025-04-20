import PyInstaller.__main__

def build_exe():
    # PyInstaller command-line arguments
    args = [
        'gui.py',  # Your main script
        '--name=IDF-Processor',  # Name of the executable
        '--onefile',  # Create a single executable file
        '--noconsole',  # Don't show console window
        '--clean',  # Clean PyInstaller cache
        '--add-data=settings.json;.',  # Include settings file if it exists
        # Add Windows specific options
        '--win-private-assemblies',
        '--uac-admin',  # Request admin privileges for long path support
    ]

    # Include main dependencies
    hidden_imports = [
        'customtkinter',
        'tkinter',
        'eppy',
        'reportlab',
    ]
    
    for imp in hidden_imports:
        args.append(f'--hidden-import={imp}')

    # Run PyInstaller
    PyInstaller.__main__.run(args)

if __name__ == "__main__":
    build_exe()
    print("Build completed! Executable can be found in the dist directory.")