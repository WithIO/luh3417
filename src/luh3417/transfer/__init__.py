from copy import deepcopy
from typing import Dict, Text

from luh3417.luhfs import Location
from luh3417.utils import LuhError, import_file


class UnknownEnvironment(LuhError):
    pass


def load_generator(file_path: Text):
    """
    Loads the generator module from the specified file
    """

    return import_file("generator", file_path)


def apply_wp_config(patch: Dict, wp_config: Dict, source: Location) -> Dict:
    """
    Given a wp_config and a source, apply them into a patch

    - Make sure that the source arg is set
    - Put the DB settings in php_define
    - Also set wp_config properly
    """

    new_patch = deepcopy(patch)

    new_patch["args"] = {"source": f"{source}"}
    new_patch["wp_config"] = wp_config

    if "php_define" not in new_patch:
        new_patch["php_define"] = {}

    try:
        new_patch["php_define"].update(
            {
                "DB_HOST": wp_config["db_host"],
                "DB_USER": wp_config["db_user"],
                "DB_NAME": wp_config["db_name"],
                "DB_PASSWORD": wp_config["db_password"],
            }
        )
    except (KeyError, TypeError, AttributeError) as e:
        raise LuhError(f"Generated wp_config is incorrect: {e}")
    else:
        return new_patch
