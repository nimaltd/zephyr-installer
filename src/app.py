"""
The application's own files: CMakeLists.txt, a Kconfig file such as prj.conf,
and sysbuild.conf.

Short blocks are added, each between marker lines so it can be found and
written again on the next install:

    CMakeLists.txt  adds the library's folder to ZEPHYR_EXTRA_MODULES, before
                    find_package(Zephyr), which is when Zephyr reads it. And
                    any group of the library's CMake lines whose place is the
                    application's: above find_package(Zephyr), or at the end
    prj.conf        sets the library's symbol, and the ones it needs. Any
                    other Kconfig file of the application can take it instead,
                    a board's own in boards/ for one, as the user chooses
    sysbuild.conf   the library's settings of sysbuild, MCUboot's for one,
                    when it has any. Never the application's Kconfig file

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

from .core import blocks
from .core.files import backup
from .core.installer import installed_libraries
from .core.manifest import LIBRARY
from .core.target import ALREADY, CHANGED, MANUAL, Outcome
from .module import cmake_quote, groups

CMAKELISTS = "CMakeLists.txt"
PRJ_CONF = "prj.conf"
SYSBUILD_CONF = "sysbuild.conf"

INSTALLER = "zephyr-installer"

MARK_OPEN = "# >>> zephyr-installer: {name} >>>"
MARK_CLOSE = "# <<< zephyr-installer: {name} <<<"

# Where a group goes in the application's CMakeLists.txt: the same names as
# zephyr.py's, here to keep the two modules apart.
BEFORE_ZEPHYR = "before-zephyr"
AFTER_ZEPHYR = "after-zephyr"

# The line Zephyr's build starts at. CMake commands ignore case, and only a
# line that starts with it counts, so a commented out one does not.
FIND_ZEPHYR = re.compile(r"^[ \t]*find_package[ \t]*\([ \t]*Zephyr\b", re.MULTILINE | re.IGNORECASE)

# CONFIG_FOO=y, and the form menuconfig writes for a symbol switched off. A
# file written on Windows ends its lines in CRLF, and $ stops only before the
# line feed, so the carriage return is allowed for, never taken into a value.
ASSIGNED = re.compile(r"^[ \t]*CONFIG_([A-Za-z0-9_]+)[ \t]*=[ \t]*(.*?)[ \t\r]*$", re.MULTILINE)
NOT_SET = re.compile(r"^[ \t]*#[ \t]*CONFIG_([A-Za-z0-9_]+) is not set[ \t\r]*$", re.MULTILINE)

# The same two forms in sysbuild.conf, where every symbol starts SB_CONFIG_.
SB_ASSIGNED = re.compile(r"^[ \t]*SB_CONFIG_([A-Za-z0-9_]+)[ \t]*=[ \t]*(.*?)[ \t\r]*$", re.MULTILINE)
SB_NOT_SET = re.compile(r"^[ \t]*#[ \t]*SB_CONFIG_([A-Za-z0-9_]+) is not set[ \t\r]*$", re.MULTILINE)


def marker(name, label=None):
    """The two lines around a block of this library, or of one of its groups."""
    return blocks.Marker(INSTALLER, name, label)


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

    # sysbuild.conf is sysbuild's, not the application's: a library is never
    # switched on there, so it is never offered.
    found = sorted(p.name for p in root.glob("*.conf") if p.is_file() and p.name != SYSBUILD_CONF)
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
    return blocks.span(text, marker(name))


def holding(project_root, name):
    """
    The Kconfig file that already has this library's block, or None.

    Looked for one folder deeper than the files offered, so one the user gave
    with --conf, such as conf/debug.conf, is found again on an update. Not in
    a build folder, and not in a hidden one. Not in sysbuild.conf either, nor
    in sysbuild/, which holds the settings of the other images.
    """
    root = Path(project_root)
    found = [p for p in list(root.glob("*.conf")) + list(root.glob("*/*.conf"))
             if p.is_file() and not p.relative_to(root).parts[0].startswith(("build", ".", "sysbuild"))]

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

    # An update, when the file had a block of the library's before.
    if f">>> zephyr-installer: {what} >>>" in text or f">>> zephyr-installer: {what}/" in text:
        return Outcome(label, CHANGED, f"Updated {what} in {label}.", backup=saved)

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
    """
    Add the library's folder to ZEPHYR_EXTRA_MODULES, and write its groups of
    CMake lines whose place is the application's. Returns an Outcome.
    """
    path = find_cmakelists(project_root)
    name = library.name
    ours = [group for group in groups(library) if group.where in (BEFORE_ZEPHYR, AFTER_ZEPHYR)]

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
            updated = text[:start] + block + text[end:]
        else:
            # Below it the list does nothing, since Zephyr has looked for modules
            # by then. It comes out, with the line it stood on, and goes above.
            if text.startswith(newline, end):
                end += len(newline)

            rest = text[:start] + text[end:]
            updated = None
    else:
        updated = None

    if updated is None:
        # Right above find_package(Zephyr), with a blank line between, and
        # nothing added above it, so an uninstall can give the file back as it was.
        first = FIND_ZEPHYR.search(rest).start()
        updated = rest[:first] + block + newline + newline + rest[first:]

    folder = library_folder(destination, project_root)
    updated = _with_groups(updated, library, ours, newline, folder)

    if updated is False:
        return _half_written(CMAKELISTS, name, "\n".join(
            line for group in ours for line in group_lines(library, group, folder)))

    outcome = _write_block(path, CMAKELISTS, text, updated, name)
    markers = [marker(name)] + [marker(name, group.label) for group in ours]
    outcome.blocks = {CMAKELISTS: blocks.fingerprints(updated, markers)}
    outcome.steps += _edited(project_root, name, CMAKELISTS, markers, text)

    return outcome


def library_folder(destination, project_root):
    """
    The library's folder as a line of the application's CMakeLists.txt names
    it, for {library} in a 2.1.0 manifest's groups: from the application's
    folder, or in full when it is somewhere else. Unquoted, since the line has
    its own quotes around it.
    """
    folder = relative(destination, project_root)

    if folder is None:
        return Path(destination).resolve().as_posix()

    return "${CMAKE_CURRENT_SOURCE_DIR}" if folder in (".", "") else "${CMAKE_CURRENT_SOURCE_DIR}/" + folder


def group_lines(library, group, folder=None):
    """A group's block in the application's CMakeLists.txt, as lines, {library} standing for folder."""
    name = marker(library.name, group.label)
    lines = list(group.lines)

    if getattr(library, "rooted", False) and folder is not None:
        lines = [line.replace(LIBRARY, folder) for line in lines]

    return ([name.open, f"# From {library.name}'s installer.yml, and written again on every install."]
            + lines + [name.close])


def _with_groups(text, library, ours, newline, folder=None):
    """
    text with the library's groups for the application each in its place, and
    any group it no longer has taken out. False when one is half written.
    """
    wanted = {group.label for group in ours}

    for label in blocks.labels(text, INSTALLER, library.name):
        if label not in wanted:
            found = blocks.span(text, marker(library.name, label))

            if found is False:
                return False

            text = blocks.cut(text, found, newline)

    for group in ours:
        lines = group_lines(library, group, folder)[1:-1]
        anchor = _above_zephyr if group.where == BEFORE_ZEPHYR else None
        text = blocks.place(text, marker(library.name, group.label), lines, newline, anchor)

        if text is False:
            return False

    return text


def _above_zephyr(text):
    """Where find_package(Zephyr)'s line starts, for a group to go above it."""
    found = FIND_ZEPHYR.search(text)

    return blocks.line_start(text, found.start()) if found else None


def _edited(project_root, name, label, markers, text):
    """A line for each block the user changed inside since it was written."""
    entry = installed_libraries(project_root).get(name)
    recorded = entry.get("blocks") if isinstance(entry, dict) else None

    return [f"Your change inside the {found.name} block is replaced: the block is written again on every "
            "install. The file as it was is in the backup."
            for found in markers if blocks.edited(recorded, label, found, text)]


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
    outcome.blocks = {label: blocks.fingerprints(updated, [marker(library.name)])}
    outcome.steps += _edited(project_root, library.name, label, [marker(library.name)], text)

    # Said again where the file's changes are, so it is not missed.
    outcome.steps += [
        f"{line} is left commented: {where} sets CONFIG_{symbol}={have}, and that is the one used."
        for symbol, _value, line, have, where in already_set(library, project_root, conf)
    ]

    return outcome


def sysbuild_assigned(text, name):
    """Every symbol sysbuild.conf sets outside this library's block: {symbol: value}."""
    text = blocks.outside(text, marker(name))
    found = {}

    for symbol in SB_NOT_SET.findall(text):
        found.setdefault(symbol, "n")

    for symbol, value in SB_ASSIGNED.findall(text):
        found.setdefault(symbol, value)

    return found


def sysbuild_block(library, text, newline="\n"):
    """
    The lines this tool owns in sysbuild.conf. A symbol the user sets outside
    it is written commented out, with what the user set, as in conf_block.
    """
    taken = sysbuild_assigned(text, library.name)
    found = marker(library.name)
    lines = [
        found.open,
        "# Added by zephyr-installer, and written again on every install, so set",
        f"# {library.name}'s sysbuild settings below this block rather than in it.",
    ]

    for setting in library.zephyr.sysbuild:
        if setting.symbol in taken:
            lines.append(f"# {setting.line}  (left out: {SYSBUILD_CONF} sets "
                         f"SB_CONFIG_{setting.symbol}={taken[setting.symbol]})")
        else:
            lines.append(setting.line)

    lines.append(found.close)

    return newline.join(lines)


def integrate_sysbuild(project_root, library):
    """
    Write the library's sysbuild settings into sysbuild.conf, made when it is
    missing, or take out the block of a version that had some. None for a
    library that has none and never had.
    """
    path = Path(project_root) / SYSBUILD_CONF

    try:
        text = read(path) if path.exists() else ""
    except (OSError, UnicodeDecodeError) as error:
        return Outcome(SYSBUILD_CONF, MANUAL, f"Could not read {SYSBUILD_CONF}: {error}",
                       sysbuild_block(library, "").splitlines())

    span = block_span(text, library.name)

    if not library.zephyr.sysbuild:
        return _cut_block(path, SYSBUILD_CONF, library.name) if span else None

    newline = line_ending(text)
    block = sysbuild_block(library, text, newline)

    if span is False:
        return _half_written(SYSBUILD_CONF, library.name, block)

    if span is not None:
        updated = text[:span[0]] + block + text[span[1]:]
    else:
        head = text.rstrip("\r\n")
        updated = (head + newline + newline if head else "") + block + newline

    outcome = _write_block(path, SYSBUILD_CONF, text, updated, library.name)
    outcome.blocks = {SYSBUILD_CONF: blocks.fingerprints(updated, [marker(library.name)])}
    outcome.steps += _edited(project_root, library.name, SYSBUILD_CONF, [marker(library.name)], text)
    taken = sysbuild_assigned(text, library.name)
    outcome.steps += [
        f"{setting.line} is left commented: {SYSBUILD_CONF} sets SB_CONFIG_{setting.symbol}="
        f"{taken[setting.symbol]}, and that is the one used."
        for setting in library.zephyr.sysbuild if setting.symbol in taken
    ]

    return outcome


def integrate(project_root, library, destination, conf):
    """Both edits, the Kconfig one only in a Zephyr application. Returns a list of Outcome."""
    outcomes = [integrate_cmake(project_root, library, destination)]

    if find_cmakelists(project_root) is not None:
        outcomes.append(integrate_conf(project_root, library, conf))
        sysbuild = integrate_sysbuild(project_root, library)

        if sysbuild is not None:
            outcomes.append(sysbuild)

    return outcomes


def _cut_block(path, label, name):
    """
    Take this library's blocks out of one file, with the blank line each
    brought: its own, and in CMakeLists.txt every group of its CMake lines.

    Returns an Outcome, ALREADY when the file has no block of it.
    """
    try:
        text = read(path)
    except (OSError, UnicodeDecodeError):
        return Outcome(label, ALREADY, f"{label} has nothing of {name}.")

    newline = line_ending(text)
    updated = text

    for found in [marker(name)] + [marker(name, group) for group in blocks.labels(text, INSTALLER, name)]:
        span = blocks.span(updated, found)

        if span is False:
            return Outcome(label, MANUAL, f"{label} has a half written zephyr-installer block for "
                           f"{found.name}. Take it out by hand.")

        if span is not None:
            updated = blocks.cut(updated, span, newline)

    if updated == text:
        return Outcome(label, ALREADY, f"{label} has nothing of {name}.")

    saved = backup(path)
    write(path, updated)

    return Outcome(label, CHANGED, f"Removed {name} from {label}.", backup=saved)


def uninstall(project_root, name):
    """
    Take this library's blocks out of CMakeLists.txt, its Kconfig file and
    sysbuild.conf. A list of Outcome. sysbuild.conf itself stays, even with
    nothing left in it: the user may have made it.
    """
    outcomes = []
    cmakelists = Path(project_root) / CMAKELISTS

    if cmakelists.is_file():
        outcomes.append(_cut_block(cmakelists, CMAKELISTS, name))

    conf = holding(project_root, name)

    if conf is not None:
        outcomes.append(_cut_block(Path(project_root) / conf, conf, name))

    sysbuild = Path(project_root) / SYSBUILD_CONF

    if sysbuild.is_file() and block_span(_text(sysbuild), name):
        outcomes.append(_cut_block(sysbuild, SYSBUILD_CONF, name))

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
