import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from posixpath import join
from subprocess import CompletedProcess, Popen
from typing import Text

from luh3417.utils import LuhError

SSH_RE = re.compile(r"^([a-zA-Z0-9_-]+)@((?:[a-zA-Z0-9-]+\.)*(?:[a-zA-Z0-9-]+)):(.*)$")


def parse_location(location: Text) -> "Location":
    """
    Guess the location type and generates the appropriate object
    """

    sm = SSH_RE.match(location)

    if sm:
        return SshLocation(user=sm.group(1), host=sm.group(2), path=sm.group(3))
    else:
        return LocalLocation(path=location)


@dataclass
class Location:
    """
    Base location object. This abstraction allows to do very specific
    operations on local or remote file systems. This is not a generic file
    system implementation but rather a very specialized one so that every
    operation can be implemented the most possibly efficient way.
    """

    path: Text

    def get_content(self) -> Text:
        """
        Calling this returns the whole content of the file
        """

        raise NotImplementedError

    def ensure_exists_as_dir(self) -> None:
        """
        This ensures that the location is a directory and exists (as well as
        all parents)
        """

        raise NotImplementedError

    def archive_local_dir(self, local_path) -> None:
        """
        Puts all the content of `local_path` into a TAR/GZ archive at the
        current location.

        Beware it's probably the opposite of what you imagined (:
        """

        raise NotImplementedError

    def child(self, file_name) -> "Location":
        """
        Generates the location object for a child file named file_name
        """

        return replace(self, path=join(self.path, file_name))

    def rsync_path(self, as_dir: bool = True):
        """
        Generates the equivalent rsync path for this location
        """

        path = f"{self}"

        if as_dir and (not path or path[-1] != "/"):
            path += "/"
        elif not as_dir and path and path[-1] == "/":
            path = path[0:-1]

        return path


@dataclass
class SshLocation(Location):
    """
    A file located on a remote server accessed through SSH
    """

    user: Text
    host: Text
    path: Text

    def __str__(self):
        return f"{self.user}@{self.host}:{self.path}"

    @property
    def ssh_target(self):
        """
        Generates the target to give to SSH for this location
        """

        return f"{self.user}@{self.host}"

    def ssh_run(self, args, *p_args, **kwargs) -> CompletedProcess:
        """
        Runs a process remotely using subprocess.run(). This will enforce
        an UTF-8 encoding for stdin/out. Otherwise it's the same argument
        as run() and the SSH command is automatically appended to the args.
        """

        kwargs = dict(kwargs, encoding="utf-8")

        new_args = ["ssh", self.ssh_target]
        new_args.extend(args)

        cp = subprocess.run(new_args, *p_args, **kwargs)

        if cp.returncode == 255:
            raise LuhError(
                f"SSH connection to {self.ssh_target} could not be established"
            )

        return cp

    def ssh_popen(self, args, *p_args, **kwargs) -> Popen:
        """
        Opens a process through SSH. It's the same arguments as Popen() except
        that the SSH command will be prepended to the args.
        """

        new_args = ["ssh", self.ssh_target]
        new_args.extend(args)

        cp = subprocess.Popen(new_args, *p_args, **kwargs)

        if cp.returncode == 255:
            raise LuhError(
                f"SSH connection to {self.ssh_target} could not be established"
            )

        return cp

    def get_content(self) -> Text:
        """
        Uses a remote cat to get the content
        """

        cp = self.ssh_run(
            ["cat", self.path], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )

        if cp.returncode == 1:
            raise LuhError(
                f"The file {self} does not exist or you don't have "
                f"permissions to read it"
            )
        elif cp.returncode:
            raise LuhError(f"Unknown error while reading {self}")

        return cp.stdout

    def ensure_exists_as_dir(self) -> None:
        """
        Runs mkdir -p remotely
        """

        cp = self.ssh_run(
            ["mkdir", "-p", self.path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        if cp.returncode:
            raise LuhError(f"Could not create {self} as a directory: {cp.stderr}")

    def archive_local_dir(self, local_path: Text):
        """
        Generates the archive locally and pipe it to a remote dd to write it
        on disk on the other side
        """

        tar = subprocess.Popen(
            ["tar", "-C", local_path, "-c", "-z", "."],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        dd = self.ssh_popen(
            ["dd", f"of={self.path}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            stdin=tar.stdout,
        )

        dd.communicate()
        tar.communicate()

        if dd.returncode:
            raise LuhError(f"Could not write remote archive: {dd.stderr}")

        if tar.returncode:
            raise LuhError(f"Could not create the archive: {tar.stderr}")


@dataclass
class LocalLocation(Location):
    """
    Runs everything locally, everything inside is pretty straightforward
    """

    path: Text

    def __str__(self):
        return self.path

    def get_content(self) -> Text:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return f.read()
        except PermissionError:
            raise LuhError(f"You don't have the permission to read {self}")
        except FileNotFoundError:
            raise LuhError(f"The file {self} does not exist")
        except OSError:
            raise LuhError(f"Unknown error while opening {self}")

    def ensure_exists_as_dir(self) -> None:
        try:
            Path(self.path).mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise LuhError(f"You don't have the permission the create {self}")
        except NotADirectoryError:
            raise LuhError(f"Some component of {self} is not a directory")
        except OSError:
            raise LuhError(f"Unknown error while creating {self}")

    def archive_local_dir(self, local_path):
        cp = subprocess.run(
            ["tar", "-C", local_path, "-c", "-z", "-f", self.path, "."],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if cp.returncode:
            raise LuhError(f"Could not create archive {self.path}")
