import PyInstaller.__main__
import os
import sys
from pathlib import Path

def create_exe():
    current_dir = Path.cwd()

    dist_dir = current_dir / "dist"

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

    args = [
        'gui.py',
        '--name=IDF-Processor',
        '--onefile',
        '--noconsole',
        '--clean',
        '--add-data=settings.json;.' if os.path.exists('settings.json') else None,
        f'--version-file={version_file}',
        '--uac-admin',
        '--hidden-import=customtkinter',
        '--hidden-import=eppy',
        '--hidden-import=reportlab',
        '--collect-all=customtkinter',
        '--noupx',
        '--noconfirm',
    ]

    args = [arg for arg in args if arg is not None]

    try:

        PyInstaller.__main__.run(args)

        version_file.unlink()

    except Exception as e:

        sys.exit(1)

if __name__ == "__main__":
    create_exe()
