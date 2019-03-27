import json
import re
import subprocess
from contextlib import contextmanager
from logging import DEBUG, getLogger
from typing import TYPE_CHECKING, Text

import coloredlogs

if TYPE_CHECKING:
    from luh3417.luhfs import Location


class LuhError(Exception):
    """
    Managed errors that are emitted by the code in order to be displayed nicely
    (aka without stack trace) to the user. Basically if you know that something
    can go wrong then write a nice explicative message and throw it in a
    LuhError when it happens.
    """

    def __init__(self, message):
        self.message = message


def setup_logging():
    """
    Setups the log formatting
    """

    coloredlogs.install(
        level=DEBUG, fmt="%(asctime)s %(name)s[%(process)d] %(levelname)s %(message)s"
    )


def make_doer(name):
    """
    Generates the logger and the doing() context manager for a given name.

    The doing() context manager will display a message in the logs and handle
    exceptions occurring during execution, displaying them in the logs as well.

    If an exception occurs, the program is exited.
    """

    logger = getLogger(name)

    @contextmanager
    def doing(message):
        logger.info(message)

        # noinspection PyBroadException
        try:
            yield
        except LuhError as e:
            logger.error(e.message)
            exit(1)
        except Exception:
            logger.exception("Unknown error")
            exit(2)

    doing.logger = logger

    return doing


def run_php(code: str):
    """
    Runs PHP code and returns its output or None if there was an error
    """

    cp = subprocess.run(
        ["php"],
        input=code,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        encoding="utf-8",
    )

    if cp.returncode:
        return None

    return cp.stdout


def extract_php_constants(file: str):
    """
    Parses a PHP file to extract all the declared constants
    """

    define = re.compile(r"^\s*define\(")
    lines = ["<?php"]

    for line in file.splitlines(False):
        if define.match(line):
            lines.append(line)

    lines.extend(
        [
            "$const = get_defined_constants(true);",
            '$user = $const["user"];',
            "echo json_encode($user);",
        ]
    )

    try:
        data = run_php("\n".join(lines))
        return json.loads(data)
    except (ValueError, TypeError):
        raise LuhError("Configuration file has syntax errors")


def parse_wp_config(location: "Location", config_file_name: Text = "wp-config.php"):
    """
    Parses the WordPress configuration to get the DB configuration
    """

    config_location = location.child(config_file_name)
    config = config_location.get_content()
    const = extract_php_constants(config)

    try:
        return {
            "db_host": const["DB_HOST"],
            "db_user": const["DB_USER"],
            "db_password": const["DB_PASSWORD"],
            "db_name": const["DB_NAME"],
        }
    except KeyError as e:
        LuhError(f"Missing config value: {e}")
