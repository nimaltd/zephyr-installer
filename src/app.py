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

    # Right above find_package(Zephyr), with a blank line between, and nothing
    # added above it, so an uninstall can give the file back as it was.
    first = FIND_ZEPHYR.search(rest).start()
    updated = rest[:first] + block + newline + newline + rest[first:]

    return _write_block(path, CMAKELISTS, text, updated, name)


def wanted(library):
    """Every line the library asks for: (symbol, value, line), its own switch last."""
    found = [(requirement.symbol, requirement.value, requirement.line)
             for requirement in library.requires.kconfig]
    symbol = library.zephyr.symbol

    return found + [(symbol, "y", f"CONFIG_{symbol}=y")]


def already_set(library, project_root, conf):
    """
    The lines the library asks for that the user's own files set already:
    (symbol, wanted value, line, value set, file).
    """
    taken = assigned(project_root, library.name, conf)

    return [(symbol, value, line) + taken[symbol]
            for symbol, value, line in wanted(library) if symbol in taken]


def conf_block(library, project_root, conf, newline="\n"):
    """
    The lines this tool owns in the Kconfig file.

    A symbol the user sets already is written too, commented out with who sets
    it, so the block shows what the library asked for and why it is not set
    here. Set again here, the line read last would win and quietly undo the
    user's choice.
    """
    taken = assigned(project_root, library.name, conf)
    body = []

    for symbol, _value, line in wanted(library):
        if symbol in taken:
            have, where = taken[symbol]
            body.append(f"# {line}  (left out: {where} sets CONFIG_{symbol}={have})")
        else:
            body.append(line)

    lines = [
        MARK_OPEN.format(name=library.name),
        "# Added by zephyr-installer, and written again on every install, so set",
        f"# {library.name}'s settings below this block rather than in it.",
    ]

    if library.zephyr.settings:
        lines.append("# Its settings, as they are unless you set them:")
        lines.extend(f"#   {setting.line}" for setting in library.zephyr.settings)

    lines.extend(body)
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

    outcome = _write_block(path, label, text, updated, library.name)

    # Said again where the file's changes are, so it is not missed.
    outcome.steps += [
        f"{line} is left commented: {where} sets CONFIG_{symbol}={have}, and that is the one used."
        for symbol, _value, line, have, where in already_set(library, project_root, conf)
    ]

    return outcome


def integrate(project_root, library, destination, conf):
    """Both edits, the Kconfig one only in a Zephyr application. Returns a list of Outcome."""
    outcomes = [integrate_cmake(project_root, library, destination)]

    if find_cmakelists(project_root) is not None:
        outcomes.append(integrate_conf(project_root, library, conf))

    return outcomes


def _cut_block(path, label, name):
    """
    Take this library's block out of one file, with the blank line it brought.

    Returns an Outcome, ALREADY when the file has no block of it.
    """
    try:
        text = read(path)
    except (OSError, UnicodeDecodeError):
        return Outcome(label, ALREADY, f"{label} has nothing of {name}.")

    span = block_span(text, name)

    if span is None:
        return Outcome(label, ALREADY, f"{label} has nothing of {name}.")

    if span is False:
        return Outcome(label, MANUAL, f"{label} has a half written zephyr-installer block for {name}. "
                       "Take it out by hand.")

    newline = line_ending(text)
    start, end = span

    # The block's own line ending, then the one blank line that came with it:
    # below it in CMakeLists.txt, or above it at the end of a Kconfig file.
    if text.startswith(newline, end):
        end += len(newline)

    if text.startswith(newline, end):
        end += len(newline)
    elif end == len(text) and text[:start].endswith(newline + newline):
        start -= len(newline)

    saved = backup(path)
    write(path, text[:start] + text[end:])

    return Outcome(label, CHANGED, f"Removed {name} from {label}.", backup=saved)


def uninstall(project_root, name):
    """Take this library's blocks out of CMakeLists.txt and its Kconfig file. A list of Outcome."""
    outcomes = []
    cmakelists = Path(project_root) / CMAKELISTS

    if cmakelists.is_file():
        outcomes.append(_cut_block(cmakelists, CMAKELISTS, name))

    conf = holding(project_root, name)

    if conf is not None:
        outcomes.append(_cut_block(Path(project_root) / conf, conf, name))

    return outcomes


def leftover(project_root, symbols):
    """
    Lines of the application's Kconfig files that still set one of symbols:
    {file: [line, ...]}. Read once the library's own block is out.
    """
    wanted = set(symbols)
    found = {}

    for relative in conf_files(project_root):
        text = _text(Path(project_root) / relative)
        lines = [line.strip() for line in text.splitlines()
                 if (ASSIGNED.match(line) and ASSIGNED.match(line).group(1) in wanted)
                 or (NOT_SET.match(line) and NOT_SET.match(line).group(1) in wanted)]

        if lines:
            found[relative] = lines

    return found
