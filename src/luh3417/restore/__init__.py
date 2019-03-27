import json
from typing import Text, Dict

from luh3417.luhfs import Location, parse_location
from luh3417.luhsql import create_from_source
from luh3417.snapshot import copy_files
from luh3417.utils import LuhError


def read_config(file_path: Text):
    """
    Read configuration from JSON file (extracted from the snapshot)
    """

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise LuhError("Configuration file is not valid JSON")
    except OSError as e:
        raise LuhError(f"Error while opening file: {e}")


def get_remote(config: Dict) -> Location:
    """
    Reads the configuration to extract the address of the remote
    """

    try:
        return parse_location(config["args"]["source"])
    except KeyError:
        raise LuhError("Configuration is incomplete, missing args.source")


def get_wp_config(config: Dict) -> Dict:
    """
    Reads the configuration to extract the database configuration
    """

    try:
        return config["wp_config"]
    except KeyError:
        raise LuhError("Configuration is incomplete, missing wp_config")


def restore_files(wp_root: Text, remote: Location):
    """
    Restores the file from the local wp_root to the remote location
    """

    local = parse_location(wp_root)
    copy_files(local, remote, delete=True)


def restore_db(wp_config, remote: Location, dump_path: Text):
    """
    Restores the specified file into DB, using the wp config and remote
    location to connect the DB.
    """

    try:
        db = create_from_source(wp_config, remote)

        with open(dump_path, "r", encoding="utf-8") as f:
            db.restore_dump(f)
    except OSError as e:
        raise LuhError(f"Could not read SQL dump: {e}")
