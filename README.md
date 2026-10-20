# zephyr-installer

Installs embedded C libraries into a Zephyr application, nRF Connect SDK ones included.

A library written for any project has no idea what a Zephyr module is. This copies it into your application, makes it a module, adds it to the build, and switches it on in `prj.conf`, so `west build` picks it up and its settings live in Kconfig like everything else in Zephyr.

It works with any library that has an `installer.yml` at the root of its repository. I wrote it for my own [NimaLTD](https://github.com/nimaltd) libraries, and they all have one, but nothing in it is tied to them: add an `installer.yml` to yours, as shown [below](#for-someone-writing-a-library), and it installs the same way. The same file serves [stm32-installer](https://github.com/nimaltd/stm32-installer), [esp32-installer](https://github.com/nimaltd/esp32-installer), [arduino-installer](https://github.com/nimaltd/arduino-installer) and [pio-installer](https://github.com/nimaltd/pio-installer), so one library can be installed into a Zephyr application, an STM32 project, an ESP-IDF project, an Arduino sketch and a PlatformIO project alike.

Every command below uses `owner/example`, the library's GitHub owner and name, such as `nimaltd/ee24`. Put the real ones in its place.

---

## Installing a library

Install the installer once. This needs internet:

```bash
pip install zephyr-installer
```

Then, from your application's folder, the one holding `CMakeLists.txt` and `prj.conf`, install a library by its GitHub owner and name. To see it work first, take [zephyr-installer-example](https://github.com/nimaltd/zephyr-installer-example), a library made for trying the installer on:

```bash
zephyr-installer nimaltd/zephyr-installer-example
```

It builds in any Zephyr application, `native_sim` included, with its settings in Kconfig. Its README walks through an install, a setting changed in `prj.conf`, an option, and an uninstall. Any other library goes in the same way, as `zephyr-installer owner/example`.

Then build as always:

```bash
west build -b nrf52840dk/nrf52840
```

To update it later, `pip install --upgrade zephyr-installer`. To remove it, `pip uninstall zephyr-installer`.

When a newer zephyr-installer is out, the last line of a run says so, with that command. It asks PyPI at most once a day, waits no more than two seconds for an answer, and says nothing when there is none. `--no-update-check` turns it off, and so does `INSTALLER_NO_UPDATE_CHECK` set to anything. On a build server, where `CI` is set, it is off already.

On Windows, if `zephyr-installer` is not found after installing, pip put it in a folder that is not on your PATH. `python -m zephyr_installer owner/example` runs the same thing.

### Every command

Each command with `owner/example` standing for the library. An update is the install again. Every option is explained under [Options](#options).

| To | Run |
|---|---|
| Install the installer | `pip install zephyr-installer` |
| Update the installer | `pip install --upgrade zephyr-installer` |
| Remove the installer | `pip uninstall zephyr-installer` |
| See which version you have | `zephyr-installer --version` |
| See every option | `zephyr-installer --help` |
| Install a library from GitHub | `zephyr-installer owner/example` |
| Install one release of it, a branch or a commit | `zephyr-installer owner/example@v2.0.0` |
| Install it by its GitHub address | `zephyr-installer https://github.com/owner/example` |
| Install it from a downloaded zip | `zephyr-installer D:/Downloads/example-main.zip` |
| Install it from a folder on disk | `zephyr-installer D:/Downloads/example-main` |
| Install several at once, such as a library and the zip of one it needs | `zephyr-installer D:/Downloads/example-main.zip D:/Downloads/osal-main.zip` |
| Install into a folder you choose, without the question | `zephyr-installer owner/example --dir libs/example` |
| Install into a application you are not running from | `zephyr-installer owner/example --project D:/work/app` |
| Choose the Kconfig file the libraries are switched on in | `zephyr-installer owner/example --conf boards/x.conf` |
| Take an option of the library without the question | `zephyr-installer owner/example --with littlefs` |
| Leave an option out, or take it out of a library already installed | `zephyr-installer owner/example --without littlefs` |
| Run a step of the library without the question | `zephyr-installer owner/example --run signing-key` |
| Leave a step unrun, without the question | `zephyr-installer owner/example --no-run signing-key` |
| Answer every question with the answer offered, and run every step, for a script | `zephyr-installer owner/example --yes` |
| Install from a private repository | `zephyr-installer owner/example --key github_pat_...` |
| Leave out the check for a newer installer | `zephyr-installer owner/example --no-update-check` |
| Update a library | `zephyr-installer owner/example` |
| Uninstall a library | `zephyr-installer --uninstall example` |
| Uninstall several, in any order | `zephyr-installer --uninstall osal example` |
| Run it when `zephyr-installer` is not found | `python -m zephyr_installer owner/example` |

### What happens

Take `example`, installed into an application called `app`:

```
app/
  CMakeLists.txt         one block added, above find_package(Zephyr)
  prj.conf               one block added, CONFIG_EXAMPLE=y and what it needs
  modules/example/
    src/example.h        the library's files, at the paths they have in its repository
    src/example.c
    zephyr/
      module.yml         written by the installer: the library as a Zephyr module
      CMakeLists.txt     its files, built when CONFIG_EXAMPLE is set
      Kconfig            CONFIG_EXAMPLE, the library's settings, and its defaults for others
```

The block in your `CMakeLists.txt` adds the library's folder to `ZEPHYR_EXTRA_MODULES`. That is how Zephyr is told about a module outside the west workspace, and it has to come before `find_package(Zephyr)`, which is when Zephyr looks:

```cmake
cmake_minimum_required(VERSION 3.20.0)
# >>> zephyr-installer: example >>>
# Added by zephyr-installer. Delete this block, and example's block in
# the Kconfig file, to drop the library from the build.
list(APPEND ZEPHYR_EXTRA_MODULES "${CMAKE_CURRENT_SOURCE_DIR}/modules/example")
# <<< zephyr-installer: example <<<

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
```

The block in `prj.conf` switches the library on, with the symbols it needs and a list of its settings:

```
# >>> zephyr-installer: example >>>
# Added by zephyr-installer, and written again on every install, so set
# example's settings below this block rather than in it.
# Its settings, as they are unless you set them:
#   CONFIG_EXAMPLE_POLL_CHUNK=32
CONFIG_I2C=y
CONFIG_EXAMPLE=y
# <<< zephyr-installer: example <<<
```

A symbol you already set yourself, on or off, is not set again: in Kconfig the line read last wins, and it would quietly undo your choice. It is still written in the block, commented out, with the line that set it, so the block shows everything the library asked for:

```
CONFIG_EXAMPLE=y
# CONFIG_I2C=y  (left out: prj.conf sets CONFIG_I2C=n)
```

And the installer warns about each one before it writes anything:

```
Requirements
  check   prj.conf sets CONFIG_I2C=n, and example needs y. The block has it commented out
          Your line is the one used. Change it if the library is to work.
```

Change your line, or delete it and install again, and the block sets it.

A library can need more than these two blocks, and then it says so in its `installer.yml`:

- **Sysbuild settings**, such as MCUboot switched on, go into a block of their own in `sysbuild.conf`, made when the application has none, with the same rules as the block in `prj.conf`. A library without them never touches `sysbuild.conf`.
- **Lines of CMake** it needs in your `CMakeLists.txt` go above `find_package(Zephyr)` or at the end of the file, wherever the library says, each place between two lines that name it:

```cmake
# >>> zephyr-installer: example/before-zephyr >>>
# From example's installer.yml, and written again on every install.
list(APPEND EXTRA_CONF_FILE "${CMAKE_CURRENT_SOURCE_DIR}/example.conf")
# <<< zephyr-installer: example/before-zephyr <<<
```

- **Defaults for other symbols**, such as Bluetooth switched on, go into the library's own Kconfig rather than your `prj.conf`: they hold while the library is on, and a line of yours that sets the same symbol wins.

Every block is written again on every install, so put your own lines outside them. An edit made inside one is noticed on the next install, and the file as it was is in the `.bak`.

Both files are copied aside before they change, as `CMakeLists.txt.20261013-170013.bak` and the like, and the files keep their own line endings. Installing twice changes nothing the second time.

The module is called `example_lib`, not `example`. Zephyr keeps one module per name, and one added by the application quietly takes the place of a module of the same name in the workspace: a library called `littlefs` would otherwise replace Zephyr's own littlefs.

### Settings

A library's settings are Kconfig symbols, set in `prj.conf` like any other, below the installer's block:

```
CONFIG_EXAMPLE_POLL_CHUNK=64
```

`west build -t menuconfig` shows them too, under the library's name. The C code reads them as `CONFIG_EXAMPLE_POLL_CHUNK`, which Zephyr gives every file of the build.

### Which Kconfig file

`prj.conf` is the one most applications have. When yours has more, such as a board's own file in `boards/`, the installer asks once which one gets the libraries:

```
This application has more than one Kconfig file: prj.conf, boards/nrf52840dk_nrf52840.conf
Kconfig file for the libraries [prj.conf]:
```

Press Enter for `prj.conf`. `--conf boards/nrf52840dk_nrf52840.conf` answers it on the command line, and a file that does not exist yet is created. One answer covers every library of that run, a library it needs included. On an update, a library stays in the file that already has its block, without a question. In a script, where nobody can answer, `prj.conf` is taken.

`sysbuild.conf` is never one of the choices. It holds sysbuild's settings, not the application's, so the installer neither asks about it nor reads it as one, and `--conf sysbuild.conf` is refused.

### Files that become yours

A library can bring files that belong to your application rather than to the library: a `VERSION`, a `CHANGELOG.md`, an overlay in `socs/` for each chip. Each is a start, made for you to change, so it is created in your application's folder only when it is not there:

```
Files
  written modules/example/src/example.h
  created VERSION  yours from now on
  created socs/nrf54l15_cpuapp.overlay  yours from now on
```

From then on it is yours. An update never writes over it, and says so with `kept VERSION  yours`. An uninstall leaves it where it is, with `kept VERSION  yours, not removed`. A library can never put such a file over one the installer manages, such as `CMakeLists.txt` or `prj.conf`, nor outside your application's folder.

### Steps a library runs

A library can need something made that no file can carry, such as the key its images are signed with, made fresh for each product. It names a step for that, and once its files are in, the installer shows you exactly what will run, and asks:

```
Run
  signing-key  Make MCUboot's signing key, sign_key.pem
               python tools/make_key.py sign_key.pem
               Run it? [Y/n]:
```

Enter runs it, in your application's folder. A Python script runs with the same Python as the installer, so it works the same on every computer. `n` leaves it, and the output says how to run it later. In a script, where nobody can answer, it is not run.

Nothing in a library's `installer.yml` can skip the question. Only you can: `--run signing-key` runs that step without asking, `--no-run signing-key` leaves it, and `--yes` runs every step and takes the offered answer to every other question, for a script or a build server.

A step that makes a file can name it, and when that file is already in your application the step is skipped without a question, so a second install never makes a second key. A step that names no file and ran before is not asked about again either, until the library changes what it runs. When a step fails, what was installed stays installed, and the installer ends with exit code 1, so a script notices.

### What you see

A first install from GitHub, into an application whose `prj.conf` turned printk off:

```
Fetching owner/example ...

example 1.2.0
Driver for the X chip
driver / storage

Requirements
  note    CONFIG_I2C=y goes into prj.conf
  check   prj.conf sets CONFIG_PRINTK=n, and example needs y
          Your line is kept. Change it if the library is to work.
  note    Needs I2C, 400 kHz
          Enable it in your board's devicetree, or in an overlay of the application.

Folder to install example into [modules/example]:

Files
  written modules/example/src/example.h
  written modules/example/src/example.c

Project
  updated Zephyr module  Wrote example_lib: zephyr/module.yml, zephyr/CMakeLists.txt, zephyr/Kconfig.
  updated CMakeLists.txt  Added example to CMakeLists.txt.
          backup: CMakeLists.txt.20261013-170013.bak
  updated prj.conf  Added example to prj.conf.
          backup: prj.conf.20261013-170014.bak

Done. #include "example.h" and you are away.
```

The hardware a library uses is yours to give it in the devicetree, which the installer names but does not change.

### What to install

The argument can be any of these, and you can give several at once:

| You have | You type |
|---|---|
| Nothing yet, and internet | `zephyr-installer owner/example` |
| One release of it, a branch, or a commit | `zephyr-installer owner/example@v2.0.0` |
| The library's GitHub address | `zephyr-installer https://github.com/owner/example` |
| The zip from GitHub's **Download ZIP** | `zephyr-installer D:/Downloads/example-main.zip` |
| That zip unpacked, anywhere on disk | `zephyr-installer D:/Downloads/example-main` |
| The library's folder, already inside your application | `zephyr-installer modules/example` |

A bare name with no owner, like `example`, is a NimaLTD library, `nimaltd/example` on GitHub, unless a folder of that name exists where you run it, in which case the folder is used. A path that does not exist is reported as missing rather than looked up on GitHub.

From GitHub, a library comes from its repository's default branch, the one GitHub shows first, whatever the repository calls it. After an `@`, a tag, a branch or a commit takes exactly that instead, and so does a GitHub address ending in `/tree/v2.0.0`. Every file comes from one commit, even when the branch moves on while they download, and the record keeps that commit, so you can always tell what you built with.

### Options

| Option | What it does |
|---|---|
| `--conf boards/x.conf` | The Kconfig file that switches the libraries on. Asked when the application has more than one, `prj.conf` otherwise. See [Which Kconfig file](#which-kconfig-file) |
| `--dir libs/example` | The folder of your application to install into, for one library. Asked for when not given, with `modules/<name>` as the answer if you just press Enter, or the folder it is already in |
| `--project D:/work/app` | Your application's folder, when you are not running from it |
| `--ref v2.0.0` | A tag, a branch or a commit to take from GitHub, the same as `owner/example@v2.0.0`. When not given, the repository's default branch |
| `--key github_pat_...` | A GitHub token, for a library in a private repository. See [A private repository](#a-private-repository) |
| `--uninstall example` | Take the library out of the application. See [Uninstalling a library](#uninstalling-a-library) |
| `--with littlefs` | Take this part of the library without being asked. Give it once for each part |
| `--without littlefs` | Leave this part out, or take it out of a library already installed |
| `--run signing-key` | Run this step of the library without being asked. Give it once for each step. See [Steps a library runs](#steps-a-library-runs) |
| `--no-run signing-key` | Leave this step unrun, without being asked |
| `--yes` | Take the answer each question offers, without asking, and run every step. For a script or a build server |
| `--no-update-check` | Do not ask PyPI whether a newer zephyr-installer is out |
| `--version` | Show which version of the installer you have, and do nothing else |

### Updating a library

Run the same command again. Every file of the library is replaced, so an update updates, and the module's three files are written again from the new `installer.yml`, so a source file the new version adds is built without you editing anything. A file that did not change is left alone, so the build does not configure again for nothing.

What you wrote between `USER CODE BEGIN` and `USER CODE END` in a library's file is kept. Outside those lines, the next install replaces it, and when that would lose something of yours the file is saved beside it first, as a `.bak`.

The record of what is installed, and where, is `.zephyr-installer.json` in your application's folder. For each library it also keeps where it came from, down to the commit, the blocks written into your files, and the steps that ran. Keep it in version control with the rest.

### Uninstalling a library

```bash
zephyr-installer --uninstall example
```

From your application's folder, or with `--project`. Its blocks go from `CMakeLists.txt`, from the Kconfig file that has its block and from `sysbuild.conf`, the module files the installer wrote go from its folder, and then the library's own files. Installed and then uninstalled, `CMakeLists.txt` and `prj.conf` are back to the byte they were. `sysbuild.conf` stays, even when the block was all it held, and so do the [files that became yours](#files-that-become-yours).

What was yours is saved before it goes, as a `.bak` beside it: any file of the library you wrote in between its `USER CODE` lines or changed by hand. A file you put in the library's folder yourself is left where it is, and the folder with it.

A setting you set yourself, below the installer's block, is your line, and it stays. The symbol it sets went with the library, though, and Zephyr stops on a symbol it does not know, so the installer names every such line:

```
  manual  prj.conf  prj.conf still sets what came with example, and Zephyr stops on a symbol it does not know. Take these lines out:
          CONFIG_EXAMPLE_POLL_CHUNK=64
```

A library another one needs stays, and the installer says which needs it. Name them all, in any order, and each goes after what needs it: `zephyr-installer --uninstall osal ee24`. When the library you took out brought another with it that nothing left needs, the last line names it, with the command that takes it out too. Uninstall works from `.zephyr-installer.json`, the record of what was installed and where.

### A library that needs another

You install only the one you want, and what it needs goes in first, each as a module of its own with its own blocks. It comes from the release the library names for it, or else from its default branch. One already in the application at a version that will do is left alone. Everything is fetched before anything is installed, so when a library cannot be had, your application is left as it was.

### Without internet

On a machine that has internet, `pip download zephyr-installer` saves one file, the installer, which needs nothing else. Download the library too, from the green **Code** button, **Download ZIP**. Then, on the machine with no internet:

```bash
pip install zephyr_installer-1.0.0-py3-none-any.whl
zephyr-installer D:/Downloads/example-main.zip
```

If the library needs another, give that zip on the same line. Behind a proxy, set `HTTPS_PROXY` to its address.

### A private repository

A library in a private repository installs the same way, given a GitHub token that can read it. Make one once:

1. Open [github.com/settings/personal-access-tokens](https://github.com/settings/personal-access-tokens) and click **Generate new token**.
2. Give it a name and an expiry. Under **Resource owner**, pick the account or the organisation that owns the repository.
3. Under **Repository access**, choose **Only select repositories** and pick the library's repository.
4. Under **Permissions**, set **Contents** to **Read-only**:
   - Older layout: open **Repository permissions** and change **Contents** from **No access** to **Read-only**.
   - Newer layout: click **+ Add permissions**, tick **Contents**, then set its access to **Read-only**.

   **Metadata** comes with it by itself. Contents is the one that matters: without it the token can see the repository but not read a file of it.
5. Click **Generate token**, and copy it. GitHub shows it only once.

Then give it with `--key`:

```bash
zephyr-installer owner/example --key github_pat_...
```

Or put it in `GITHUB_TOKEN` once, and install by name as usual. That keeps it out of your shell's history, where `--key` leaves it:

**Windows, PowerShell:**

```powershell
$env:GITHUB_TOKEN = "github_pat_..."
zephyr-installer owner/example
```

**Windows, Command Prompt:**

```bat
set GITHUB_TOKEN=github_pat_...
zephyr-installer owner/example
```

**Linux and macOS:**

```bash
export GITHUB_TOKEN=github_pat_...
zephyr-installer owner/example
```

`--key` comes first when both are there. `GH_TOKEN` works as well, and if you use the `gh` command, `gh auth token` prints the token you are signed in with. Whichever way it comes, the token is sent to GitHub and nowhere else.

When the token cannot read the library, the installer says which of these it is:

- **It can see the repository, but cannot read its files.** The token has no Contents permission, only Metadata. Edit the token, and its value stays the same, so the command you ran keeps working: open the tokens page, click the token's name, click **Edit**, set Contents to **Read-only** as in step 4, and click **Update** at the bottom of the page. Then run the same command again.
- **It cannot see the repository.** The repository is not in the token's Repository access. Edit the token as above and add it.
- **GitHub did not accept the token.** It has expired, been revoked, or was copied with a character missing. Make a new one.

A repository of an organisation can need one more step: an organisation that asks for fine-grained tokens to be approved shows the token nothing of its repositories until an owner of the organisation approves it, under its settings, **Personal access tokens**, **Pending requests**.

---

## For someone writing a library

Put an `installer.yml` at the root of the repository. Any library can have one, whoever wrote it, and the one file serves zephyr-installer and the other installers alike: each reads its own keys and leaves the others' alone.

Every key zephyr-installer reads is below, each with what it does, as a manifest asking for 2.1.0 writes it. Only `name` and its `headers` or `sources` are required; leave out what your library does not need. For a working one to copy, see [zephyr-installer-example](https://github.com/nimaltd/zephyr-installer-example). What changed in 2.1.0, and how a manifest from before reads, is under [Paths, from 2.1.0](#paths-from-210).

```yaml
name: example                      # the library's name, its folder and its Kconfig symbol
description: Driver for the X chip # one line, shown while installing and in menuconfig
repository: https://github.com/owner/example  # where it comes from
license: Apache-2.0                # the licence's SPDX name
version: 1.0.0                     # only when the first header has no @version tag

kind: driver                       # driver, middleware, rtos, protocol, filesystem,
                                   # utility or bsp
category: storage                  # sensor, storage, display, communication, wireless,
                                   # rtos, timing, power, input, math or system
provides: []                       # what it gives other libraries: [rtos] for an RTOS

requires:
  zephyr_installer: 2.1.0          # the oldest zephyr-installer that reads this file
  libraries:                       # other libraries, installed first when missing
    - osal >= 1.0.0                # no owner means nimaltd; >= the oldest that will do
    - owner/lib                    # anyone else's, as owner/name
    - owner/lib@v1.2.0             # a tag, branch or commit, not its default branch
    - source: owner/other@v2.9.3   # a repository with no installer.yml of its own,
      manifest: manifests/other.yml  # with one this library carries for it
      minimum: 2.9.0               # the oldest version that will do
  kconfig:                         # symbols it needs, set in the Kconfig file
    - I2C                          # a symbol alone is set to y
    - MAIN_STACK_SIZE=2048         # or SYMBOL=value: y, n, a number, 0x.. or "text"
  peripherals:                     # hardware it uses, named to the user
    - type: i2c                    # what it is
      count: 1                     # how many
      note: 400 kHz                # how to set it up

install:
  include_dirs: [src]              # include folders, only when the guess is wrong
  defines:                         # given to the whole build, NAME or NAME=value
    - EXAMPLE_FAST

headers:                           # .h files; the first is the one to #include
  - src/example.h                  # every file keeps its path: modules/example/src/example.h
  - src/port/*.h                   # a wildcard, matched the way a shell would:
                                   # * inside one folder, ** across any number of them
sources:                           # .c files, built when the library is switched on
  - src/example.c
  - from: src/port/spi.c           # a file that goes somewhere of its own,
    to: port/spi.c                 # in the library's folder

options:                           # parts the user chooses at install
  littlefs:                        # the name typed after --with
    description: LittleFS file system on the flash  # the question asked
    libraries:                     # libraries this part needs, installed first
      - littlefs >= 2.11.0
    sources:                       # its files, written like headers and sources above
      - src/example_lfs.c

extras:                            # copied as they are, never compiled
  - LICENSE.md                     # LICENSE.md and NOTICE are the default,
  - NOTICE                         # so leave this out if that is all
  - README.md                      # in the library's folder: modules/example/README.md
  - root: tools                    # 2.1.0: tools/ into the application's folder instead,
                                   # as the library's own, written again on every install

once:                              # the application's own files: made when missing,
                                   # then the user's, never replaced or removed
  - VERSION                        # 2.1.0: a path alone lands at that path: VERSION
  - from: boards/nrf54l15.overlay  # to: another place in the application
    to: socs/nrf54l15_cpuapp.overlay

run:                               # steps run once the files are in, each asked about first
  - label: signing-key             # the name typed after --run
    description: Make the signing key, sign_key.pem  # shown with the question
    script: tools/make_key.py      # Python, run with the installer's own Python, from the
                                   # application's folder, or {library}/... in the library's
    args: [sign_key.pem]           # or command: [program, arguments], with no shell
    unless: sign_key.pem           # skipped when this file is in the application already

zephyr:                            # read by zephyr-installer only
  kconfig: EXAMPLE                 # the library's symbol; the name in capitals when left out
  defaults:                        # 2.1.0: settings of other symbols, held while the library
    - BT                           # is on; prj.conf can change any. A symbol alone is y,
    - BT_L2CAP_TX_MTU=498          # or SYMBOL=value, written as under requires.kconfig
  cmake:                           # lines of CMake, under the place they go:
    module:                        # the module's CMakeLists.txt, in if(CONFIG_EXAMPLE)
      - zephyr_library_link_libraries(mbedTLS)
    before-zephyr:                 # the application's, above find_package(Zephyr)
      - list(APPEND EXTRA_DTC_OVERLAY_FILE "{library}/dts/example.overlay")
    after-zephyr: []               # the application's, at its end
  sysbuild:                        # sysbuild settings, a block in sysbuild.conf
    - BOOTLOADER_MCUBOOT           # a symbol alone is set to y, without SB_CONFIG_
    - BOOT_SIGNATURE_KEY_FILE="${APP_DIR}/sign_key.pem"  # or SYMBOL=value
  settings:                        # Kconfig symbols the user sets, CONFIG_<name> in the code
    - name: EXAMPLE_POLL_CHUNK     # the symbol, best started with the library's own
      type: int                    # bool, int, hex or string
      default: 32                  # required: true or false, a number, 0x.. or text
      range: [1, 32768]            # int and hex only: [smallest, largest]
      prompt: Bytes read per call  # one line, shown in menuconfig
      help: |                      # as many lines as it takes, shown in menuconfig
        A read by polling moves at most this many bytes per call.
```

Keys only the other installers read, such as `requires.stm32_installer`, `requires.hal_modules` and `esp32`, can stay in the same file. This installer skips them.

Leave `version` out. The installer reads the version from the `@version` tag in the file comment of the first header listed, so it is written in the code and nowhere else.

`requires.zephyr_installer` is the oldest zephyr-installer that reads the file correctly. It is checked before anything else in the file is read, so an older installer stops with a message saying to update, rather than read the file wrongly. Write it as three numbers, `1.0.0`: unquoted, YAML reads `1.10` as the decimal number `1.1`, and that is refused.

A library that uses anything 2.0.0 brings says `requires.zephyr_installer: 2.0.0`: `once` files in the application's folder, `run`, groups under `zephyr.cmake`, `zephyr.sysbuild`, or a library it needs given with an `@` or a `manifest`. The version also decides where `once` files go. A manifest asking for 2.0.0 or newer puts them in the application's folder, and one asking for less keeps the meaning it was written for, the library's own folder, so a release tagged before 2.0.0 still installs and builds as it did.

### Paths, from 2.1.0

A manifest asking for `requires.zephyr_installer: 2.1.0` has one rule for every path that names a place in the application: it starts at the application's folder, the one holding `CMakeLists.txt`. `{library}` at its start names the library's own folder instead, wherever `--dir` put it. A path that names a file of the library, under `headers`, `sources`, `extras` or `once`, or as a `from`, is a path in the repository, as always.

And every file is copied to the path it has, unchanged, unless a `to` says otherwise, so a path alone is all an entry needs. `src/example.c` lands at `modules/example/src/example.c`, so `install.layout` is gone: `flat` is refused, `mirror` says nothing new. A `once` file lands at its own path in the application: `- sysbuild/mcuboot.conf` at `sysbuild/mcuboot.conf`, where before 2.1.0 it was written `- from: sysbuild/mcuboot.conf` and took only its name. And `headers` and `sources` need no `files` around them; `files` still reads, but not both at once.

A `to` gives a file another place, where its list puts files. Under `headers`, `sources` and `extras` that is the library's folder, so `- from: src/example.h, to: example.h` lands at `modules/example/example.h`, and the include path follows it. Under `once` it is the application's folder, where every `once` file lands. A `root` puts an extra in the application's folder instead of the library's: `- root: tools` takes the library's `tools/` to the application's `tools/`. Code has no `root`, since it is built in the library's folder, and a `once` file needs none. Wherever a `from` would be the same path as its `to` or `root`, leave it out: `- root: tools` is `- from: tools, root: tools`.

And `zephyr.cmake` gives its lines under the places they go, with no `label`, `where` or `lines`: see [More CMake for a library](#more-cmake-for-a-library).

| Key | Starts at |
|---|---|
| `headers`, `sources`, `extras`, `once`, `from` | the library's repository |
| `to` under `headers`, `sources` and `extras` | the library's folder |
| `once.to`, `extras.root` | the application's folder |
| `run.script`, `run.unless` | the application's folder, or the library's with `{library}/` |
| `{library}` in `run.args` and `run.command` | the library's folder, as the step names it from the application's |
| `{library}` in `zephyr.cmake` lines | `${CMAKE_CURRENT_SOURCE_DIR}/<the library's folder>` in the application's `CMakeLists.txt`, `${ZEPHYR_CURRENT_MODULE_DIR}` in the module's |

An extra with a `root` lands in the application's folder, as the library's own. A file lands at `root` itself, the files of a folder keep their path below it, and those a wildcard matches keep their names under it; an extra's `to` places them the same way in the library's folder. It is written again on every install, as every extra is, a file of it the new version no longer ships is removed, and an uninstall takes it out. A file already there that the installer did not put there is yours, and is never written over: the install stops and says so.

A wildcard matches the whole path, the way a shell does, and the same whether the library comes from GitHub or a folder: `*` and `?` stay inside one folder, `**` crosses any number of them, none included, and `[ab]` is one of a set. So `*.c` is the `.c` files at the top, `src/*.c` those in `src`, and `src/**/*.c` every one below `src`, however deep. Two files of the code that would land in one place, such as two `util.c` that `flat` put side by side, are refused when the manifest is read, where the second used to replace the first without a word.

```yaml
extras:
  - root: tools                    # tools/keygen.py and tools/keygen.md, beside CMakeLists.txt
run:
  - label: signing-key
    script: tools/keygen.py        # the application's tools/keygen.py
    unless: sign_key.pem
zephyr:
  cmake:
    before-zephyr:
      - list(APPEND EXTRA_DTC_OVERLAY_FILE "{library}/dts/example.overlay")
```

A step's script has to be one the install puts in place, an extra with a `root` or a `once` file, or with `{library}`, a file of the library's folder. Anything else is refused when the manifest is read, since it would not be there to run. A manifest asking for less than 2.1.0 keeps the meaning it was written for: its script is found in the library as it was fetched, and `{library}` is left as it is written.

### Settings of other symbols, from 2.1.0

A library that needs Bluetooth, MCUmgr or anything else of Zephyr switched on, or set to a value of its own, lists those settings under `zephyr.defaults`, written as under `requires.kconfig`: a symbol alone is set to `y`, or `SYMBOL=value`:

```yaml
requires:
  zephyr_installer: 2.1.0
zephyr:
  kconfig: GCORE
  defaults:
    - BT
    - BT_PERIPHERAL
    - BT_L2CAP_TX_MTU=498
    - BT_DEVICE_NAME="gcore"
    - BT_CTLR_LE_PING=n
```

The installer writes each into the library's Kconfig as a `configdefault`, inside `if GCORE`, and the application's `prj.conf` gets only `CONFIG_GCORE=y`:

```
if GCORE

configdefault BT
	default y

configdefault BT_L2CAP_TX_MTU
	default 498
...
endif # GCORE
```

So the settings hold while the library is switched on, and only then. A line of the application's own that sets one of them wins: `CONFIG_BT_L2CAP_TX_MTU=247` in `prj.conf` is the value used, and the install says so. A setting whose dependencies are not met stays off, without a warning. The library's Kconfig is read before Zephyr's subsystems, so its defaults come before theirs, and win over them; only a board's or a SoC's `Kconfig.defconfig`, read earlier still, can come before it.

A value is `y`, `n`, a number, `0x` and a hex number, or `"text"` with no quote or backslash in it. A symbol given twice, one also under `requires.kconfig`, or the library's own switch, is refused when the manifest is read. A symbol this Zephyr does not define stops the build, as it would in a `prj.conf`. A choice, such as which of several backends is used, cannot be set this way: it goes under `requires.kconfig`, into the application's Kconfig file.

`requires.kconfig` and `zephyr.defaults` differ in where the line goes. `requires.kconfig` writes it into the application's Kconfig file, for the user to see and keep; `zephyr.defaults` keeps it in the library, as a default. A Kconfig fragment given with `EXTRA_CONF_FILE` would be neither: it is read after `prj.conf`, so it would win over the application's own lines, and it would hold with the library switched off.

### More CMake for a library

A library that needs more than its files and its defines, a library of Zephyr's linked in, an option for its compiler, or a line in the application's own `CMakeLists.txt`, lists the lines under `zephyr.cmake`, under the place each goes:

```yaml
zephyr:
  cmake:
    module:
      - zephyr_library_link_libraries(mbedTLS)
      - zephyr_library_compile_options(-O2)
    before-zephyr:
      - list(APPEND EXTRA_DTC_OVERLAY_FILE "{library}/dts/example.overlay")
    after-zephyr:
      - 'message(STATUS "example: built for ${BOARD}")'
```

| Place | Written into | For |
|---|---|---|
| `module` | the module's `zephyr/CMakeLists.txt`, inside `if(CONFIG_EXAMPLE)`, after the library's files | `zephyr_library_...` calls on the library itself, counted only while it is switched on |
| `before-zephyr` | the application's `CMakeLists.txt`, above `find_package(Zephyr)`, below the library's `ZEPHYR_EXTRA_MODULES` block | what Zephyr reads as it starts: `EXTRA_CONF_FILE`, `EXTRA_DTC_OVERLAY_FILE`, `SNIPPET`. No `CONFIG_` value exists yet |
| `after-zephyr` | the application's `CMakeLists.txt`, at its end | what needs the application's own targets, such as `app` |

The lines of each place are written as one block, between two lines that name the library and the place, `# >>> zephyr-installer: example/before-zephyr >>>` and its pair, in the manifest's order:

```cmake
# >>> zephyr-installer: example/before-zephyr >>>
# From example's installer.yml, and written again on every install.
list(APPEND EXTRA_DTC_OVERLAY_FILE "${CMAKE_CURRENT_SOURCE_DIR}/modules/example/dts/example.overlay")
# <<< zephyr-installer: example/before-zephyr <<<
```

Every install writes them again: a place whose lines changed is updated, and one the manifest no longer has is taken out. A line keeps the spaces it starts with, so the body of an `if()` can be indented. `{library}` in a line names the library's folder, as `${CMAKE_CURRENT_SOURCE_DIR}/modules/example` in the application's file and `${ZEPHYR_CURRENT_MODULE_DIR}` in the module's, wherever `--dir` put it; anything else in a line is CMake's own, written as it stands. A line holding a colon, as `message()` often does, goes in quotes, or YAML reads it as a mapping.

An option brings lines of its own under `options.<name>.zephyr.cmake`, the same way, written while it is chosen and taken out by the update that turns it off. Its blocks are named after it and the place, `example/littlefs-module`, so they never meet the library's.

`zephyr_library_...` commands act on the library's own files only. A library of headers alone has no library of its own, so it uses the `zephyr_...` ones, which act on the whole build. The lines run when the user configures the build, the same as a module the library ships itself would, so they are the library's to answer for.

The forms from before 2.1.0 still install. A list of groups, each with a `label`, a `where`, `module` when left out, and its `lines`, writes each group as a block named after its label, `example/<label>`; a manifest moving to places has its old blocks taken out on the next install, and the new ones written. The form from before 2.0.0, a plain list of lines, is one group in `module`, written as it always was.

The user has a place in the module's file too. Its last lines are a `USER CODE` section, empty to start with, and every install keeps what is written in it, the way a configuration header keeps settings:

```cmake
  # USER CODE BEGIN EXAMPLE_CMAKE
  zephyr_library_compile_definitions(EXAMPLE_DEBUG=1)
  # USER CODE END EXAMPLE_CMAKE
endif()
```

On an uninstall, a section with something in it is saved as a `.bak` before the file goes.

### Sysbuild settings

MCUboot is an image of its own, built by sysbuild, and sysbuild does not see a module added through `ZEPHYR_EXTRA_MODULES`. So a library that needs it switched on lists the settings under `zephyr.sysbuild`, and they go into a block in the application's `sysbuild.conf`:

```yaml
zephyr:
  sysbuild:
    - BOOTLOADER_MCUBOOT
    - BOOT_SIGNATURE_TYPE_ECDSA_P256
    - BOOT_SIGNATURE_KEY_FILE="${APP_DIR}/sign_key.pem"
```

```
# >>> zephyr-installer: example >>>
# Added by zephyr-installer, and written again on every install, so set
# example's sysbuild settings below this block rather than in it.
SB_CONFIG_BOOTLOADER_MCUBOOT=y
SB_CONFIG_BOOT_SIGNATURE_TYPE_ECDSA_P256=y
SB_CONFIG_BOOT_SIGNATURE_KEY_FILE="${APP_DIR}/sign_key.pem"
# <<< zephyr-installer: example <<<
```

Each is read like `requires.kconfig`, written without `SB_CONFIG_`, which the installer adds. A value is written as given: sysbuild expands `${APP_DIR}` itself. The block follows the rules of the one in `prj.conf`: a symbol the user sets outside it is left commented out in it, an uninstall takes it out, and `sysbuild.conf` is made when the application has none.

### Files of the application's own

A file that belongs to the application rather than to the library goes under `once`: a `VERSION`, which Zephyr reads from the application's folder, a `CHANGELOG.md`, an overlay. It is created in the application's folder when it is missing, and is the user's from then on: never replaced by an update, never removed by an uninstall.

```yaml
once:
  - VERSION                            # lands at VERSION, its own path
  - sysbuild/mcuboot.conf              # lands at sysbuild/mcuboot.conf
  - from: templates/CHANGELOG.md
    to: CHANGELOG.md                   # a place of its own
  - from: boards/nrf54l15.overlay
    to: socs/nrf54l15_cpuapp.overlay   # a folder inside the application is fine
```

From 2.1.0 a path alone is a file of the library's repository, landing at the same path in the application, so a repository that keeps these files where the application keeps them needs nothing more. A file that goes somewhere else names it with `from`, the file in the repository, and `to`, its place from the application's folder. Before 2.1.0 each entry is a mapping with a `from`, and a `to` left out meant the file's name alone, at the top. A `once` file has no `root`: it always lands in the application's folder. Zephyr applies an overlay in the application's `socs/` folder to every board with that chip, so a library can bring one per chip this way.

Each is checked before anything is written. `to` stays inside the application, names none of the files the installer manages, `CMakeLists.txt`, the Kconfig file with the library's block, the record, and `sysbuild.conf` when the library has sysbuild settings, and does not point into the library's own folder, which every install replaces. Two entries with one `to` are refused. And `from`, like every file a manifest names, stays inside the library: no `..`, no absolute path, no link leading out of it.

What the user changes in their settings belongs in USER CODE sections of the library's own files, not in `once`, which is for files outside the library.

### Steps run after the install

Something no file can carry, such as a signing key made fresh for each product, is made by a step under `run`. It runs once the library's files are in, in the application's folder:

```yaml
extras:
  - root: tools                        # tools/make_key.py, beside CMakeLists.txt
run:
  - label: signing-key
    description: Make MCUboot's signing key, sign_key.pem
    script: tools/make_key.py          # the application's tools/make_key.py
    args: [sign_key.pem]
    unless: sign_key.pem
```

- `label` names the step, typed after `--run`, in lower case letters, digits, `_` and `-`.
- `description` is shown with the question.
- `script` is a Python file, run with the installer's own Python, so it works on every computer the installer does. From 2.1.0 it is a path from the application's folder, where an extra with a `root` or a `once` file put it, or `{library}/...` in the library's folder, see [Paths, from 2.1.0](#paths-from-210); before, it is a file of the library's repository. Or `command`, a program and its arguments as a list, `[imgtool, keygen, -k, sign_key.pem, -t, ecdsa-p256]`, run as it is, with no shell. One of the two, never both.
- `args` are added after either.
- `unless` names a file the step makes, from the application's folder. When it is there, the step is skipped without a question.

The step sees where things are in its environment: `INSTALLER_PROJECT`, the application's folder, `INSTALLER_LIBRARY`, the library's folder in it, `INSTALLER_NAME` and `INSTALLER_VERSION`, the library's, and `INSTALLER`, `zephyr-installer`.

The user is always asked, and is shown exactly what will run. Nothing in the manifest can turn that off, only the user, with `--run` or `--yes`. A step with no `unless` that ran before is not asked about again until what it runs changes, so make it safe to run twice anyway. A step that fails leaves the install as it is and ends the run with exit code 1.

### A library it needs

`requires.libraries` lists the libraries yours needs, each installed first when it is missing or older than the version given:

```yaml
requires:
  libraries:
    - osal >= 1.0.0                    # no owner means nimaltd: github.com/nimaltd/osal
    - someone/lib                      # anyone else's, by owner and name
    - someone/lib@v1.2.0               # exactly this tag, branch or commit
    - source: littlefs-project/littlefs@v2.11.0
      manifest: manifests/littlefs.yml # an installer.yml for a repository without one
      minimum: 2.11.0
```

Without an `@`, a library comes from its repository's default branch. The last form installs a library whose repository has no `installer.yml` of its own: yours carries one for it, at the path given, written as if it sat at the root of that repository.

### Settings in the code

Zephyr hands every file of the build its configuration, so the library's code reads a setting as a macro. One header can serve Zephyr and any other project, taking the setting from Kconfig when it is there:

```c
#ifdef CONFIG_EXAMPLE_POLL_CHUNK
#define EXAMPLE_POLL_CHUNK          CONFIG_EXAMPLE_POLL_CHUNK
#endif

#ifndef EXAMPLE_POLL_CHUNK
#define EXAMPLE_POLL_CHUNK          32U
#endif
```

A `bool` setting that is off is not defined at all, which is how Kconfig does it, so test it with `#ifdef` or `IS_ENABLED()`. A `string` arrives in quotes, ready for C.

Each setting is checked at install, since all of it is written into a Kconfig file: a default of the wrong type, one outside its range, or a name Kconfig would refuse stops the install with the reason, before anything is written.

### A library with its own module

A library that ships a `zephyr/module.yml` of its own, listed under `extras`, `headers` or `sources` so it is installed, knows its build better than the installer does. Its module is used as it is: nothing is written into its `zephyr` folder, and only the two blocks in the application are added. `zephyr.kconfig` then names the symbol its Kconfig defines, for the block in `prj.conf` to set.

---

## Running the tests

The shared core, [core-installer](https://github.com/nimaltd/core-installer), is a git submodule in `src/core`, so clone with it:

```bash
git clone --recursive https://github.com/nimaltd/zephyr-installer.git
```

In a clone made without `--recursive`, `git submodule update --init` fetches it. Then:

```bash
python test/run_tests.py
```

CI also installs two small libraries from `test/e2e/` into an application, one of them with everything 2.0.0 brings: files made once, groups of CMake lines in all three places, and a sysbuild setting. It builds the application with Zephyr for `native_sim`, runs it, checks what it prints, and then takes that library out again and checks nothing of it is left in the application's files. So every release is known to build with real Zephyr.

---

## Support

I write these tools and libraries in my own time and give them away, because good tools should be easy to get. If this one saved you an afternoon, there are two things that genuinely help:

**Star the repo.** It costs you one click, it helps other engineers find the tool, and it is the main reason I keep going.

**[Buy me a coffee on Ko-fi](https://ko-fi.com/nimaltd).** Any amount is a real motivation to keep writing, documenting and maintaining this work.

[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?style=for-the-badge&logo=github)](https://github.com/NimaLTD)
[![YouTube](https://img.shields.io/badge/YouTube-Subscribe-red?style=for-the-badge&logo=youtube)](https://youtube.com/@nimaltd)
[![Instagram](https://img.shields.io/badge/Instagram-Follow-purple?style=for-the-badge&logo=instagram)](https://instagram.com/github.nimaltd)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=for-the-badge&logo=linkedin)](https://linkedin.com/in/nimaltd)
[![Email](https://img.shields.io/badge/Email-Contact-red?style=for-the-badge&logo=gmail)](mailto:nima.askari@gmail.com)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-orange?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/nimaltd)

---

## License

Apache License 2.0. See [LICENSE](https://github.com/nimaltd/zephyr-installer/blob/main/LICENSE).
