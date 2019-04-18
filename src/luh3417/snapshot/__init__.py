import subprocess

from luh3417.luhfs import Location
from luh3417.utils import LuhError


def copy_files(remote: Location, local: Location, delete: bool = False):
    """
    Use rsync to copy files from a location to another
    """

    local.ensure_exists_as_dir()

    args = [
        "rsync",
        "-rz",
        "--exclude=.git",
        "--exclude=.idea",
        "--exclude=*.swp",
        "--exclude=*.un~",
    ]

    if delete:
        args.append("--delete")

    args += [remote.rsync_path(True), local.rsync_path(True)]

    cp = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    if cp.returncode:
        raise LuhError(f"Error while copying files: {cp.stderr}")
