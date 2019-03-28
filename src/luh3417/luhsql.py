import subprocess
from dataclasses import dataclass
from subprocess import DEVNULL, PIPE
from typing import List, Optional, Text, TextIO

from luh3417.luhfs import LocalLocation, Location, SshLocation
from luh3417.luhssh import SshManager
from luh3417.serialized_replace import ReplaceMap, walk
from luh3417.utils import LuhError


def create_from_source(wp_config, source: Location):
    """
    Using a Location object and the WP config, generates the appropriate LuhSql
    object
    """

    if isinstance(source, SshLocation):
        ssh_user = source.user
        ssh_host = source.host
    elif isinstance(source, LocalLocation):
        ssh_user = None
        ssh_host = None
    else:
        raise LuhError(f"Unknown source type: {source.__class__.__name__}")

    return LuhSql(
        host=wp_config["db_host"],
        user=wp_config["db_user"],
        password=wp_config["db_password"],
        db_name=wp_config["db_name"],
        ssh_user=ssh_user,
        ssh_host=ssh_host,
    )


def patch_sql_dump(source_path: Text, dest_path: Text, replace: ReplaceMap):
    """
    Patches the SQL dump found at source_path into a new SQL dump found in
    dest_path. It will use the replace map to replace values.

    Values are replaced in a holistic way so that PHP serialized values are
    not broken and escaped character are detected as such. This is by far not
    perfect but seems sufficient for most use cases.
    """

    try:
        with open(source_path, "rb") as i, open(dest_path, "wb") as o:
            for line in i:
                o.write(walk(line, replace))
    except OSError as e:
        raise LuhError(f"Could not open SQL dump: {e}")


@dataclass
class LuhSql:
    """
    A helper class to access MySQL locally or remotely through a SSH proxy
    """

    host: Text
    user: Text
    password: Text
    db_name: Text
    ssh_user: Optional[Text]
    ssh_host: Optional[Text]

    def args(self, args: List[Text]):
        """
        Generates the args to run a command
        """

        if self.ssh_host and self.ssh_user:
            return SshManager.instance(self.ssh_user, self.ssh_host).get_args(args)
        else:
            return args

    def dump_to_file(self, file_path: Text):
        """
        Dumps the database into the specified file
        """

        with open(file_path, "w", encoding="utf-8") as f:
            p = subprocess.Popen(
                self.args(
                    [
                        "mysqldump",
                        "--hex-blob",
                        "-u",
                        self.user,
                        f"-p{self.password}",
                        "-h",
                        self.host,
                        self.db_name,
                    ]
                ),
                stderr=PIPE,
                stdout=f,
                stdin=DEVNULL,
                encoding="utf-8",
            )

            _, err = p.communicate()

            if p.returncode:
                raise LuhError(f"Could not dump MySQL DB: {err}")

    def restore_dump(self, fp: TextIO):
        """
        Restores a dump into the DB, reading the dump from an input TextIO
        (which can be the stdout of another process or simply an open file, by
        example).
        """

        p = subprocess.Popen(
            self.args(
                [
                    "mysql",
                    "-u",
                    self.user,
                    f"-p{self.password}",
                    "-h",
                    self.host,
                    self.db_name,
                ]
            ),
            stderr=PIPE,
            stdout=DEVNULL,
            stdin=fp,
            encoding="utf-8",
        )

        _, err = p.communicate()

        if p.returncode:
            raise LuhError(f"Could not import MySQL DB: {err}")

    def run_query(self, query: Text):
        """
        Runs a single SQL query
        """

        p = subprocess.Popen(
            self.args(
                [
                    "mysql",
                    "-u",
                    self.user,
                    f"-p{self.password}",
                    "-h",
                    self.host,
                    self.db_name,
                ]
            ),
            stderr=PIPE,
            stdout=DEVNULL,
            stdin=PIPE,
            encoding="utf-8",
        )

        _, err = p.communicate(query)

        if p.returncode:
            raise LuhError(f"Could not run MySQL query: {err}")
