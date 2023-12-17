#!/usr/bin/bash

# get the distro and get the Title version
distro_id=$(python3 -c "import distro; print(distro.id())" | awk '{printf("%s%s\n",toupper(substr($0,1,1)),substr($0,2))}')
version=$(git describe --abbrev=0 --tags)

echo "Zipping to Blender_Launcher_${version}_${distro_id}_x64.zip"
cd ./dist/release/ || exit
zip "Blender_Launcher_${version}_${distro_id}_x64.zip" "./Blender Launcher"