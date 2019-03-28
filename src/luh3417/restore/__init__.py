import json
from json import JSONDecodeError
from typing import Text, Dict, Optional, List

from luh3417.luhfs import Location, parse_location
from luh3417.luhsql import LuhSql
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


def restore_db(db: LuhSql, dump_path: Text):
    """
    Restores the specified file into DB, using the wp config and remote
    location to connect the DB.
    """

    try:
        with open(dump_path, "r", encoding="utf-8") as f:
            db.restore_dump(f)
    except OSError as e:
        raise LuhError(f"Could not read SQL dump: {e}")


def run_queries(db: LuhSql, queries: List[Text]):
    """
    Runs all the queries from the config
    """

    for query in queries:
        db.run_query(query)


def patch_config(config: Dict, patch_location: Optional[Text]) -> Dict:
    """
    Applies a configuration patch from the source patch file, which will
    alter the restoration process.

    Available options:

    - `owner` - Same syntax as chown owner, changes the ownership of restored
      files
    - `git` - A list of repositories to clone (cf below).
    - `setup_queries` - A list of SQL queries (as strings) that will be
      executed after restoring the DB

    Example for the `git` value:

        "git": [
            {
                "location": "wp-content/themes/jupiter-child",
                "repo": "git@gitlab.com:your_company/jupiter_child.git",
                "version": "master"
            }
        ]
    """

    base_config = {"owner": None, "git": [], "setup_queries": []}

    for k, v in config.items():
        base_config[k] = v

    if patch_location:
        try:
            with open(patch_location, "r", encoding="utf-8") as f:
                patch = json.load(f)
        except OSError as e:
            raise LuhError(f"Could not open patch file: {e}")
        except JSONDecodeError as e:
            raise LuhError(f"Could not decode patch file: {e}")
        else:
            for k, v in patch.items():
                base_config[k] = v

    return base_config
