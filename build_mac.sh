PYTHONOPTIMIZE=2 pyinstaller \
    --windowed \
    --hidden-import "pynput.keyboard._darwin" \
    --hidden-import "pynput.mouse._darwin" \
    --name="Blender Launcher" \
    --add-binary="source/resources/certificates/custom.pem:files" \
    --distpath="./dist/release" \
    source/main.py
