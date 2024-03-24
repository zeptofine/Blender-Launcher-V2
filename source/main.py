from __future__ import annotations

import gettext
import logging
import os
import shutil
import sys
from argparse import ArgumentParser
from pathlib import Path

import modules._resources_rc
from modules import argument_parsing as ap
from modules._platform import _popen, get_cwd, get_launcher_name, get_platform, is_frozen

version = "2.0.24"

_ = gettext.gettext

# Setup logging config
_format = "[%(asctime)s:%(levelname)s] %(message)s"
logging.basicConfig(
    format=_format,
    handlers=[logging.FileHandler(get_cwd() / "Blender Launcher.log"), logging.StreamHandler(stream=sys.stdout)],
)
logger = logging.getLogger(__name__)


# Setup exception handling
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error(f"{get_platform()} - Blender Launcher {version}", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception


# List of available line arguments
cli_help = """
    Command line arguments sheet:

    -help                        * Show command line arguments sheet
    -update                      * Run updater instead of the main application
    -debug                       * Set logging level to DEBUG
    -set-library-folder "%path%" * Set library folder
    -offline                     * Disable scraper thread
    -instanced                   * Do not check if other BL instance is
                                   running, used for restarting app
    """


def add_help(parser: ArgumentParser):
    parser.add_argument(
        parser.prefix_chars + "h",
        parser.prefix_chars * 2 + "help",
        action="store_true",
        help="show this help message and exit",
    )


def main():
    parser = ArgumentParser(description=f"Blender Launcher V2 ({version})", add_help=False)
    add_help(parser)

    subparsers = parser.add_subparsers(dest="command")

    update_parser = subparsers.add_parser("update", help="Update the application to a new version.", add_help=False)
    add_help(update_parser)
    update_parser.add_argument("version", help="Version to update to.", nargs="?")

    parser.add_argument("-debug", help="Enable debug logging.", action="store_true")
    parser.add_argument("-set-library-folder", help="Set library folder", type=Path)
    parser.add_argument(
        "--offline",
        "-offline",
        help="Run the application offline. (Disables the scraper threads and update checks)",
        action="store_true",
    )
    parser.add_argument(
        "--instanced",
        "-instanced",
        help="Run the application in an already running instance.",
        action="store_true",
    )

    # possible launch_parser
    # args:
    #   "launch":               Launch a specific version of Blender. If no file or version is specified,
    #                            the favorite build is chosen. If there is no favorite build, TODO: BUILD_CHOOSER
    #   "-f" | "--file":        Path to a specific Blender file to launch.
    #   "-v" | "--version":     Version to launch. If not specified, the latest stable release is used.

    args, argv = parser.parse_known_args()
    if argv:
        msg = _("unrecognized arguments: ") + " ".join(argv)
        ap.error(parser, msg)

    # Custom help is necessary for frozen Windows builds
    if args.help:
        ap.show_help(parser, update_parser, args)
        sys.exit(0)

    if args.debug:
        logging.root.setLevel(logging.DEBUG)
    else:
        logging.root.setLevel(logging.INFO)

    from modules.settings import set_library_folder
    from PyQt5.QtCore import QByteArray
    from PyQt5.QtNetwork import QLocalSocket
    from PyQt5.QtWidgets import QApplication
    from windows.dialog_window import DialogWindow
    from windows.main_window import BlenderLauncher
    from windows.update_window import BlenderLauncherUpdater

    # Create an instance of application and set its core properties
    app = QApplication([])
    app.setStyle("Fusion")
    app.setApplicationVersion(version)

    set_lib_folder: Path | None = args.set_library_folder
    if set_lib_folder is not None:
        if set_library_folder(str(set_lib_folder)):
            logging.info(f"Library folder set to {set_lib_folder!s}")
        else:
            logging.error("Failed to set library folder")
            dlg = DialogWindow(
                title="Warning",
                text="Passed path is not a valid folder or<br>it doesn't have write permissions!",
                accept_text="Quit",
                cancel_text=None,
                app=app,
            )
            dlg.show()
            sys.exit(app.exec())

    if args.command == "update":
        if args.instanced or not is_frozen():
            BlenderLauncherUpdater(app=app, version=version, release_tag=args.version)
            sys.exit(app.exec())
        else:
            # Copy the launcher to the updater position
            bl_exe, blu_exe = get_launcher_name()
            cwd = get_cwd()
            source = cwd / bl_exe
            dist = cwd / blu_exe
            shutil.copy(source, dist)

            # Run the updater with the instanced flag
            if get_platform() == "Windows":
                _popen([blu_exe, "--instanced", "update"])
            elif get_platform() == "Linux":
                os.chmod(blu_exe, 0o744)
                _popen(f'nohup "{blu_exe}" --instanced update')
            sys.exit(0)

    # if args.command == "launch":
    #     ...

    if not args.instanced:
        socket = QLocalSocket()
        socket.connectToServer("blender-launcher-server")
        is_running = socket.waitForConnected()
        if is_running:
            socket.write(QByteArray(version.encode()))
            socket.waitForBytesWritten()
            socket.close()
            return

    app.setQuitOnLastWindowClosed(False)
    BlenderLauncher(app=app, version=version, offline=args.offline)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
