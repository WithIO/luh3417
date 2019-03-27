from argparse import ArgumentParser, Namespace
from os.path import join
from tempfile import TemporaryDirectory

from luh3417.luhfs import Location, parse_location
from luh3417.restore import (
    get_remote,
    get_wp_config,
    read_config,
    restore_db,
    restore_files,
)
from luh3417.utils import make_doer, setup_logging

doing = make_doer("luh3417.restore")


def parse_args() -> Namespace:
    """
    Parse arguments from CLI
    """

    parser = ArgumentParser(description="Restores a snapshot")

    parser.add_argument(
        "snapshot",
        help=(
            "Location of the snapshot file. Syntax: `~/snap.tar.gz` or "
            "`user@host:snap.tar.gz`"
        ),
        type=parse_location,
    )

    return parser.parse_args()


def main():
    """
    Executes things in order
    """

    setup_logging()
    args = parse_args()
    snap: Location = args.snapshot

    with TemporaryDirectory() as d:
        with doing("Extracting archive"):
            snap.extract_archive_to_dir(d)

        with doing("Reading configuration"):
            config = read_config(join(d, "settings.json"))

        with doing("Restoring files"):
            remote = get_remote(config)
            restore_files(join(d, "wordpress"), remote)

        with doing("Restoring DB"):
            wp_config = get_wp_config(config)
            restore_db(wp_config, remote, join(d, "dump.sql"))


if __name__ == "__main__":
    main()
