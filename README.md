`Safecopy` synchronizes drives and directories very carefully. Like rsync, without rsync's insecure default metadata check. Securely copies to and from remote filesystems through sshfs.

Table of Contents

- [Description](#description)
- [Install](#install)
  - [From PyPi](#from-pypi)
  - [From Source](#from-source)
- [How it Works](#how-it-works)
- [License](#license)

# Description

Reliably Synchronize Drives and Directories

`Safecopy` synchronizes drives and directories, and carefully verifies the copy. When you are copying massive files or large directory trees, it's important to know that every file was copied accurately. `Safecopy` verifies byte-by-byte, or you can choose a quick metadata check.

# Install

## From PyPi

`Safecopy` is available on [PyPi](https://pypi.org/project/safecopy). You can install it with pip:

```sh
pip3 install safecopy
```

> For best practices and to avoid potential conflicts with your global Python environment, it is strongly recommended to install this program within a virtual environment. Avoid using the --user option for global installations. We highly recommend using [pipx](https://pypi.org/project/pipx/) for a safe and isolated installation experience. Therefore, the appropriate command to install `Safecopy` would be:
>
> ```sh
> pipx install safecopy
> ```

## From Source

You can also install `Safecopy` from source.

1. clone the repository:

   ```sh
   git clone https://github.com/YisusChrist/safecopy
   ```

2. Change to the `safecopy` directory.

   ```sh
   cd safecopy
   ```

3. Install it with poetry:

   ```sh
   poetry install --only main
   ```

# How it Works

```sh
safecopy SOURCE ... DESTINATION
```

It's just like the standard cp command. You can have as many source paths as you like. The destination path is always last.

`Safecopy` gives you a lot of control:

```
-h, --help Show this help message
--verbose Show progress
--quick Only update files if the size or last modified time is different
--dryrun Show what would be done, but don't do anything
--delete Delete all files that are not in the source before copying any files
--nowarn No warnings
--test Run tests
--exclude EXCLUDE_PATH... Exclude the files or directories (comma separated)
--verify Verify copies
--persist Continue on errors, except verify error
--retries RETRIES How many times to retry a failed copy. Default is not to retry
```

If you need the rsync protocol install the [pyrsync2](https://pypi.org/project/pyrsync2) library. But it's almost always better to replace rsync with `safecopy` and `sshfs`.

`Safecopy` detects when the `setuid/setgid` bit is set. This is almost always a serious security risk. To remove the bit:

```sh
chmod -s PATH
```

# License

`Safecopy` is released under the [GPL-3.0 license](https://opensource.org/licenses/GPL-3.0).
