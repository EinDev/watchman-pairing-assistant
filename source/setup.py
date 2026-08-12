import os
import sys
from cx_Freeze import setup, Executable

gitRelease=os.environ['RELEASEVERSION']

base = 'gui'

#linux zsync update data
if sys.platform == "linux":
	gitRepo=os.environ['GITHUB_REPOSITORY_CLEAN']
	zsyncUpdateType="gh-releases-zsync|"
	zsyncFileName="|watchman-pairing-assistant-*.AppImage"
	zsyncUpdateValue= zsyncUpdateType + gitRepo + zsyncFileName

else:
	zsyncUpdateValue="na"

# Dependencies are automatically detected, but it might need
# fine tuning.
build_options = {
    'packages': [],
    'zip_exclude_packages': [],
    'excludes': [],
    'include_files': [
    ],
}


directory_table = [
    ("ProgramMenuFolder", "TARGETDIR", "."),
    ("MyProgramMenu", "ProgramMenuFolder", "MYPROG~1|My Program"),
]

msi_data = {
    "Directory": directory_table,
    "ProgId": [
        ("Prog.Id", "gitRelease", None, "GUI for pairing SteamVR Tracking devices", "IconId", None),
    ],
    "Icon": [
        ("IconId", "../resources/icon.ico"),
    ],
    "Shortcut": [
        ("DesktopShortcut", "DesktopFolder", "watchman-pairing-assistant",
         "TARGETDIR", "[TARGETDIR]main.exe",
         None, None, None, None, None, None, "TARGETDIR"),
        ("StartMenuShortcut", "MyProgramMenu", "watchman-pairing-assistant",
         "TARGETDIR", "[TARGETDIR]main.exe",
         None, None, None, None, None, None, "TARGETDIR"),
    ],
}

bdist_msi_options = {
    "add_to_path": True,
    "data": msi_data,
    "upgrade_code": "{78047038-4615-43f6-b538-eab094968716}",
    #"output_name": "watchman-pairing-assistant-installer",
    "product_name": "watchman-pairing-assistant",
    "product_version": gitRelease,
}
bdist_appimage_options = {
    "target_name": "watchman-pairing-assistant",
    "updateinformation": zsyncUpdateValue
}

# Pick the right icon per platform
if sys.platform == "win32":
    icon = '../resources/icon.ico'
else:
    icon = '../resources/icon.png'

executables = [
    Executable(
        'main.py',
        base=base,
        icon=icon,
    ),
]

setup(name='watchman-pairing-assistant',
      version = gitRelease,
      description = "GUI for pairing SteamVR Tracking devices",
      license = "MIT License",
      options = {
      'build_exe': build_options,
      'bdist_msi': bdist_msi_options,
      'bdist_appimage': bdist_appimage_options,
      },
      executables = executables)
