from contextlib import contextmanager
from importlib.util import module_from_spec, spec_from_file_location
from logging import DEBUG, getLogger
from random import SystemRandom
from typing import Text

import coloredlogs

random = SystemRandom()


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


def escape(string, char):
    """
    Quotes a string with the given char. By example:

    >>> assert escape("O'Neil", "'") == "'O\\'Neil'"
    """
    return char + string.replace(char, f"\\{char}") + char


def import_file(name: Text, file_path: Text):
    """
    Imports a Python file as a module named luh3417.{name}
    """

    spec = spec_from_file_location(f"luh3417.{name}", file_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def random_password(
    n=50, chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890/>#"
):
    """
    Generates a secure random password
    """

    return "".join(random.choice(chars) for _ in range(0, n))


def run_main(main, doing):
    """
    Runs a main() function while taking care to catch the appropriate
    exceptions and do the cleaning up
    """

    # noinspection PyBroadException
    try:
        main()
    except KeyboardInterrupt:
        doing.logger.info("Quitting due to user signal")
    except SystemExit:
        pass
    except BaseException:
        doing.logger.exception("Unknown error")
    finally:
        from luh3417.luhssh import SshManager

        SshManager.shutdown()
