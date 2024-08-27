import json
import logging
from functools import lru_cache
from pathlib import Path

from modules._platform import get_config_path, get_cwd

logger = logging.getLogger()

config_path = Path(get_config_path())
api_path = config_path / "Blender Launcher API.json"
internal_api_path = get_cwd() / "source/resources/api/blender_launcher_api.json"


def update_local_api_files(data):
    if not config_path.exists():
        config_path.mkdir(parents=True)
        logger.info(f"Created config directory in {config_path}")

    try:
        with open(api_path, "w") as f:
            json.dump(data, f, indent=4)
            logger.info(f"Updated API file in {api_path}")
        read_bl_api.cache_clear()
    except OSError as e:
        logger.error(f"Failed to write API file: {e}")

@lru_cache(maxsize=1)
def read_bl_api()-> dict:
    api = api_path if api_path.exists() else internal_api_path
    if api == internal_api_path:
        logger.error(f"API file not found in {api_path}. Using internal API file.")

    with open(api) as f:
        return json.load(f)


def read_blender_version_list() -> dict[str, str]:
    return read_bl_api().get("blender_versions", {})


def lts_blender_version():
    return tuple(version for version, lts in read_blender_version_list().items() if lts == "LTS")


def dropdown_blender_version() -> dict[str, int]:
    """Ex:

    {
        "4.0": 0,
        "3.6": 1,
        "3.5": 2,
        "3.4": 3
    }
    """
    return {key: index for index, key in enumerate(read_blender_version_list().keys())}
