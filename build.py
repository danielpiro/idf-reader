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
        '--add-data=data;data',  # Include entire data folder
        '--add-data=parsers;parsers',  # Include parsers module
        '--add-data=generators;generators',  # Include generators module
        '--add-data=utils;utils',  # Include utils module
        # Add Windows specific options
        '--uac-admin',  # Request admin privileges for long path support
    ]

    # Include main dependencies
    hidden_imports = [
        'customtkinter',
        'tkinter',
        'eppy',
        'reportlab',
        'parsers',
        'generators',
        'utils',
        'processing_manager',
        'idf_code_cleaner',
    ]
    
    for imp in hidden_imports:
        args.append(f'--hidden-import={imp}')

    # Run PyInstaller
    PyInstaller.__main__.run(args)

if __name__ == "__main__":
    build_exe()
    print("Build completed! Executable can be found in the dist directory.")