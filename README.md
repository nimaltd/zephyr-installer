# zephyr-installer

Installs embedded C libraries into a Zephyr application, nRF Connect SDK ones included.

A library written for any project has no idea what a Zephyr module is. This copies it into your application, makes it a module, adds it to the build, and switches it on in `prj.conf`, so `west build` picks it up and its settings live in Kconfig like everything else in Zephyr.

It works with any library that has an `installer.yml` at the root of its repository. I wrote it for my own [NimaLTD](https://github.com/nimaltd) libraries, and they all have one, but nothing in it is tied to them: add an `installer.yml` to yours, as shown [below](#for-someone-writing-a-library), and it installs the same way. The same file serves [stm32-installer](https://github.com/nimaltd/stm32-installer), so one library can be installed into an STM32 project and a Zephyr application alike.

Every command below uses `owner/example`, the library's GitHub owner and name, such as `nimaltd/ee24`. Put the real ones in its place.

---

## Installing a library

Install the installer once. This needs internet:

```bash
pip install zephyr-installer
```

Then, from your application's folder, the one holding `CMakeLists.txt` and `prj.conf`:

```bash
zephyr-installer owner/example
```

Then build as always:

```bash
west build -b nrf52840dk/nrf52840
```

To update it later, `pip install --upgrade zephyr-installer`. To remove it, `pip uninstall zephyr-installer`.

On Windows, if `zephyr-installer` is not found after installing, pip put it in a folder that is not on your PATH. `python -m zephyr_installer owner/example` runs the same thing.

### Try it first

There is a library made for trying the installer on, [zephyr-installer-example](https://github.com/nimaltd/zephyr-installer-example). It builds in any Zephyr application, `native_sim` included, with its settings in Kconfig. Its README walks through an install, an update that keeps a setting you changed, an option, and an uninstall. From your application's folder:

```bash
zephyr-installer nimaltd/zephyr-installer-example
```

Its `installer.yml` has every key with a comment, so it is also a starting point for making your own library installable.

### What happens

Take `example`, installed into an application called `app`:

```
app/
  CMakeLists.txt         one block added, above find_package(Zephyr)
  prj.conf               one block added, CONFIG_EXAMPLE=y and what it needs
  modules/example/
    example.h            the library's files, as its installer.yml lists them
    example.c
    zephyr/
      module.yml         written by the installer: the library as a Zephyr module
      CMakeLists.txt     its files, built when CONFIG_EXAMPLE is set
      Kconfig            CONFIG_EXAMPLE and the library's settings
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
  written modules/example/example.h
  written modules/example/example.c

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
| The library's GitHub address | `zephyr-installer https://github.com/owner/example` |
| The zip from GitHub's **Download ZIP** | `zephyr-installer D:/Downloads/example-main.zip` |
| That zip unpacked, anywhere on disk | `zephyr-installer D:/Downloads/example-main` |
| The library's folder, already inside your application | `zephyr-installer modules/example` |

A bare name with no owner, like `example`, is a NimaLTD library, `nimaltd/example` on GitHub, unless a folder of that name exists where you run it, in which case the folder is used. A path that does not exist is reported as missing rather than looked up on GitHub.

### Options

| Option | What it does |
|---|---|
| `--conf boards/x.conf` | The Kconfig file that switches the libraries on. Asked when the application has more than one, `prj.conf` otherwise. See [Which Kconfig file](#which-kconfig-file) |
| `--dir libs/example` | The folder of your application to install into, for one library. Asked for when not given, with `modules/<name>` as the answer if you just press Enter, or the folder it is already in |
| `--project D:/work/app` | Your application's folder, when you are not running from it |
| `--ref v2.0.0` | A tag, a branch or a commit to take from GitHub. When not given, `main`, or `master` for a repository that has no `main` |
| `--key github_pat_...` | A GitHub token, for a library in a private repository. See [A private repository](#a-private-repository) |
| `--uninstall example` | Take the library out of the application. See [Uninstalling a library](#uninstalling-a-library) |
| `--with littlefs` | Take this part of the library without being asked. Give it once for each part |
| `--without littlefs` | Leave this part out, or take it out of a library already installed |
| `--version` | Show which version of the installer you have, and do nothing else |

### Updating a library

Run the same command again. Every file of the library is replaced, so an update updates, and the module's three files are written again from the new `installer.yml`, so a source file the new version adds is built without you editing anything. A file that did not change is left alone, so the build does not configure again for nothing.

What you wrote between `USER CODE BEGIN` and `USER CODE END` in a library's file is kept. Outside those lines, the next install replaces it, and when that would lose something of yours the file is saved beside it first, as a `.bak`.

The record of what is installed, and where, is `.zephyr-installer.json` in your application's folder. Keep it in version control with the rest.

### Uninstalling a library

```bash
zephyr-installer --uninstall example
```

From your application's folder, or with `--project`. Its block goes from `CMakeLists.txt` and from the Kconfig file that has it, the module files the installer wrote go from its folder, and then the library's own files. Installed and then uninstalled, `CMakeLists.txt` and `prj.conf` are back to the byte they were.

What was yours is saved before it goes, as a `.bak` beside it: any file of the library you wrote in between its `USER CODE` lines or changed by hand. A file you put in the library's folder yourself is left where it is, and the folder with it.

A setting you set yourself, below the installer's block, is your line, and it stays. The symbol it sets went with the library, though, and Zephyr stops on a symbol it does not know, so the installer names every such line:

```
  manual  prj.conf  prj.conf still sets what came with example, and Zephyr stops on a symbol it does not know. Take these lines out:
          CONFIG_EXAMPLE_POLL_CHUNK=64
```

A library another one needs stays, and the installer says which needs it. Name them all, in any order, and each goes after what needs it: `zephyr-installer --uninstall osal ee24`. When the library you took out brought another with it that nothing left needs, the last line names it, with the command that takes it out too. Uninstall works from `.zephyr-installer.json`, the record of what was installed and where.

### A library that needs another

You install only the one you want, and what it needs goes in first, each as a module of its own with its own blocks. One already in the application at a version that will do is left alone. Everything is fetched before anything is installed, so when a library cannot be had, your application is left as it was.

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

Put an `installer.yml` at the root of the repository. Any library can have one, whoever wrote it, and the one file serves both zephyr-installer and stm32-installer: each reads its own keys and leaves the other's alone.

Every key zephyr-installer reads is below, each with what it does. Only `name` and `files` are required; leave out what your library does not need. For a working one to copy, see [zephyr-installer-example](https://github.com/nimaltd/zephyr-installer-example).

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
  zephyr_installer: 1.0.0          # the oldest zephyr-installer that reads this file
  libraries:                       # other libraries, installed first when missing
    - osal >= 1.0.0                # no owner means nimaltd; >= the oldest that will do
    - owner/lib                    # anyone else's, as owner/name
  kconfig:                         # symbols it needs, set in the Kconfig file
    - I2C                          # a symbol alone is set to y
    - MAIN_STACK_SIZE=2048         # or SYMBOL=value: y, n, a number, 0x.. or "text"
  peripherals:                     # hardware it uses, named to the user
    - type: i2c                    # what it is
      count: 1                     # how many
      note: 400 kHz                # how to set it up

install:
  layout: mirror                   # mirror keeps the repository's folders,
                                   # flat (the default) puts every file at the top
  include_dirs: [src]              # include folders, only when the guess is wrong
  defines:                         # given to the whole build, NAME or NAME=value
    - EXAMPLE_FAST

files:
  headers:                         # .h files; the first is the one to #include
    - src/example.h
    - src/port/*.h                 # a wildcard, matched the way a shell would
  sources:                         # .c files, built when the library is switched on
    - src/example.c
    - from: src/port/spi.c         # a file that goes somewhere of its own,
      to: port/spi.c               # whatever the layout says

options:                           # parts the user chooses at install
  littlefs:                        # the name typed after --with
    description: LittleFS file system on the flash  # the question asked
    libraries:                     # libraries this part needs, installed first
      - littlefs >= 2.11.0
    files:                         # its files, written like files above
      sources:
        - src/example_lfs.c

extras:                            # copied as they are, never compiled
  - LICENSE.md                     # LICENSE.md and NOTICE are the default,
  - NOTICE                         # so leave this out if that is all
  - README.md

zephyr:                            # read by zephyr-installer only
  kconfig: EXAMPLE                 # the library's symbol; the name in capitals when left out
  cmake:                           # lines of CMake added to the module, inside if(CONFIG_X)
    - zephyr_library_link_libraries(mbedTLS)
  settings:                        # Kconfig symbols the user sets, CONFIG_<name> in the code
    - name: EXAMPLE_POLL_CHUNK     # the symbol, best started with the library's own
      type: int                    # bool, int, hex or string
      default: 32                  # required: true or false, a number, 0x.. or text
      range: [1, 32768]            # int and hex only: [smallest, largest]
      prompt: Bytes read per call  # one line, shown in menuconfig
      help: |                      # as many lines as it takes, shown in menuconfig
        A read by polling moves at most this many bytes per call.
```

Keys only stm32-installer reads, such as `requires.installer`, `requires.hal_modules` and `requires.rtos`, can stay in the same file. This installer skips them.

Leave `version` out. The installer reads the version from the `@version` tag in the file comment of the first header listed, so it is written in the code and nowhere else.

`requires.zephyr_installer` is the oldest zephyr-installer that reads the file correctly. It is checked before anything else in the file is read, so an older installer stops with a message saying to update, rather than read the file wrongly. Write it as three numbers, `1.0.0`: unquoted, YAML reads `1.10` as the decimal number `1.1`, and that is refused.

### More CMake for a library

A library that needs more than its files and its defines, a library of Zephyr's linked in or an option for its compiler, lists the lines under `zephyr.cmake`. They go into its module's `CMakeLists.txt`, inside `if(CONFIG_EXAMPLE)`, so they count only while the library is switched on:

```yaml
zephyr:
  cmake:
    - zephyr_library_link_libraries(mbedTLS)
    - zephyr_library_compile_options(-O2)
```

`zephyr_library_...` commands act on the library's own files only. A library of headers alone has no library of its own, so it uses the `zephyr_...` ones, which act on the whole build. The lines run when the user configures the build, the same as a module the library ships itself would, so they are the library's to answer for.

The user has a place in that file too. Its last lines are a `USER CODE` section, empty to start with, and every install keeps what is written in it, the way a configuration header keeps settings:

```cmake
  # USER CODE BEGIN EXAMPLE_CMAKE
  zephyr_library_compile_definitions(EXAMPLE_DEBUG=1)
  # USER CODE END EXAMPLE_CMAKE
endif()
```

On an uninstall, a section with something in it is saved as a `.bak` before the file goes.

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

A library that ships a `zephyr/module.yml` of its own, listed under `extras` or `files` so it is installed, knows its build better than the installer does. Its module is used as it is: nothing is written into its `zephyr` folder, and only the two blocks in the application are added. `zephyr.kconfig` then names the symbol its Kconfig defines, for the block in `prj.conf` to set.

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

CI also installs a small library from `test/e2e/` into an application, builds it with Zephyr for `native_sim`, runs it, and checks what it prints, so every release is known to build with real Zephyr.

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
