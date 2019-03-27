from luh3417.luhfs import Location
import subprocess

from luh3417.utils import LuhError


def copy_files(remote: Location, local: Location):
    """
    Use rsync to copy files from a location to another
    """

    local.ensure_exists_as_dir()

    cp = subprocess.run(
        [
            "rsync",
            "-rtv",
            "--exclude=.git",
            remote.rsync_path(True),
            local.rsync_path(True),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    if cp.returncode:
        raise LuhError(f"Error while copying files: {cp.stderr}")
