import json
import re
import subprocess
from itertools import chain
from typing import Any, Dict, Text

from luh3417.luhfs import Location
from luh3417.utils import LuhError

PHP_STR = (
    r"\"(?:[^\"\\]|\\(?:[nrtvef\\$\"]|[0-7]{1,3}|x[0-9A-Fa-f]{1,2}|u[0-9A-Fa-f]+))*\""
    r"|'(?:[^'\\]|\\')*'"
)


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


def parse_php_string(string: Text) -> Text:
    """
    Parses a PHP string literal (including quotes) and returns the equivalent
    Python string (as a string, not a literal)
    """

    parser = f"<?php echo json_encode({string});"

    try:
        data = run_php(parser)
        return json.loads(data)
    except (ValueError, TypeError):
        raise LuhError("Invalid PHP string")


def encode_php_string(string: Text) -> Text:
    """
    Encodes a string into something that can be given to PHP as a string
    literal
    """

    quoted = string.replace("'", "\\'")
    return f"'{quoted}'"


def encode_php_value(val):
    """
    Transforms a JSON-encodable value into a PHP literal
    """

    data = encode_php_string(json.dumps(val))
    parser = f"<?php var_export(json_decode({data}, true));"

    try:
        data = run_php(parser)
        assert data is not None
        return data
    except AssertionError:
        raise LuhError(f"Could not encode to PHP value: {repr(val)}")


def set_wp_config_values(values: Dict[Text, Any], file_path: Text):
    """
    Makes sure that the key/values set in values are set to this value in
    wp-config.php.

    - Existing define() are modified to get the new value
    - Missing define() are added at the top of the file

    Values must be JSON-encodable
    """

    try:
        e = re.compile(r"^\s*define\(\s*(" + PHP_STR + ")")
        out = []
        patched = set()

        with open(file_path, "r", encoding="utf-8") as f:
            for line in (x.rstrip("\r\n") for x in f.readlines()):
                m = e.match(line)

                if e.match(line):
                    key = parse_php_string(m.group(1))
                else:
                    key = None

                if key in values:
                    out.append(
                        f"define("
                        f"{encode_php_string(key)}, "
                        f"{encode_php_value(values[key])}"
                        f");"
                    )
                    patched.add(key)
                else:
                    out.append(line)

        missing = set(values.keys()) - patched
        extra = []

        if missing:
            extra = ["/** Extra values created by LUH3417 */"]

            for k in missing:
                v = values[k]
                extra.append(
                    f"define("
                    f"{encode_php_string(k)}, "
                    f"{encode_php_value(v)}"
                    f");"
                )

            extra.append("")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(chain(out[0:1], extra, out[1:])) + "\n")
    except OSError as e:
        raise LuhError(f"Could not open config file at {file_path}: {e}")
