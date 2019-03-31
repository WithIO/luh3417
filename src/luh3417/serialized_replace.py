#!/usr/bin/env python3
import json
import re
from argparse import ArgumentParser
from enum import Enum
from sys import stderr
from typing import List, Tuple

ReplaceMap = List[Tuple[bytes, bytes]]

PHP_SER_RE = rb"^s:(\d+):\""

MYSQL_CHARS = [
    (b"\\0", b"\0"),
    (b"\\'", b"'"),
    (b'\\"', b'"'),
    (b"\\b", b"\b"),
    (b"\\n", b"\n"),
    (b"\\r", b"\r"),
    (b"\\t", b"\t"),
    (b"\\Z", bytes([26])),
    (b"\\\\", b"\\"),
]


def parse_args():
    """
    Configure the arguments parser and parses the arguments. Returns the
    parsing result.
    """

    parser = ArgumentParser(
        description="Replaces a string by another safely even if it lies "
        "within a PHP serialized value"
    )

    parser.add_argument("search")
    parser.add_argument("replace")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug")

    return parser.parse_args()


class StringType(Enum):
    """
    Different types of strings that can be recognized
    """

    RAW = 0
    PHP_SER = 1
    JSON = 2
    MYSQL = 3


def multi_replace(seq: bytes, mapping: ReplaceMap, reverse=False) -> bytes:
    """
    Replaces multiple search/replace couples at once
    """

    if reverse:
        d = dict((b, a) for a, b in mapping)
    else:
        d = dict(mapping)

    pattern = re.compile(b"|".join(re.escape(k) for k in d.keys()))

    return pattern.sub(lambda m: d[m.group(0)], seq)


def split(line):
    """
    Given a line of data, emit a couple (segment, type) which are the different
    kind of recognized strings
    """

    i = 0
    raw_start = 0

    while i < len(line):
        length = 0
        start = 0
        rest = line[i:]
        ser_m = re.match(PHP_SER_RE, rest)
        json_m = re.match(
            rb"\"(?:[^\"\\\0-\x1F\x7F\r\n]|\\(?:[\"\\/bfnrt]|u[a-fA-F0-9]{4}))*\"", rest
        )
        mysql_m = re.match(rb"'(?:[^'\\\r\n]|\\['\"0bnrtZ\\%_])*'", rest)

        is_php_ser = False
        is_json = bool(json_m)
        is_mysql = bool(mysql_m)

        if ser_m:
            length = int(ser_m.group(1))
            start = i + len(ser_m.group(0))
            try:
                is_php_ser = line[start + length : start + length + 2] == b'";'
            except IndexError:
                is_php_ser = False

        if is_php_ser or is_json or is_mysql:
            if raw_start != i:
                yield line[raw_start:i], StringType.RAW

        if is_php_ser:
            yield line[i : start + length + 2], StringType.PHP_SER
            i += len(ser_m.group(0)) + length + 2
            raw_start = i
        elif is_json:
            yield line[i : i + len(json_m.group(0))], StringType.JSON
            i += len(json_m.group(0))
            raw_start = i
        elif is_mysql:
            yield line[i : i + len(mysql_m.group(0))], StringType.MYSQL
            i += len(mysql_m.group(0))
            raw_start = i
        else:
            i += 1

    if i != raw_start:
        yield line[raw_start:], StringType.RAW


def uncap_json(s: bytes) -> bytes:
    return json.loads(s.decode("utf-8")).encode("utf-8")


def encapsulate_json(s: bytes) -> bytes:
    return json.dumps(s.decode("utf-8"), ensure_ascii=False).encode("utf-8")


def uncap_php_ser(s: bytes) -> bytes:
    m = re.match(PHP_SER_RE, s)
    return s[len(m.group(0)) : -2]


def encapsulate_php_ser(s: bytes) -> bytes:
    return b"s:" + f"{len(s)}".encode("utf-8") + b':"' + s + b'";'


def uncap_mysql(s: bytes) -> bytes:
    return multi_replace(s[1:-1], MYSQL_CHARS, reverse=False)


def encapsulate_mysql(s: bytes) -> bytes:
    return b"'" + multi_replace(s, MYSQL_CHARS, reverse=True) + b"'"


def uncap(s: bytes, type_: StringType) -> bytes:
    """
    Given a string literal of type_, extracts and returns its content
    """

    if type_ == StringType.PHP_SER:
        return uncap_php_ser(s)
    elif type_ == StringType.JSON:
        return uncap_json(s)
    elif type_ == StringType.MYSQL:
        return uncap_mysql(s)


def encapsulate(s: bytes, type_: StringType) -> bytes:
    """
    Encodes some content into something valid in the target string type
    """

    if type_ == StringType.PHP_SER:
        return encapsulate_php_ser(s)
    elif type_ == StringType.JSON:
        return encapsulate_json(s)
    elif type_ == StringType.MYSQL:
        return encapsulate_mysql(s)


def walk(data: bytes, mapping: ReplaceMap, depth=None) -> bytes:
    """
    Walks down the data and replaces things as it goes
    """

    out = b""

    for segment, type_ in split(data):
        if depth is not None:
            prefix = "-" * (1 + depth)
            stderr.write(f"{prefix}> {type_.name}: {segment.decode()}\n")
            stderr.flush()

        if type_ == StringType.RAW:
            out += multi_replace(segment, mapping)
        else:
            raw = uncap(segment, type_)
            replaced = walk(
                uncap(segment, type_), mapping, depth + 1 if depth is not None else None
            )

            if replaced != raw:
                out += encapsulate(replaced, type_)
            else:
                out += segment

    return out
