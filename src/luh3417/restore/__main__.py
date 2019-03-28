from argparse import ArgumentParser, Namespace
from os.path import join
from tempfile import TemporaryDirectory

from luh3417.luhfs import Location, parse_location
from luh3417.luhsql import create_from_source
from luh3417.luhssh import SshManager
from luh3417.restore import (
    get_remote,
    get_wp_config,
    patch_config,
    read_config,
    restore_db,
    restore_files,
    run_queries,
)
from luh3417.utils import make_doer, setup_logging

doing = make_doer("luh3417.restore")


def parse_args() -> Namespace:
    """
    Parse arguments from CLI
    """

    parser = ArgumentParser(description="Restores a snapshot")

    parser.add_argument("-p", "--patch", help="A settings patch file")

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

    try:
        with TemporaryDirectory() as d:
            with doing("Extracting archive"):
                snap.extract_archive_to_dir(d)

            with doing("Reading configuration"):
                config = patch_config(read_config(join(d, "settings.json")), args.patch)

            with doing("Restoring files"):
                remote = get_remote(config)
                restore_files(join(d, "wordpress"), remote)

            if config["git"]:
                with doing("Cloning Git repos"):
                    for repo in config["git"]:
                        location = remote.child(repo["location"])
                        location.set_git_repo(repo["repo"], repo["version"])
                        doing.logger.info(
                            "Cloned %s@%s to %s",
                            repo["repo"],
                            repo["version"],
                            location,
                        )

            if config["owner"]:
                with doing("Changing files owner"):
                    remote.chown(config["owner"])

            with doing("Restoring DB"):
                wp_config = get_wp_config(config)
                db = create_from_source(wp_config, remote)
                restore_db(db, join(d, "dump.sql"))

            if config["setup_queries"]:
                with doing("Running setup queries"):
                    run_queries(db, config["setup_queries"])
    except KeyboardInterrupt:
        doing.logger.info('Quitting due to user signal')
    finally:
        SshManager.shutdown()


if __name__ == "__main__":
    main()
