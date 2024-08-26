import os
import json
import logging

from modules._platform import get_config_path, get_cwd

logger = logging.getLogger()
api_path = os.path.join(get_config_path(), "Blender Launcher API.json")
internal_api_path = (get_cwd() / "source/resources/api/blender_launcher_api.json").as_posix()


def update_local_api_files(data):
    if not os.path.exists(get_config_path()):
        os.makedirs(get_config_path())
        logger.info(f"Created config directory in {get_config_path()}")

    with open(api_path, "w") as f:
        json.dump(data, f, indent=4)
        logger.info(f"Updated API file in {api_path}")


def read_blender_version_list():
    if not os.path.exists(api_path):
        logger.error(f"API file not found in {api_path}")
        api = internal_api_path
    else:
        api = api_path

    with open(api, "r") as f:
        data = json.load(f)

    # Dictionary {"Verison Number" : "LTS"}
    blender_vesrion = data["blender_versions"]
    return blender_vesrion


def lts_blender_version():
    blender_version = read_blender_version_list()
    lts_vesrion = []
    for version, lts in blender_version.items():
        if lts == "LTS":
            lts_vesrion.append(version)

    return tuple(lts_vesrion)


def dropdown_blender_version():
    blender_version = read_blender_version_list()
    index = 0
    dropdown_blender_version = {}

    for key, _ in blender_version.items():
        dropdown_blender_version[key] = index
        index += 1

    # Dictionary {"Verison Number" : index}
    return dropdown_blender_version
