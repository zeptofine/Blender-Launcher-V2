<style>body {text-align: justify}</style>

# Development

## Requirements

- Linux or Windows x64
- Python 3.9
- pdm

!!! warning

    To use different Python version, run `pdm use` to select the correct python interpreter

## Using Pdm

!!! info "Note"

    All actions should be performed under repository root folder i.e. `/Blender-Launcher-V2`!

### Preparing virtual environment

1. Install pdm package

        pip install pdm

1. Install dependencies

        pdm install

1. Enter the virtual environment

        pdm venv activate

### Building Blender Launcher executable

!!! warning

    Executables made in Pyinstaller must be built inside the target platform! You cannot build for a different platform other than your own.

=== "Windows"

    1. Run batch file

        ```
        .\build_win.bat
        ```

    1. Look for bundled app under `Blender-Launcher-V2\dist\release` folder

=== "Linux"

    1. Run shell script file

        ```
        sh build_linux.sh
        ```

    1. Look for bundled app under `Blender-Launcher-V2\dist\release` folder
