<style>body {text-align: justify}</style>

# Settings

## Settings Window

To open the **Settings Window** use button with gear icon on top left of the **Main Window**. All changes saved automatically.

## General

![alt text](imgs/settings_window_general.png)

### Library Folder

**Library Folder** - a directory on hard drive, where all downloaded builds are stored. For detailed information check [Library Folder](library_folder.md) page.

### Launch When System Starts

!!! info
    This is only working on Windows

:   Determines if **Blender Launcher** will run when system starts.

### Show Tray Icon

:   Toggles visibility of tray icon. If option is disabled, **Blender Launcher** will shut down after closing its **Main Window**.

### Launch Minimized To Tray

:   Determines if **Main Window** will pop up when user execute **Blender Launcher** or only tray icon will be shown.

### Worker Thread Count

:   Set the maximal number of **CPU Thread Blender** Launcher can use

## Appearance

![alt text](imgs/settings_window_appearance.png)

### Window

#### Use System Title Bar

#### Enable High DPI Scaling

:   Determines if **Blender Launcher** user interface will automatically scale based on the monitor's pixel density. To apply changes application should be restarted.


### Notifications

#### New Available Build

:   Show OS notifications when new new builds of Blender are available in Downloads tab.

#### Finished Downloading

:   Show OS notifications when build finished downloading and added to Library tab.

#### Errors

:   Show OS nitification when an error occur on the Blender Launcher

### Tabs

#### Default Tab

:   Set what tab of will be opened when **Blender Launcher** starts.

#### Sync Library & Downloads

:   Determines if pages of Library and Downloads tabs will be automatically matched between each over.

#### Default Library Page

:   Sets what page of Library tab will be opened when **Blender Launcher** starts.

#### Default Downloads Page

:   Sets what page of Downloads tab will be opened when **Blender Launcher** starts.

## Connection

![alt text](imgs/settings_window_connection.png)


### Proxy

:   TODO

#### Use Custom TLS Certificates

:   TODO

#### Type

:   TODO

#### IP

:   TODO

#### Proxy User

:   TODO

#### Password

:   TODO

## Blender Builds

![alt text](imgs/settings_window_blenderbuilds.png)

### Checking For Builds

#### Check Automatically

:   Automatically check if a new build have been release and send a notification it there is a new one available

#### On Startup

:   If Blender launcher will check for new build when lunch

#### Min Stable Build to Scrape

:   set the minimum blender version to scape, this reduce the request amont and sppeed up the build gatering time

#### Scrape Stable Builds

:   If the Blender Luancher will gather the Stable build, disabeling this will spped up the gatering of the daly build

#### Scrape Automated Builds

:   If the Blender Laucher will gather the automated daly build (daly, experimental, patch) 

### Downloading & Saving build

Actions that will be performed on newly added build to Library tab right after downloading is finished.

#### Mark As Favorite

:   Mark every newly added build to Library tab as favorite depending on branch type.

#### Install Template

:   Installs template on newly added build to Library tab.

### Launching Builds

#### Quick Launch Global SHC

:   Launches build added to quick launch via user defined key sequence.

#### Hide Console On Startup

!!! info
    This is only working on Windows


:   Launch Blender via `blender-launcher.exe` to hide console on startup. Works on Blender version 3.0 and higher.

    !!! warning "Known Issues"

        When using this feature number of running instances will not be shown.

#### Startup Arguments

:   Adds specific instructions as if Blender was launching from the command line (after the blender executable i.e. `blender [args …]`).

:   For example `-W` (force opening Blender in fullscreen mode) argument internally will produce following command:

    ```
    %path to blender executable% -W
    ```

:   List of commands can be found on Blender manual [Command Line Arguments](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html) page.

#### Bash Arguments

!!! info
    This is only working on Windows

:   Adds specific instructions as if Blender was launching from the command line (before the blender executable i.e. `[args …] blender`).

:   For example `env __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia` (force Blender to use dedicated graphics card) arguments internally will produce following command:

    ```
    env __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia nohup %path to blender executable% %startup arguments%
    ```
