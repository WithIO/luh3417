import subprocess
from dataclasses import dataclass
from subprocess import DEVNULL, PIPE
from typing import List, Optional, Text, TextIO

from luh3417.luhfs import LocalLocation, Location, SshLocation
from luh3417.utils import LuhError


def create_from_source(wp_config, source: Location):
    """
    Using a Location object and the WP config, generates the appropriate LuhSql
    object
    """

    if isinstance(source, SshLocation):
        ssh_proxy = f"{source.user}@{source.host}"
    elif isinstance(source, LocalLocation):
        ssh_proxy = None
    else:
        raise LuhError(f"Unknown source type: {source.__class__.__name__}")

    return LuhSql(
        host=wp_config["db_host"],
        user=wp_config["db_user"],
        password=wp_config["db_password"],
        db_name=wp_config["db_name"],
        ssh_proxy=ssh_proxy,
    )


@dataclass
class LuhSql:
    """
    A helper class to access MySQL locally or remotely through a SSH proxy
    """

    host: Text
    user: Text
    password: Text
    db_name: Text
    ssh_proxy: Optional[Text]

    def args(self, args: List[Text]):
        """
        Generates the args to run a command
        """

        if self.ssh_proxy:
            return ["ssh", self.ssh_proxy] + args
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
                        "-p",
                        "-h",
                        self.host,
                        self.db_name,
                    ]
                ),
                stderr=PIPE,
                stdout=f,
                stdin=PIPE,
                encoding="utf-8",
            )

            p.stderr.read(1)
            p.stdin.write(f"{self.password}\n")

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
