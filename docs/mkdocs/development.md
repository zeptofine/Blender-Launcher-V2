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

2. Create the virtual environment

    ```bash
    python -m pip install virtualenv
    python -m virtualenv --clear --download .venv
    python -m ensurepip
    python -m pip install --upgrade pdm
    # Enter the virtual Environment
    pdm venv activate
    # ^ Execute the command this returns with!
    ```

2. Install dependencies

    === "Minimum set of packages for building executable"

        ```
        pip install -e .
        ```

    === "All set of packages including development tools"

        ```
        pdm install
        ```

## Running Blender Launcher

!!! info

    As of ([c90f33d](https://github.com/Victor-IX/Blender-Launcher-V2/commit/c90f33dfb710da509e50932bae3cbe5b588d8688)), cached Blender-Launcher-V2 files (such as resources_rc.py and global.qss) are no longer included in the source due to them artificially inflating git diffs. In order to generate them, run the `build_style.py` script located in the root project directory. running Blender Launcher without these being built will result in an error.

```bash
python source/main.py
```

## Building Blender Launcher executable

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
