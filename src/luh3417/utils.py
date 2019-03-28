from contextlib import contextmanager
from logging import DEBUG, getLogger

import coloredlogs


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
