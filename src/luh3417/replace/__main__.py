from argparse import ArgumentParser
from typing import Optional, Sequence, Text

from luh3417.serialized_replace import walk
from luh3417.utils import make_doer, run_main, setup_logging

doing = make_doer("luh3417.replace")


def parse_args(argv: Optional[Sequence[Text]] = None):
    parser = ArgumentParser(description="Seeks and replaces serialized values")

    parser.add_argument("-i", "--input", required=True, help="Input file name")
    parser.add_argument("-o", "--output", required=True, help="Output file name")
    parser.add_argument("-b", "--before", nargs="+", help="String(s) to look for")
    parser.add_argument("-a", "--after", nargs="+", help="String(s) to replace by")
    parser.add_argument(
        "-c", "--charset", default="utf-8", help="What charset to use to read the file"
    )

    args = parser.parse_args(argv)

    if len(args.before) != len(args.after):
        parser.error("Not the same number of --before and --after")
        exit(1)

    return args


def main(argv: Optional[Sequence[Text]] = None):
    args = parse_args(argv)
    setup_logging()

    rep = [*zip(
        (x.encode(args.charset) for x in args.before),
        (x.encode(args.charset) for x in args.after),
    )]

    with open(args.input, "rb") as i, open(args.output, "wb") as o:
        for line in i:
            o.write(walk(line, rep))


def __main__():
    return run_main(main, doing)


if __name__ == "__main__":
    __main__()
