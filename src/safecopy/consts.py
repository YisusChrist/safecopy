import stat

DEBUG = True

CURRENT_VERSION = "1.3.2"
COPYRIGHT = "Copyright 2018-2023 solidlibs"
LICENSE = "GPLv3"

# do not change the format of the following line without updating blockchain-backup
COPYING_FILE = 'copying "{}" to "{}"'

UID_GID_MASK = stat.S_ISUID | stat.S_ISGID

BUFFER_1K = 1024
BUFFER_1M = BUFFER_1K * BUFFER_1K
