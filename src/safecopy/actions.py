import os
from safecopy.file_copier import FileCopier

from .utils import delay, error_exit, exclude_path, log_message, verbose, verbose_log


def verify_copy(from_path, to_path, shared_path):
    """Verify the copy."""

    verbose(f"verifying: {shared_path}")

    # fresh copier to verify
    file_pair = FileCopier(from_path, to_path, shared_path)
    if file_pair.equal():
        verbose(f"verified: {shared_path}")
    else:
        # verify failure takes precendence over --persist
        error_exit("Unable to verify")


def copy_files(from_path, to_path, from_root, to_root, exclude_paths):
    """Copy files from from_path to to_path. Copy directories recursively.

    >>> def check_dir(from_path, to_path, shared_path):
    ...    dir_entries = os.scandir(from_path)
    ...    for dir_entry in dir_entries:
    ...        to_path = os.path.join(to_path, dir_entry.name)
    ...        if dir_entry.is_dir():
    ...            check_dir(dir_entry.path, to_path, shared_path)
    ...        else:
    ...             verify_copy(dir_entry.path, to_path, shared_path)

    >>> from tempfile import gettempdir

    >>> temp_dir = gettempdir()
    >>> test_from = os.path.join(temp_dir, 'test-safecopy-from')
    >>> if os.path.exists(test_from):
    ...     rmtree(test_from)
    >>> test_to = os.path.join(temp_dir, 'test-safecopy-to')
    >>> to_root = os.path.dirname(test_to)
    >>> if os.path.exists(test_to):
    ...     rmtree(test_to)

    # create a multi-level directory so we can verify metadata matches at all levels
    >>> from_test_subdir = os.path.join(test_from, 'subdir1', 'subdir2')
    >>> from_test_path = os.path.join(from_test_subdir, 'test-file.txt')
    >>> from_root = os.path.dirname(test_from)
    >>> os.makedirs(from_test_subdir)
    >>> with open(from_test_path, 'wt') as outfile:
    ...     __ = outfile.write('this is a test')

    >>> exclude_paths = []
    >>> copy_files(test_from, test_to, from_root, to_root, exclude_paths)

    >>> os.path.isdir(test_to)
    True

    >>> shared_path = test_from[len(from_root):].lstrip(os.sep)
    >>> verify_copy(test_from, test_to, shared_path)
    >>> check_dir(test_from, test_to, shared_path)

    >>> to_test_path = os.path.join(test_to, 'subdir1', 'subdir2', 'test-file.txt')
    >>> os.path.isfile(to_test_path)
    True

    >>> with open(to_test_path) as infile:
    ...     print(infile.read())
    this is a test
    """

    # shared_path is the shared part of the path
    # that currently exists in from_path,
    # and will exist in to_path, excluding the from_root
    shared_path = from_path[len(from_root) :].lstrip(os.sep)

    if exclude_path(from_path, from_root, exclude_paths):
        log_message(f"excluding {from_path}")

    else:
        file_pair = FileCopier(from_path, to_path, shared_path)
        if file_pair.equal():
            verbose_log(f"already equal: {shared_path}")

        else:
            # the dir entries to copy are in self.from_path and self.to_path
            # from_root and to_root are just so we can make and update dirs
            file_pair.make_dirs_and_copy(from_root, to_root)

        if os.path.isdir(from_path):
            verbose_log(f"dir: {shared_path}")

            # copy dir contents recursively
            dir_entries = sorted(os.scandir(from_path), key=lambda k: k.name)
            # for rsync compatibility, files then dirs
            for entry in dir_entries:
                # if entry is a file or symlink
                if entry.is_file():
                    full_from = entry.path
                    full_to = os.path.join(to_path, entry.name)
                    copy_files(full_from, full_to, from_root, to_root, exclude_paths)
                delay()
            for entry in dir_entries:
                # symlinks are included above by entry.is_file()
                # if entry is a dir that is not a symlink
                if entry.is_dir(follow_symlinks=False):
                    full_from = entry.path
                    full_to = os.path.join(to_path, entry.name)
                    copy_files(full_from, full_to, from_root, to_root, exclude_paths)
                delay()

            if not args.dryrun:
                # we need a check for stats_equal,
                # for the stats that copystat copies
                verbose_log(f"copy dir metadata from: {from_path}")
                verbose_log(f"                    to: {to_path}")
                # from_path and to_path are the dirs we just copied
                file_pair.copy_metadata(from_path, to_path)
