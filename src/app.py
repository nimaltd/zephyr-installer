"""
The application's own files: CMakeLists.txt and a Kconfig file such as prj.conf.

Two short blocks are added, each between marker lines so it can be found and
written again on the next install:

    CMakeLists.txt  adds the library's folder to ZEPHYR_EXTRA_MODULES, before
                    find_package(Zephyr), which is when Zephyr reads it
    prj.conf        sets the library's symbol, and the ones it needs. Any
                    other Kconfig file of the application can take it instead,
                    a board's own in boards/ for one, as the user chooses

Both files are the user's, so the rules of every edit here hold: a copy is
taken before anything changes, a file this cannot read safely is left alone
with the lines to add by hand, a second install adds nothing twice, and the
file's own line endings are kept.

What the user set in a Kconfig file outside the block is theirs. A symbol they
set is not set again in the block, whatever value they gave it, since the line
read last would win and quietly undo their choice.
"""

import os
import re
from pathlib import Path

from .core.files import backup
from .core.target import ALREADY, CHANGED, MANUAL, Outcome
from .module import cmake_quote

CMAKELISTS = "CMakeLists.txt"
PRJ_CONF = "prj.conf"

MARK_OPEN = "# >>> zephyr-installer: {name} >>>"
MARK_CLOSE = "# <<< zephyr-installer: {name} <<<"

# The line Zephyr's build starts at. CMake commands ignore case, and only a
# line that starts with it counts, so a commented out one does not.
FIND_ZEPHYR = re.compile(r"^[ \t]*find_package[ \t]*\([ \t]*Zephyr\b", re.MULTILINE | re.IGNORECASE)

# CONFIG_FOO=y, and the form menuconfig writes for a symbol switched off. A
# file written on Windows ends its lines in CRLF, and $ stops only before the
# line feed, so the carriage return is allowed for, never taken into a value.
ASSIGNED = re.compile(r"^[ \t]*CONFIG_([A-Za-z0-9_]+)[ \t]*=[ \t]*(.*?)[ \t\r]*$", re.MULTILINE)
NOT_SET = re.compile(r"^[ \t]*#[ \t]*CONFIG_([A-Za-z0-9_]+) is not set[ \t\r]*$", re.MULTILINE)


def read(path):
    """The file's text, with its line endings exactly as they are on disk."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return handle.read()


def write(path, text):
    """Write the text back with its line endings untouched."""
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def line_ending(text):
    """The line ending the file already uses, line feed for a new one."""
    return "\r\n" if "\r\n" in text else "\n"


def _text(path):
    """A file's text, empty when it is missing or unreadable."""
    try:
        return read(path)
    except (OSError, UnicodeDecodeError):
        return ""


def find_cmakelists(project_root):
    """The application's CMakeLists.txt, when it is a Zephyr application."""
    path = Path(project_root) / CMAKELISTS

    return path if FIND_ZEPHYR.search(_text(path)) else None


def conf_files(project_root):
    """
    The application's Kconfig files, as paths from its folder: prj.conf first,
    then any other .conf beside it, then the boards' own in boards/.
    """
    root = Path(project_root)
    found = sorted(p.name for p in root.glob("*.conf") if p.is_file())
    found += sorted(f"boards/{p.name}" for p in (root / "boards").glob("*.conf") if p.is_file())

    if PRJ_CONF in found:
        found.remove(PRJ_CONF)
        found.insert(0, PRJ_CONF)

    return found


def block_span(text, name):
    """
    Where this library's block is: (start, end), None when it has none, or
    False when only its first marker is there.
    """
    open_mark = MARK_OPEN.format(name=name)
    close_mark = MARK_CLOSE.format(name=name)

    if open_mark not in text:
        return None

    start = text.index(open_mark)

    if close_mark not in text[start:]:
        return False

    return start, text.index(close_mark, start) + len(close_mark)


def holding(project_root, name):
    """
    The Kconfig file that already has this library's block, or None.

    Looked for one folder deeper than the files offered, so one the user gave
    with --conf, such as conf/debug.conf, is found again on an update. Not in
    a build folder, and not in a hidden one.
    """
    root = Path(project_root)
    found = [p for p in list(root.glob("*.conf")) + list(root.glob("*/*.conf"))
             if p.is_file() and not p.relative_to(root).parts[0].startswith(("build", "."))]

    for path in sorted(found):
        if block_span(_text(path), name) is not None:
            return path.relative_to(root).as_posix()

    return None


def in_block(project_root, name, conf):
    """The symbols this library's own block in conf sets, and their values."""
    text = _text(Path(project_root) / conf)
    span = block_span(text, name)

    return dict(ASSIGNED.findall(text[span[0]:span[1]])) if span else {}


def assigned(project_root, name, conf):
    """
    Every symbol set outside this library's block, {symbol: (value, file)},
    in the Kconfig file conf and in prj.conf, which Zephyr reads with a
    board's own file.
    """
    found = {}

    for relative in dict.fromkeys([Path(conf).as_posix(), PRJ_CONF]):
        text = _text(Path(project_root) / relative)
        span = block_span(text, name)

        if span:
            text = text[:span[0]] + text[span[1]:]

        for symbol in NOT_SET.findall(text):
            found.setdefault(symbol, ("n", relative))

        for symbol, value in ASSIGNED.findall(text):
            found.setdefault(symbol, (value, relative))

    return found


def relative(path, root):
    """A forward slash path from root to path, None on another drive."""
    try:
        return Path(os.path.relpath(Path(path).resolve(), Path(root).resolve())).as_posix()
    except ValueError:
        return None


def _module_path(destination, project_root):
    """The library's folder as CMake reads it, from the application's folder."""
    folder = relative(destination, project_root)

    if folder is None:
        return cmake_quote(Path(destination).resolve().as_posix())

    return '"${CMAKE_CURRENT_SOURCE_DIR}/' + cmake_quote(folder)[1:]


def _write_block(path, label, text, updated, what):
    """Back the file up and write it. Returns an Outcome."""
    if updated == text:
        return Outcome(label, ALREADY, f"{label} already has {what}.")

    saved = backup(path) if path.exists() else None

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path, updated)
    except OSError as error:
        return Outcome(label, MANUAL, f"Could not write {label}: {error}", backup=saved)

    return Outcome(label, CHANGED, f"Added {what} to {label}.", backup=saved)


def _half_written(label, name, block):
    return Outcome(
        label, MANUAL,
        f"{label} has a half written zephyr-installer block for {name}. Fix it by hand first.",
        block.splitlines(),
    )


def cmake_block(library, destination, project_root, newline="\n"):
    """The lines this tool owns in the application's CMakeLists.txt."""
    lines = [
        MARK_OPEN.format(name=library.name),
        f"# Added by zephyr-installer. Delete this block, and {library.name}'s block in",
        "# the Kconfig file, to drop the library from the build.",
        f"list(APPEND ZEPHYR_EXTRA_MODULES {_module_path(destination, project_root)})",
        MARK_CLOSE.format(name=library.name),
    ]

    return newline.join(lines)


def integrate_cmake(project_root, library, destination):
    """Add the library's folder to ZEPHYR_EXTRA_MODULES. Returns an Outcome."""
    path = find_cmakelists(project_root)
    name = library.name

    if path is None:
        return Outcome(
            CMAKELISTS, MANUAL,
            "No CMakeLists.txt with find_package(Zephyr) here, so the library was not added to the build.",
            ["Add this to your application's CMakeLists.txt, above find_package(Zephyr):"]
            + cmake_block(library, destination, project_root).splitlines(),
        )

    text = read(path)
    newline = line_ending(text)
    block = cmake_block(library, destination, project_root, newline)
    span = block_span(text, name)

    if span is False:
        return _half_written(CMAKELISTS, name, block)

    rest = text

    if span is not None:
        start, end = span

        # Where it is, when that is above find_package(Zephyr).
        if start < FIND_ZEPHYR.search(text).start():
            return _write_block(path, CMAKELISTS, text, text[:start] + block + text[end:], name)

        # Below it the list does nothing, since Zephyr has looked for modules
        # by then. It comes out, with the line it stood on, and goes above.
        if text.startswith(newline, end):
            end += len(newline)

        rest = text[:start] + text[end:]

    first = FIND_ZEPHYR.search(rest).start()
    before = rest[:first]

    # A blank line either side, unless one is there already.
    gap = newline if before and not before.endswith(newline + newline) else ""
    updated = before + gap + block + newline + newline + rest[first:]

    return _write_block(path, CMAKELISTS, text, updated, name)


def conf_block(library, project_root, conf, newline="\n"):
    """The lines this tool owns in the Kconfig file, leaving out what the user sets."""
    taken = assigned(project_root, library.name, conf)
    wanted = [requirement.line for requirement in library.requires.kconfig
              if requirement.symbol not in taken]
    symbol = library.zephyr.symbol

    if symbol not in taken:
        wanted.append(f"CONFIG_{symbol}=y")

    lines = [
        MARK_OPEN.format(name=library.name),
        "# Added by zephyr-installer, and written again on every install, so set",
        f"# {library.name}'s settings below this block rather than in it.",
    ]

    if library.zephyr.settings:
        lines.append("# Its settings, as they are unless you set them:")
        lines.extend(f"#   {setting.line}" for setting in library.zephyr.settings)

    lines.extend(wanted)
    lines.append(MARK_CLOSE.format(name=library.name))

    return newline.join(lines)


def integrate_conf(project_root, library, conf):
    """
    Switch the library on in the Kconfig file conf, a path from the
    application's folder, created when it is not there. Returns an Outcome.
    """
    path = Path(project_root) / conf
    label = Path(conf).as_posix()

    try:
        text = read(path) if path.exists() else ""
    except (OSError, UnicodeDecodeError) as error:
        return Outcome(label, MANUAL, f"Could not read {label}: {error}",
                       conf_block(library, project_root, conf).splitlines())

    newline = line_ending(text)
    block = conf_block(library, project_root, conf, newline)
    span = block_span(text, library.name)

    if span is False:
        return _half_written(label, library.name, block)

    if span is not None:
        updated = text[:span[0]] + block + text[span[1]:]
    else:
        # At the end, after a blank line when the file has anything in it.
        head = text.rstrip("\r\n")
        updated = (head + newline + newline if head else "") + block + newline

    return _write_block(path, label, text, updated, library.name)


def integrate(project_root, library, destination, conf):
    """Both edits, the Kconfig one only in a Zephyr application. Returns a list of Outcome."""
    outcomes = [integrate_cmake(project_root, library, destination)]

    if find_cmakelists(project_root) is not None:
        outcomes.append(integrate_conf(project_root, library, conf))

    return outcomes
