import os
import platform
from shutil import copystat

from solidlibs.os.command import run_verbose
from solidlibs.os.fs import why_file_permission_denied

from .consts import BUFFER_1K, BUFFER_1M, COPYING_FILE, UID_GID_MASK
from .utils import (delay, delete, error_exit, log, log_message, verbose,
                    verbose_log, warn)

changed_dirs = set()


class FileCopier:
    """Copy a file to another path.

    FileCopier.equal() returns True if the files are byte-for-byte
    equal. This does not say anything about metadata.

    FileCopier.count_equal_bytes() returns the count of equal bytes. The count
    lets us start a copy at the first unequal byte.
    This is particularly effective if the last copy to to_path
    wasn't complete, or if from_path was updated by appending.
    """

    def __init__(self, from_path, to_path, shared_path):
        self.from_path = from_path
        self.to_path = to_path
        self.shared_path = shared_path

        self.count = 0

    def count_equal_bytes(self):
        """Count how many leading bytes are equal."""

        # In order to directly compare equal size buffers from from_path
        # and to_path, we don't rely on read() to guess the buffer size
        buffer_size = BUFFER_1K

        if self.count == 0:
            ok = (
                os.path.isfile(self.from_path)
                and (not os.path.islink(self.from_path))
                and os.path.exists(self.to_path)
            )

            if ok:
                with open(self.from_path, "rb") as from_file:
                    with open(self.to_path, "rb") as to_file:
                        self.count = 0
                        log_message("counting equal bytes")

                        from_bytes = from_file.read(buffer_size)
                        to_bytes = to_file.read(buffer_size)
                        while from_bytes and to_bytes and (from_bytes == to_bytes):
                            self.count = self.count + len(from_bytes)
                            # verbose_log('equal so far: {}'.format(self.count))
                            # verbose_log('read from_file')
                            from_bytes = from_file.read(buffer_size)
                            # verbose_log('read to_file')
                            to_bytes = to_file.read(buffer_size)

                            delay()

                        last_buffer_size = min(len(from_bytes), len(to_bytes))
                        index = 0
                        if (index < last_buffer_size) and (
                            from_bytes[index] == to_bytes[index]
                        ):
                            verbose_log(
                                f"including last partial buffer: {last_buffer_size}"
                            )

                        while (index < last_buffer_size) and (
                            from_bytes[index] == to_bytes[index]
                        ):
                            self.count = self.count + 1
                            index = index + 1

        verbose_log(f"{self.count} equal bytes")

        return self.count

    def both_exist(self):
        """Test that both files exist."""

        # check to_path first, since from_path very likely exists
        to_exists = os.path.exists(self.to_path)
        if to_exists:
            from_exists = os.path.exists(self.from_path)
            if from_exists:
                equal = True
            else:
                equal = False
                log_message(
                    f"unequal because source path does not exist: {self.from_path}"
                )
        else:
            equal = False
            log_message(f"unequal because dest path does not exist: {self.to_path}")

        return equal

    def types_equal(self):
        """Test that paths are both files, or both dirs,
        or both links with the same target.
        """

        if os.path.islink(self.from_path):
            if os.path.islink(self.to_path):
                from_target = os.readlink(self.from_path)
                to_target = os.readlink(self.to_path)
                equal = from_target == to_target
                if not equal:
                    log_message(
                        f"unequal: link targets are different: {self.shared_path}"
                    )
            else:
                equal = False
                log_message(
                    f"unequal: from_path is a link and to_path is not: {self.shared_path}"
                )

        # isfile() returns True on regular files and links
        # so we checked for links above
        elif os.path.isfile(self.from_path):
            equal = os.path.isfile(self.to_path)
            if not equal:
                log_message(
                    f"unequal: from_path is a file and to_path is not: {self.shared_path}"
                )

        elif os.path.isdir(self.from_path):
            equal = os.path.isdir(self.to_path)
            if not equal:
                log_message(
                    f"unequal: from_path is a dir and to_path is not: {self.shared_path}"
                )

        else:
            log_message(
                f"skipped because file is not a link, file, or dir: {self.from_path}"
            )
            # set equal so we won't try to copy it
            equal = True

        return equal

    def permissions_equal(self):
        """Test that permissions are equal.

        Because we don't set uid/gid in the dest, this test ignores
        setuid/setgid. See copy_metadata().

        This test is necessary, but weak.
        """

        from_stat = os.lstat(self.from_path)
        to_stat = os.lstat(self.to_path)

        if from_stat.st_mode & UID_GID_MASK:
            warn(f"setuid/setgid bit set on {self.from_path}")
            # mask out uid/gid in source
            # so we don't set uid/gid in dest
            from_mode = from_stat.st_mode & ~UID_GID_MASK
            to_mode = to_stat.st_mode & ~UID_GID_MASK
        else:
            from_mode = from_stat.st_mode
            to_mode = to_stat.st_mode

        equal = from_mode == to_mode
        if not equal:
            log_message(
                f"unequal because permissions are different: {self.shared_path}"
            )

        return equal

    def modified_times_equal(self):
        """Test that modified times are equal.

        Because safecopy sets the dest stats from the source after copying,
        comparing times is a good quick test. If the file is the same
        size and the last-modified time is the same, the files are very
        likely equal. But this test can fail if an attacker has reduced
        the size of a file by the length of their embedded malware,
        then restored the file times.
        """

        from_stats = os.lstat(self.from_path)
        to_stats = os.lstat(self.to_path)
        equal = from_stats.st_mtime == to_stats.st_mtime
        if not equal:
            log_message(
                f"unequal because modified times are different: {self.shared_path}"
            )
            # log_message(f'{from_stats.st_mtime} is not {to_stats.st_mtime}')

        return equal

    def byte_for_byte_equal(self):
        """Compare byte by byte. If one doesn't match, stop.

        This comparison is as safe as it gets.

        filecmp.cmp() is smart about buffers, etc.
        """

        if os.path.isfile(self.from_path) and not os.path.islink(self.from_path):
            if os.path.exists(self.to_path):
                equal_bytes = self.count_equal_bytes()
                equal = (equal_bytes == os.path.getsize(self.from_path)) and (
                    equal_bytes == os.path.getsize(self.to_path)
                )
                if equal:
                    log_message("files are byte-for-byte equal; metadata unknown")
                    # equal = filecmp.cmp(self.from_path, self.to_path, shallow=False)

                else:
                    log_message(
                        f"unequal because bytes not equal: from size {os.path.getsize(self.from_path)}"
                    )
                    log_message(
                        f"                                   to size {os.path.getsize(self.to_path)}"
                    )

            else:
                equal = False
                log_message(
                    f"byte for byte not equal because {self.to_path} does not exist"
                )

        else:
            # no bytes to compare for links or dirs, so all bytes are equal
            equal = True

        return equal

    def metadata_equal(self):
        """
        Just compare metadata, not byte-for-byte.
        """

        # Cheap comparisons first. Shortcut compare when we can. If unequal, log why.

        if os.path.exists(self.to_path):
            # double check our metadata compare
            # filecmp.cmp(self.from_path, self.to_path, shallow=True)

            equal = (
                self.both_exist()
                and self.types_equal()
                and self.sizes_equal()
                and self.permissions_equal()
                and self.modified_times_equal()
            )
            if not equal:
                log_message(f"{self.from_path} not equal to {self.to_path}")
        else:
            equal = False
            log_message(f"unequal because path does not exist: {self.to_path}")

        return equal

    def sizes_equal(self, from_path=None, to_path=None):
        """Test that file sizes are equal.

        This test can fail if an attacker has reduced the size of a file
        by the length of their embedded malware.
        """

        if from_path is None:
            from_path = self.from_path
        if to_path is None:
            to_path = self.to_path

        if os.path.isdir(self.from_path) or os.path.islink(self.from_path):
            # no meaningful size
            equal = True

        elif not os.path.exists(self.to_path):
            equal = False

        else:
            from_size = os.path.getsize(self.from_path)
            to_size = os.path.getsize(self.to_path)
            equal = from_size == to_size
            if not equal:
                log_message(
                    f"unequal because sizes not equal: {from_size} != {to_size}"
                )

        return equal

    def equal(self):
        """Return True if metadata is equal and files are byte-for-byte equal.

        '--quick' just checks metadata.
        """

        # Cheap comparisons first. Shortcut compare when we can. If unequal, log why.
        if args.quick:
            equal = self.metadata_equal()

        else:
            equal = self.metadata_equal() and self.byte_for_byte_equal()

        return equal

    def try_to_copy(self):
        """Try to copy from_path to to_path."""

        if os.path.islink(self.from_path):
            link_ok = False
            target = os.readlink(self.from_path)
            if os.path.exists(self.to_path) and os.path.islink(self.to_path):
                to_target = os.readlink(self.to_path)
                if target == to_target:
                    verbose_log(f"{self.to_path} already exists and matches")
                    link_ok = True
            if not link_ok:
                verbose_log(f"deleting bad link for {self.to_path}")
                delete(self.to_path)
                os.symlink(
                    target,
                    self.to_path,
                    target_is_directory=os.path.isdir(self.from_path),
                )
                verbose_log(f"linked from {self.to_path} to {target}")

        elif os.path.isfile(self.from_path):
            # if we start copying from equal bytes, we don't remove the to_path
            # delete(self.to_path)

            if self.byte_for_byte_equal():
                log_message("files are byte-for-byte equal; metadata unchecked")

            elif os.path.getsize(self.from_path) == 0:
                with open(self.to_path, "wb"):
                    log_message(f"created empty file {self.to_path} to match original")

            else:
                verbose(f"Copying {os.path.basename(self.from_path)} to {self.to_path}")
                try:
                    self.copy_bytes()
                except PermissionError:
                    warn(
                        f"trying cp because it sometimes handles network filesystem permissions better:\n    {self.from_path}"
                    )
                    run_verbose("cp", "--verbose", self.from_path, self.to_path)

        elif os.path.isdir(self.from_path):
            # to_path must be a dir
            if not os.path.isdir(self.to_path):
                delete(self.to_path)

            if not os.path.exists(self.to_path):
                log_message(f"makedirs {self.to_path}")
                os.makedirs(self.to_path)
                verbose(f"Created: {self.to_path}")

        # set to_path attrs from from_path
        self.copy_metadata(from_path=self.from_path, to_path=self.to_path)

    def copy_bytes(self):
        """Copy bytes from_path to to_path, skipping those that match."""

        def copy_remaining_bytes(from_file, to_file, buffer_size=None):
            if buffer_size:
                buf = from_file.read(buffer_size)
            else:
                buf = from_file.read()
            while buf:
                to_file.write(buf)
                if buffer_size:
                    buf = from_file.read(buffer_size)
                else:
                    buf = from_file.read()

                delay()

        log_message(COPYING_FILE.format(self.from_path, self.to_path))

        # open both files as random access
        # not using "with open()" so we can check permission cleanly
        try:
            from_file = open(self.from_path, "r+b")
        except PermissionError:
            raise PermissionError(
                f"{why_file_permission_denied(self.from_path, 'r+b')}: {self.from_path}"
            )

        # open the to_path for appending so that part
        # which matches the from_path will be kept and
        # we'll seek to the correct position before writing
        try:
            to_file = open(self.to_path, "a+b")
        except PermissionError:
            raise PermissionError(
                f"{why_file_permission_denied(self.to_path, 'a+b')}: {self.to_path}"
            )

        equal_bytes = self.count_equal_bytes()
        log_message(f"copy from byte {equal_bytes + 1}")
        # seek position is zero-based, so the count
        # of equal bytes is the seek position
        from_file.seek(equal_bytes)
        to_file.seek(equal_bytes)

        to_file.truncate(equal_bytes)

        buffer_size = BUFFER_1M
        copy_remaining_bytes(from_file, to_file, buffer_size=buffer_size)

        copy_remaining_bytes(from_file, to_file, buffer_size=buffer_size)

        from_file.close()
        to_file.close()

        verbose_log("copied bytes")

    def make_dirs_and_copy(self, from_root, to_root):
        """
        Make parent dirs and copy one directory entry
        from self.from_path to self.to_path.

        The dir entries to copy are in self.from_path and
        self.to_path. The params from_root and to_root are just
        so we can make and update dirs.
        """

        def make_parent_dirs(path):
            """Create parent dirs, outermost first.

            For rsync compatibility."""

            if path and path != os.sep:
                # log_message(f'make_parent_dirs(): {path}')

                # recurse early to make highest level dir first
                make_parent_dirs(os.path.dirname(path))

                if path not in changed_dirs:
                    # log_message(f'making parent dir: {path}')

                    changed_dirs.add(path)

                    from_dir = os.path.join(from_root, path)
                    to_dir = os.path.join(to_root, path)

                    if not os.path.exists(to_dir):
                        verbose(f"Creating: {path + os.sep}")
                        if not args.dryrun:
                            os.makedirs(to_dir)

        def copy_persistently():
            """Copy and retry as needed."""

            try:
                ok = False
                try:
                    self.try_to_copy()
                    ok = True
                except:
                    log.exception()
                    retries = args.retries
                    while retries:
                        log_message("retry copy path after error")
                        try:
                            self.try_to_copy()
                        except:
                            if retries:
                                log.exception_only()
                                retries = retries - 1
                        else:
                            ok = True
                            retries = 0

                        delay()

                    if not ok:
                        raise

                else:
                    if args.verify:
                        verify_copy(self.from_path, self.to_path, self.shared_path)

            except:
                if args.persist:
                    # log exception and continue
                    log.exception()
                    log_message("continue with next path after error")

                else:
                    raise

        path = os.path.dirname(self.shared_path)
        make_parent_dirs(path)
        if not args.dryrun:
            copy_persistently()

    def copy_metadata(self, from_path=None, to_path=None):
        """
        Copy metadata from from_path to to_path.

        >>> from shutil import copyfile, copytree, rmtree

        >>> # verify that we set the metadata on a file
        >>> from tempfile import gettempdir
        >>> from_path = os.path.abspath(__file__)
        >>> to_path = os.path.join(gettempdir(), os.path.basename(from_path))
        >>> from_root = os.path.dirname(from_path)
        >>> shared_path = from_path[len(from_root):].lstrip(os.sep)
        >>> if os.path.exists(to_path):
        ...     if os.path.isdir(to_path):
        ...         rmtree(to_path)
        ...     else:
        ...         os.remove(to_path)
        >>> __ = copyfile(from_path, to_path)
        >>> fc = FileCopier(from_path, to_path, shared_path)
        >>> fc.copy_metadata()
        >>> filecmp.cmp(from_path, to_path)
        True

        >>> from shutil import copyfile, copytree, rmtree
        >>> def verify_metadata_in_dir(fc, from_path, to_path):
        ...     entries = sorted(os.scandir(from_path), key=lambda k: k.name)
        ...     for entry in entries:
        ...         full_from = entry.path
        ...         full_to = os.path.join(to_path, entry.name)
        ...         log_message(f'comparing: {full_from} to {full_to}')
        ...         if not fc.metadata_equal():
        ...             log_message(f'from: {os.stat(full_from)}')
        ...             log_message(f'to {os.stat(full_to)}')
        ...         assert fc.metadata_equal() == True
        ...         if entry.is_dir():
        ...             fname = os.path.join(to_path, entry.name)
        ...             verify_metadata_in_dir(fc, entry.path, fname)

        >>> # verify that we set the metadata on a directory and all its components
        >>> from tempfile import gettempdir
        >>> from_path = os.path.abspath(os.path.dirname(__file__))
        >>> to_path = os.path.join(gettempdir(), os.path.basename(from_path))
        >>> from_root = os.path.dirname(from_path)
        >>> shared_path = from_path[len(from_root):].lstrip(os.sep)
        >>> if os.path.exists(to_path):
        ...     if os.path.isdir(to_path):
        ...         rmtree(to_path)
        ...     else:
        ...         os.remove(to_path)
        >>> __ = copytree(from_path, to_path)
        >>> fc = FileCopier(from_path, to_path, shared_path)
        >>> fc.copy_metadata()
        >>> verify_metadata_in_dir(fc, from_path, to_path)
        """

        if from_path != to_path:
            verbose_log(f"Copying metadata {os.path.basename(from_path)} to {to_path}")

            if from_path is None:
                from_path = self.from_path
            if to_path is None:
                to_path = self.to_path

            # links don't have normal stat, and the permissions are for the target path
            # or if the target does not exist, the permissions are 0o777 placeholders
            if os.path.islink(to_path):
                verbose_log(
                    "not changing link's metadata because it would change the source's metadata"
                )

            else:
                if os.path.isfile(from_path) and not os.path.islink(to_path):
                    if not self.sizes_equal(from_path=from_path, to_path=to_path):
                        msg = f"Cannot copy {from_path} metadata because file sizes are not equal"
                        error_exit(msg)

                from_stat = os.lstat(from_path)

                # Windows does not support os.chown
                system = platform.system()
                if system != "Windows":
                    ERR_MSG = f"Unable to chown to uid {from_stat.st_uid} or gid {from_stat.st_gid}: {to_path}"
                    try:
                        os.chown(to_path, from_stat.st_uid, from_stat.st_gid)
                    except PermissionError:
                        # uid/gid often don't match
                        # the point is to copy the file
                        warn(ERR_MSG)
                        log(ERR_MSG)
                    except OSError as ose:
                        warn(ERR_MSG)
                        log(ERR_MSG)
                        warn(ose)
                        log(ose)
                        raise
                    finally:
                        verbose_log(
                            f"Changed owner to {from_stat.st_uid}:{from_stat.st_gid}"
                        )

                if from_stat.st_mode & UID_GID_MASK:
                    warn(f"setuid/setgid bit set on {from_path}")
                    # mask out uid/gid in source
                    # so we don't set uid/gid in dest
                    mode = from_stat.st_mode & ~UID_GID_MASK
                else:
                    mode = from_stat.st_mode
                os.chmod(to_path, mode)
                verbose_log(f"Changed mode to {mode}")

                copystat(from_path, to_path, follow_symlinks=False)

                # earlier metadata updates apparently change last
                # modified/accessed times
                # shutil.copystat() does not seem to reliably
                # change mtime, so we do
                atime = os.path.getatime(from_path)
                mtime = os.path.getmtime(from_path)
                os.utime(to_path, (atime, mtime))

                os.utime(to_path, (mtime, mtime))
                verbose_log(f"Finished setting time")
