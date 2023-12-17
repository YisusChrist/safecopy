import os
from src.safecopy.utils import verbose_log
from tempfile import mkstemp


try:
    from pyrsync2 import blockchecksums, patchstream, rsyncdelta
except ImportError:
    pass

def copy_rsync_delta(from_path, to_path):
    """Copy using pyrsync2 implementation of rsync delta-copy algo.

    Based on benchmarks, the delta-copy algo may be good for huge
    files with small changes on a slow network. For most cases today,
    a straight byte comparison and full copy is faster and more
    secure. Even rsync doesn't use delta-copy by default.
    """

    try:
        verbose_log("hash old file")
        unpatched = open(to_path, "rb")
        hashes = blockchecksums(unpatched)

        verbose_log("get changes")
        patchedfile = open(from_path, "rb")
        delta = rsyncdelta(patchedfile, hashes)

        verbose_log("apply changes")
        unpatched.seek(0)
        _, temp_path = mkstemp()
        save_to = open(temp_path, "wb")
        patchstream(unpatched, save_to, delta)

        save_to.close()
        unpatched.close()
        patchedfile.close()

        os.rename(unpatched, to_path)
    except ImportError:
        pass