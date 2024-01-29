import os
from pathlib import Path

cwd = Path.cwd()
dist = Path(r"source/resources/styles")
styles = sorted((cwd / dist).glob("*.css"))

with (dist / "global.qss").open("w") as outfile:
    for style in styles:
        outfile.write(style.read_text())
        outfile.write("\n")

os.system("pyrcc5 source/resources/resources.qrc -o source/resources_rc.py")
