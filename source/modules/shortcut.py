import os
import sys
from pathlib import Path
from shutil import copyfile

from modules._platform import get_cwd, get_launcher_name, get_platform
from modules.settings import get_library_folder


def create_shortcut(folder, name):
    platform = get_platform()
    library_folder = Path(get_library_folder())

    if platform == "Windows":
        import win32com.client
        from win32comext.shell import shell, shellcon

        targetpath = library_folder / folder / "blender.exe"
        workingdir = library_folder / folder
        desktop = shell.SHGetFolderPath(0, shellcon.CSIDL_DESKTOP, None, 0)
        dist = Path(desktop) / (name + ".lnk")

        if getattr(sys, "frozen", False):
            icon = sys._MEIPASS + "/files/winblender.ico"  # noqa: SLF001
        else:
            icon = Path("./resources/icons/winblender.ico").resolve().as_posix()

        icon_location = library_folder / folder / "winblender.ico"
        copyfile(icon, icon_location.as_posix())

        _WSHELL = win32com.client.Dispatch("Wscript.Shell")
        wscript = _WSHELL.CreateShortCut(dist.as_posix())
        wscript.Targetpath = targetpath.as_posix()
        wscript.WorkingDirectory = workingdir.as_posix()
        wscript.WindowStyle = 0
        wscript.IconLocation = icon_location.as_posix()
        wscript.save()
    elif platform == "Linux":
        _exec = library_folder / folder / "blender"
        icon = library_folder / folder / "blender.svg"
        desktop = Path.home() / "Desktop"
        filename = name.replace(" ", "-")
        dist = desktop / (filename + ".desktop")

        kws = (
            "3d;cg;modeling;animation;painting;"
            "sculpting;texturing;video editing;"
            "video tracking;rendering;render engine;"
            "cycles;game engine;python;"
        )

        desktop_entry = "\n".join(
            [
                "[Desktop Entry]",
                f"Name={name}",
                "Comment=3D modeling, animation, rendering and post-production",
                f"Keywords={kws}",
                "Icon={}".format(icon.as_posix().replace(" ", r"\ ")),
                "Terminal=false",
                "Type=Application",
                "Categories=Graphics;3DGraphics;",
                "MimeType=application/x-blender;",
                "Exec={} %f".format(_exec.as_posix().replace(" ", r"\ ")),
            ]
        )
        with open(dist, "w", encoding="utf-8") as file:
            file.write(desktop_entry)

        os.chmod(dist, 0o744)



def get_shortcut_type() -> str:
    """ ONLY FOR VISUAL REPRESENTATION """
    return {
        "Windows": "Shortcut",
        "Linux":   "Desktop file",
    }.get(get_platform(), "Shortcut")



# def get_default_shortcut_destination():
#     return {
#         "Windows": Path.home() / "Desktop",
#         "Linux":   Path.home()
#     }

def generate_program_shortcut(destination: Path):
    platform = get_platform()

    if platform == "Windows":
        ...

    elif platform == "Linux":
        import shlex

        bl_exe, _ = get_launcher_name()
        cwd = get_cwd()
        source = cwd / bl_exe

        _exec = source
        text = "\n".join(
            [
                "[Desktop Entry]",
                "Name=Blender Launcher V2",
                "GenericName=Launcher",
                f"Exec={shlex.quote(str(_exec))} __launch_target",
                "MimeType=application/x-blender;",
                "Icon=blender-icon",
                "Terminal=false",
                "Type=Application",
            ]
        )

        with destination.open("w", encoding="utf-8") as file:
            file.write(text)

        os.chmod(destination, 0o744)


# generate_program_shortcut(Path("~/.local/share/applications/BLV2.desktop").expanduser())
