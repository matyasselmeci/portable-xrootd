import errno
import os
import re
import subprocess
import sys
import typing


class Error(Exception):
    pass


Pathable = typing.Union[str, os.PathLike]


def statusmsg(*args):
    if sys.stdout.isatty():
        print("\x1b[35;1m>>> ", " ".join(args), "\x1b[0m")
    else:
        print(">>> ".join(args))


def errormsg(*args):
    if sys.stdout.isatty():
        print("\x1b[31;1m*** ", " ".join(args), "\x1b[0m")
    else:
        print("*** ".join(args))


def safe_makedirs(path, mode=511):
    try:
        os.makedirs(path, mode)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def safe_symlink(src, dst):
    try:
        os.symlink(src, dst)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def to_str(strlike, encoding="latin-1", errors="backslashescape"):
    if not isinstance(strlike, str):
        if str is bytes:
            return strlike.encode(encoding, errors)
        else:
            return strlike.decode(encoding, errors)
    else:
        return strlike


def to_bytes(strlike, encoding="latin-1", errors="backslashescape"):
    if not isinstance(strlike, bytes):
        return strlike.encode(encoding, errors)
    else:
        return strlike


def sanitize_image_tag(image_tag: str) -> str:
    """
    Return the sanitized version of an image tag.
    A tag name follows the same rules as DNS for what's permitted to be in it.
    """
    it = image_tag.strip()
    it = re.sub(r'[^a-zA-Z0-9.-]+', '-', it)
    it = it[:64]
    it = it.strip('.-')
    return it


class MountProcFS:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.proc_dir = os.path.join(root_dir, 'proc')

    def __enter__(self):
        safe_makedirs(self.proc_dir)
        subprocess.check_call(['mount', '-t', 'proc', 'proc', self.proc_dir])

    def __exit__(self, exc_type, exc_value, traceback):
        subprocess.call(['umount', self.proc_dir])


VALID_DVERS = ["el8", "el9", "el10"]
VALID_BASEARCHES = ["x86_64", "aarch64"]
DEFAULT_BASEARCH = VALID_BASEARCHES[0]
