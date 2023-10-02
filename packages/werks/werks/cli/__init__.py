#!/usr/bin/env python3
# Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
"""Checkmk development script to manage werks
"""

# pylint: skip-file

import argparse
import ast
import fcntl
import os
import shlex
import struct
import subprocess
import sys
import termios
import time
import tty
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import NoReturn

Werk = dict[str, str]

RESERVED_IDS_FILE_PATH = f"{os.getenv('HOME')}/.cmk-werk-ids"

# colored output, if stdout is a tty
if sys.stdout.isatty():
    TTY_RED = "\033[31m"
    TTY_GREEN = "\033[32m"
    TTY_YELLOW = "\033[33m"
    TTY_BLUE = "\033[34m"
    TTY_MAGENTA = "\033[35m"
    TTY_CYAN = "\033[36m"
    TTY_WHITE = "\033[37m"
    TTY_BG_RED = "\033[41m"
    TTY_BG_GREEN = "\033[42m"
    TTY_BG_YELLOW = "\033[43m"
    TTY_BG_BLUE = "\033[44m"
    TTY_BG_MAGENTA = "\033[45m"
    TTY_BG_CYAN = "\033[46m"
    TTY_BG_WHITE = "\033[47m"
    TTY_BOLD = "\033[1m"
    TTY_UNDERLINE = "\033[4m"
    TTY_NORMAL = "\033[0m"

else:
    TTY_RED = ""
    TTY_GREEN = ""
    TTY_YELLOW = ""
    TTY_BLUE = ""
    TTY_MAGENTA = ""
    TTY_CYAN = ""
    TTY_WHITE = ""
    TTY_BG_RED = ""
    TTY_BG_GREEN = ""
    TTY_BG_BLUE = ""
    TTY_BG_MAGENTA = ""
    TTY_BG_CYAN = ""
    TTY_BG_WHITE = ""
    TTY_BOLD = ""
    TTY_UNDERLINE = ""
    TTY_NORMAL = ""


grep_colors = [
    TTY_BOLD + TTY_MAGENTA,
    TTY_BOLD + TTY_CYAN,
    TTY_BOLD + TTY_GREEN,
]


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # BLAME
    parser_blame = subparsers.add_parser("blame", help="Show who worked on a werk")
    parser_blame.add_argument(
        "id",
        nargs="?",
        type=int,
        help="werk ID",
        default=None,
    )
    parser_blame.set_defaults(func=main_blame)

    # DELETE
    parser_delete = subparsers.add_parser("delete", help="delete werk(s)")
    parser_delete.add_argument(
        "id",
        nargs="+",
        type=int,
        help="werk ID",
    )
    parser_delete.set_defaults(func=main_delete)

    # EDIT
    parser_edit = subparsers.add_parser("edit", help="open werk in editor")
    parser_edit.add_argument(
        "id",
        nargs="?",
        type=int,
        help="werk ID (defaults to newest)",
    )
    parser_edit.set_defaults(func=main_edit)

    # EXPORT
    parser_export = subparsers.add_parser("export", help="List werks")
    parser_export.add_argument(
        "-r",
        "--reverse",
        action="store_true",
        help="reverse order",
    )
    parser_export.add_argument(
        "filter",
        nargs="*",
        help="filter for edition, component, state, class, or target version",
    )
    parser_export.set_defaults(func=lambda args: main_list(args, "csv"))

    # GREP
    parser_grep = subparsers.add_parser(
        "grep",
        help="show werks containing all of the given keywords",
    )
    parser_grep.add_argument("-v", "--verbose", action="store_true")
    parser_grep.add_argument(
        "keywords",
        nargs="+",
        help="keywords to grep",
    )
    parser_grep.set_defaults(func=main_grep)

    # IDS
    parser_ids = subparsers.add_parser(
        "ids",
        help="Show the number of reserved werk IDs or reserve new werk IDs",
    )
    parser_ids.add_argument(
        "count",
        nargs="?",
        type=int,
        help="number of werks to reserve",
    )
    parser_ids.set_defaults(func=main_fetch_ids)

    # LIST
    parser_list = subparsers.add_parser("list", help="List werks")
    parser_list.add_argument(
        "-r",
        "--reverse",
        action="store_true",
        help="reverse order",
    )
    parser_list.add_argument(
        "filter",
        nargs="*",
        help="filter for edition, component, state, class, or target version",
    )
    parser_list.set_defaults(func=lambda args: main_list(args, "console"))

    # NEW
    parser_new = subparsers.add_parser("new", help="Create a new werk")
    parser_new.add_argument(
        "custom_files",
        nargs="*",
        help="files passed to 'git commit'",
    )
    parser_new.set_defaults(func=main_new)

    # PICK
    parser_pick = subparsers.add_parser(
        "pick",
        aliases=["cherry-pick"],
        help="Pick these werks",
    )
    parser_pick.add_argument(
        "-n",
        "--no-commit",
        action="store_true",
        help="do not commit at the end",
    )
    parser_pick.add_argument(
        "commit",
        nargs="+",
        help="Pick these commits",
    )
    parser_pick.set_defaults(func=main_pick)

    # SHOW
    parser_show = subparsers.add_parser("show", help="Show several werks")
    parser_show.add_argument(
        "ids",
        nargs="*",
        help="Show these werks, or 'all' for all, of leave out for last",
    )
    parser_show.set_defaults(func=main_show)

    # URL
    parser_url = subparsers.add_parser("url", help="Show the online URL of a werk")
    parser_url.add_argument("id", type=int, help="werk ID")
    parser_url.set_defaults(func=main_url)

    return parser.parse_args(argv)


def get_tty_size() -> tuple[int, int]:
    try:
        ws = bytearray(8)
        fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, ws)
        lines, columns, _x, _y = struct.unpack("HHHH", ws)
        if lines > 0 and columns > 0:
            return lines, columns
    except OSError:
        pass
    return (24, 99999)


def bail_out(text: str, exit_code: int = 1) -> NoReturn:
    sys.stderr.write(text + "\n")
    sys.exit(exit_code)


g_base_dir = ""


def goto_werksdir() -> None:
    global g_base_dir
    g_base_dir = os.path.abspath(".")
    while not os.path.exists(".werks") and os.path.abspath(".") != "/":
        os.chdir("..")

    try:
        os.chdir(".werks")
    except Exception:
        sys.stderr.write("Cannot find directory .werks\n")
        sys.exit(1)


g_last_werk: int | None = None


def get_last_werk() -> int:
    if g_last_werk is None:
        bail_out("No last werk known. Please specify id.")
    return g_last_werk


def load_config() -> None:
    global g_last_werk, valid_choices
    with open("config") as f_config:
        exec(f_config.read(), globals(), globals())  # nosec B102 # BNS:aee528
    try:
        with open(".last") as f_last:
            g_last_werk = int(f_last.read())
    except Exception:
        g_last_werk = None

    valid_choices = {
        "compatible": {e[0] for e in compatible},
        "class": {e[0] for e in classes},
        "edition": {e[0] for e in editions},
        "component": {e[0] for e in all_components()},
        "level": {e[0] for e in levels},
    }


def load_werks() -> dict[int, Werk]:
    werks = {}
    for entry in os.listdir("."):
        try:
            werkid = int(entry)
            try:
                werks[werkid] = load_werk(werkid)
            except Exception as e:
                sys.stderr.write("ERROR: Skipping invalid werk %d: %s\n" % (werkid, e))
        except Exception:
            continue
    return werks


def save_last_werkid(wid: int) -> None:
    try:
        with open(".last", "w") as f:
            f.write("%d\n" % int(wid))
    except OSError:
        pass


def load_current_version() -> str:
    with open("../defines.make") as f:
        for line in f:
            if line.startswith("VERSION"):
                version = line.split("=", 1)[1].strip()
                return version

    bail_out("Failed to read VERSION from defines.make")


@cache
def git_modified_files() -> set[int]:
    # this is called from `werk list` via werk_is_modified
    # so we can assume, that this won't change during runtime of this script
    modified = set()
    for line in os.popen("git status --porcelain"):
        if line[0] in "AM" and ".werks/" in line:
            try:
                wid = line.rsplit("/", 1)[-1].strip()
                modified.add(int(wid))
            except Exception:
                pass
    return modified


def werk_is_modified(werkid: int) -> bool:
    return werkid in git_modified_files()


def werk_exists(werkid: int) -> bool:
    return os.path.exists(str(werkid))


def load_werk(werkid: int) -> Werk:
    werk: Werk = {
        "id": str(werkid),
        "state": "unknown",
        "title": "unknown",
        "component": "general",
        "compatible": "compat",
        "edition": "cre",
    }

    with open(str(werkid)) as f:
        for line in f:
            line = line.strip()
            if line == "":
                break
            header, value = line.split(":", 1)
            werk[header.strip().lower()] = value.strip()

        werk["description"] = f.read()

    validate_werk(werk)

    return werk


def validate_werk(werk: Werk) -> None:
    for key, choices in valid_choices.items():
        if werk[key] not in choices:
            raise ValueError(f"Invalid value {werk[key]!r} for '{key}'")


def save_werk(werk: Werk) -> None:
    with open(werk["id"], "w") as f:
        f.write("Title: %s\n" % werk["title"])
        for key, val in sorted(werk.items()):
            if key not in ["title", "description", "id"]:
                f.write(f"{key[0].upper()}{key[1:]}: {val}\n")
        f.write("\n")
        f.write(werk["description"])
        f.write("\n")
    git_add(werk)
    save_last_werkid(int(werk["id"]))


def change_werk_version(werk_id: int, new_version: str) -> None:
    werk = load_werk(werk_id)
    werk["version"] = new_version
    save_werk(werk)
    git_add(werk)


def git_add(werk: Werk) -> None:
    os.system("git add %s" % werk["id"])  # nosec


def git_commit(werk: Werk, custom_files: list[str]) -> None:
    title = werk["title"]
    for classid, _classname, prefix in classes:
        if werk["class"] == classid:
            if prefix:
                title = f"{prefix} {title}"

    title = "{} {}".format(werk["id"].rjust(5, "0"), title)

    if custom_files:
        files_to_commit = custom_files
        default_files = [".werks"]
        for entry in default_files:
            files_to_commit.append(f"{git_top_level()}/{entry}")

        os.chdir(g_base_dir)
        cmd = "git commit {} -m {}".format(
            " ".join(files_to_commit),
            shlex.quote(title + "\n\n" + werk["description"]),
        )
        os.system(cmd)  # nosec

    else:
        if something_in_git_index():
            dash_a = ""
            os.system("cd '%s' ; git add .werks" % git_top_level())  # nosec
        else:
            dash_a = "-a"

        cmd = "git commit {} -m {}".format(
            dash_a,
            shlex.quote(title + "\n\n" + werk["description"]),
        )
        os.system(cmd)  # nosec


def git_top_level() -> str:
    with subprocess.Popen(["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE) as info:
        return str(info.communicate()[0].split()[0])


def something_in_git_index() -> bool:
    for line in os.popen("git status --porcelain"):
        if line[0] == "M":
            return True
    return False


def next_werk_id() -> int:
    my_werk_ids = get_werk_ids()
    if not my_werk_ids:
        bail_out(
            'You have no werk IDS left. You can reserve 10 additional Werk IDS with "./werk ids 10".'
        )
    return my_werk_ids[0]


def add_comment(werk: Werk, title: str, comment: str) -> None:
    werk[
        "description"
    ] += """
{}: {}
{}""".format(
        time.strftime("%F %T"),
        title,
        comment,
    )


def list_werk(werk: Werk) -> None:
    if werk_is_modified(int(werk["id"])):
        bold = TTY_BOLD + TTY_CYAN + "(*) "
    else:
        bold = ""
    _lines, cols = get_tty_size()
    title = werk["title"][: cols - 45]
    sys.stdout.write(
        "%s %-9s %s %3s %-13s %-6s %s%s%s %-8s %s%s%s\n"
        % (
            format_werk_id(werk["id"]),
            time.strftime("%F", time.localtime(int(werk["date"]))),
            colored_class(werk["class"], 8),
            werk["edition"],
            werk["component"],
            werk["compatible"],
            TTY_BOLD,
            werk["level"],
            TTY_NORMAL,
            werk["version"],
            bold,
            title,
            TTY_NORMAL,
        )
    )


def format_werk_id(werk_id: int | str) -> str:
    return TTY_BG_WHITE + TTY_BLUE + ("#%05d" % int(werk_id)) + TTY_NORMAL


def colored_class(classname: str, digits: int) -> str:
    if classname == "fix":
        return TTY_BOLD + TTY_RED + ("%-" + str(digits) + "s") % classname + TTY_NORMAL
    return ("%-" + str(digits) + "s") % classname


def show_werk(werk: Werk) -> None:
    list_werk(werk)
    sys.stdout.write("\n%s\n" % werk["description"])


def main_list(args: argparse.Namespace, fmt: str) -> None:  # pylint: disable=too-many-branches
    # arguments are tags from state, component and class. Multiple values
    # in one class are orred. Multiple types are anded.

    werks = list(load_werks().values())
    versions = set(werk["version"] for werk in werks)

    filters: dict[str, list[str]] = {}

    for a in args.filter:
        if a == "current":
            a = g_current_version

        hit = False
        for tp, values in [
            ("edition", editions),
            ("component", all_components()),
            ("level", levels),
            ("class", classes),
            ("version", versions),
            ("compatible", compatible),
        ]:
            for v in values:  # type: ignore[attr-defined] # all of them are iterable.
                if isinstance(v, tuple):
                    v = v[0]
                if v.startswith(a):
                    entries = filters.get(tp, [])
                    entries.append(v)
                    filters[tp] = entries
                    hit = True
                    break
            if hit:
                break
        if not hit:
            bail_out(
                "No such edition, component, state, class, or target version: %s" % a,
                0,
            )

    # Filter
    newwerks = []
    for werk in werks:
        skip = False
        for tp, entries in filters.items():
            if werk[tp] not in entries:
                skip = True
                break
        if not skip:
            newwerks.append(werk)

    werks = sorted(newwerks, key=lambda w: int(w["date"]), reverse=args.reverse)

    # Output
    if fmt == "console":
        for werk in werks:
            list_werk(werk)
    else:
        output_csv(werks)


# CSV Table has the following columns:
# Component;ID;Title;Class;Effort
def output_csv(werks: list[Werk]) -> None:
    def line(*l: int | str) -> None:
        sys.stdout.write('"' + '";"'.join(map(str, l)) + '"\n')

    nr = 1
    for entry in components:
        if isinstance(entry, tuple) and len(entry) == 2:
            name, alias = entry
        elif isinstance(entry, str):  # TODO: Hmmm...
            name, alias = entry, entry
        else:
            bail_out(f"invalid component {entry!r}")

        line("", "", "", "", "")

        total_effort = 0
        for werk in werks:
            if werk["component"] == name:
                total_effort += werk_effort(werk)
        line("", "%d. %s" % (nr, alias), "", total_effort)
        nr += 1

        for werk in werks:
            if werk["component"] == name:
                line(werk["id"], werk["title"], werk_class(werk), werk_effort(werk))
                line("", werk["description"].replace("\n", " ").replace('"', "'"), "", "")


def werk_class(werk: Werk) -> str:
    cl = werk["class"]
    for entry in classes:
        # typing: why would this be? LH: Tuple[str, str, str], RH: str
        if entry == cl:  # type: ignore[comparison-overlap]
            return cl

        if isinstance(entry, tuple) and entry[0] == cl:
            return entry[1]
    return cl


def werk_effort(werk: Werk) -> int:
    return int(werk.get("effort", "0"))


def main_show(args: argparse.Namespace) -> None:
    if "all" in args.ids:
        ids = list(load_werks().keys())
    else:
        ids = args.ids or [get_last_werk()]

    for wid in ids:
        if wid != ids[0]:
            sys.stdout.write(
                "-------------------------------------------------------------------------------\n"
            )
        try:
            show_werk(load_werk(int(wid)))
        except Exception:
            sys.stderr.write("Skipping invalid werk id '%s'\n" % wid)
    save_last_werkid(ids[-1])


def get_input(what: str, default: str = "") -> str:
    sys.stdout.write("%s: " % what)
    sys.stdout.flush()
    value = sys.stdin.readline().strip()
    if value == "":
        return default
    return value


def getch() -> str:
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    if ord(ch) == 3:
        raise KeyboardInterrupt()
    return ch


def input_choice(
    what: str, choices: list[str] | list[tuple[str, str]] | list[tuple[str, str, str]]
) -> str:
    next_index = 0
    ctc = {}
    texts = []
    for choice in choices:
        if isinstance(choice, tuple):
            choice = choice[0]

        added = False

        # Find an identifying character for the input choice. In case all possible
        # characters are already used start using unique numbers
        for c in str(choice):
            if c not in ".-_/" and c not in ctc:
                ctc[c] = choice
                texts.append(str(choice).replace(c, TTY_BOLD + c + TTY_NORMAL, 1))
                added = True
                break

        if not added:
            ctc["%s" % next_index] = choice
            texts.append("{}:{}".format("%s%d%s" % (TTY_BOLD, next_index, TTY_NORMAL), choice))
            next_index += 1

    while True:
        sys.stdout.write("{} ({}): ".format(what, ", ".join(texts)))
        sys.stdout.flush()
        c = getch()
        if c in ctc:
            sys.stdout.write(f" {TTY_BOLD}{ctc[c]}{TTY_NORMAL}\n")
            return ctc[c]

        sys.stdout.write("\n")


def get_edition_components(edition: str) -> list[tuple[str, str]]:
    return components + edition_components.get(edition, [])


def all_components() -> list[tuple[str, str]]:
    c = components
    for ed_components in edition_components.values():
        c += ed_components
    return components


werk_notes = """
    .---Werk----------------------------------------------------------------------.
    |                                                                             |
    |             The werk is intended for the user/admin!!                       |
    |                                                                             |
    |    From the titel it should be obvious if the user/admin is affected.       |
    |    Describe what needs to be done in the details. You can also note if no   |
    |    user interaction is required. If necessary add technical details.        |
    |                                                                             |
    '-----------------------------------------------------------------------------'

"""


def main_new(args: argparse.Namespace) -> None:
    sys.stdout.write(TTY_GREEN + werk_notes + TTY_NORMAL)

    werk: Werk = {}
    werk["id"] = str(next_werk_id())
    werk["date"] = str(int(time.time()))
    assert g_current_version
    werk["version"] = g_current_version
    werk["title"] = get_input("Title")
    if werk["title"] == "":
        sys.stderr.write("Cancelled.\n")
        sys.exit(0)
    werk["class"] = input_choice("Class", classes)
    werk["edition"] = input_choice("Edition", editions)
    werk["component"] = input_choice("Component", get_edition_components(werk["edition"]))
    werk["level"] = input_choice("Level", levels)
    werk["compatible"] = input_choice("Compatible", compatible)
    werk["description"] = "\n"

    save_werk(werk)
    invalidate_my_werkid(int(werk["id"]))
    edit_werk(int(werk["id"]), args.custom_files)

    sys.stdout.write("Werk %s saved.\n" % format_werk_id(werk["id"]))


def get_werk_arg(arg: str | int | None) -> int:
    wid = get_last_werk() if arg is None else int(arg)

    werk = load_werk(wid)
    if not werk:
        bail_out("No such werk.\n")
    save_last_werkid(wid)
    return wid


def main_blame(args: argparse.Namespace) -> None:
    wid = get_werk_arg(args.id)
    os.system("git blame %d" % wid)  # nosec


def main_url(args: argparse.Namespace) -> None:
    wid = get_werk_arg(args.id)
    sys.stdout.write(online_url % wid + "\n")


def main_delete(args: argparse.Namespace) -> None:
    werks = args.ids or [get_last_werk()]

    for werk_id in werks:
        if not werk_exists(werk_id):
            bail_out("There is no werk %s." % format_werk_id(werk_id))

        werk_to_be_removed_title = load_werk(int(werk_id))["title"]
        if os.system("git rm -f %s" % werk_id) == 0:  # nosec
            sys.stdout.write(
                "Deleted werk {} ({}).\n".format(format_werk_id(werk_id), werk_to_be_removed_title)
            )
            my_ids = get_werk_ids()
            my_ids.append(werk_id)
            store_werk_ids(my_ids)
            sys.stdout.write(
                "You lucky bastard now own the werk ID %s.\n" % format_werk_id(werk_id)
            )


def grep(line: str, kw: str, n: int) -> str | None:
    lc = kw.lower()
    i = line.lower().find(lc)
    if i == -1:
        return None
    col = grep_colors[n % len(grep_colors)]
    return line[0:i] + col + line[i : i + len(kw)] + TTY_NORMAL + line[i + len(kw) :]


def main_grep(args: argparse.Namespace) -> None:
    for werk in load_werks().values():
        one_kw_didnt_match = False
        title = werk["title"]
        lines = werk["description"].split("\n")
        bodylines = set()

        # *all* of the keywords must match in order for the
        # werk to be displayed
        i = 0
        for kw in args.keywords:
            i += 1
            this_kw_matched = False

            # look for keyword in title
            match = grep(title, kw, i)
            if match:
                werk["title"] = match
                title = match
                this_kw_matched = True

            # look for keyword in description
            for j, line in enumerate(lines):
                match = grep(line, kw, i)
                if match:
                    bodylines.add(j)
                    lines[j] = match
                    this_kw_matched = True

            if not this_kw_matched:
                one_kw_didnt_match = True

        if not one_kw_didnt_match:
            list_werk(werk)
            if args.verbose:
                for x in sorted(list(bodylines)):
                    sys.stdout.write("  %s\n" % lines[x])


def main_edit(args: argparse.Namespace) -> None:
    werkid = args.id or get_last_werk()
    edit_werk(werkid, None, commit=False)  # custom files are pointless if commit=False
    save_last_werkid(werkid)


def edit_werk(werkid: int, custom_files: list[str] | None = None, commit: bool = True) -> None:
    if custom_files is None:
        custom_files = []
    if not os.path.exists(str(werkid)):
        bail_out("No werk with this id.")
    editor = os.getenv("EDITOR")
    if not editor:
        for p in ["/usr/bin/editor", "/usr/bin/vim", "/bin/vi"]:
            if os.path.exists(p):
                editor = p
                break
    if not editor:
        bail_out("No editor available (please set EDITOR).\n")

    if os.system(f"bash -c '{editor} +11 {werkid}'") == 0:  # nosec
        werk = load_werk(werkid)
        git_add(werk)
        if commit:
            git_commit(werk, custom_files)


def main_pick(args: argparse.Namespace) -> None:
    for commit_id in args.commit:
        werk_cherry_pick(commit_id, args.no_commit)


def werk_cherry_pick(commit_id: str, no_commit: bool) -> None:
    # First get the werk_id
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_id],
        capture_output=True,
        check=True,
    )
    werk_id = None
    for line in result.stdout.splitlines():
        filename = line.decode("utf-8")
        if filename.startswith(".werks/") and filename[7:].isdigit():
            werk_id = int(filename[7:])

    if werk_id is not None:
        if os.path.exists(str(werk_id)):
            bail_out(f"Trying to pick werk {werk_id}, but werk already present. Aborted.")

    # Cherry-pick the commit in question from the other branch
    cmd = ["git", "cherry-pick"]
    if no_commit:
        cmd.append("--no-commit")
    cmd.append(commit_id)
    pick = subprocess.run(cmd, check=False)

    # Find werks that have been cherry-picked and change their version
    # to our current version
    if werk_id is not None:
        # Change the werk's version before checking the pick return code.
        # Otherwise the dev may forget to change the version
        assert g_current_version
        change_werk_version(werk_id, g_current_version)
        sys.stdout.write(
            f"Changed version of werk {format_werk_id(werk_id)} to {g_current_version}.\n"
        )

    if pick.returncode:
        # Exit with the result of the pick. This may be a merge conflict, so
        # other tools may need to know about this.
        sys.exit(pick.returncode)

    # Commit
    if werk_id is not None:
        # This allows for picking regular commits as well
        if not no_commit:
            subprocess.run(["git", "add", str(werk_id)], check=True)
            subprocess.run(["git", "commit", "--no-edit", "--amend"], check=True)
        else:
            sys.stdout.write("We don't commit yet. Here is the status:\n")
            sys.stdout.write("Please commit with git commit -C '%s'\n\n" % commit_id)
            subprocess.run(["git", "status"], check=True)


def get_werk_ids() -> list[int]:
    try:
        return ast.literal_eval(Path(RESERVED_IDS_FILE_PATH).read_text())  # type: ignore
    except Exception:
        return []


def invalidate_my_werkid(wid: int) -> None:
    ids = get_werk_ids()
    ids.remove(wid)
    store_werk_ids(ids)
    if not ids:
        sys.stdout.write(f"\n{TTY_RED}This was your last reserved ID.{TTY_NORMAL}\n\n")


def store_werk_ids(l: list[int]) -> None:
    with open(RESERVED_IDS_FILE_PATH, "w") as f:
        f.write(repr(l) + "\n")
    sys.stdout.write(f"Werk IDs stored in the file: {RESERVED_IDS_FILE_PATH}\n")


def current_branch() -> str:
    return [l for l in os.popen("git branch") if l.startswith("*")][0].split()[-1]


def current_repo() -> str:
    return list(os.popen("git config --get remote.origin.url"))[0].strip().split("/")[-1]


def main_fetch_ids(args: argparse.Namespace) -> None:
    if args.count is None:
        sys.stdout.write("You have %d reserved IDs.\n" % (len(get_werk_ids())))
        sys.exit(0)

    if current_branch() != "master" or current_repo() != "check_mk":
        bail_out("Werk IDs can only be reserved on the master branch of the check_mk repository.")

    # Get the start werk_id to reserve
    try:
        with open("first_free") as f:
            first_free = int(f.read().strip())
    except (OSError, ValueError):
        first_free = 0

    new_first_free = first_free + args.count
    # enterprise werks were between 8000 and 8749. Skip over this area for new
    # reserved werk ids
    if 8000 <= first_free < 8780 or 8000 <= new_first_free < 8780:
        first_free = 8780
        new_first_free = first_free + args.count

    # cmk-omd werk were between 7500 and 7680. Skip over this area for new
    # reserved werk ids
    if 7500 <= first_free < 7680 or 7500 <= new_first_free < 7680:
        first_free = 7680
        new_first_free = first_free + args.count

    # cma werks are between 9000 and 9999. Skip over this area for new
    # reserved werk ids
    if 9000 <= first_free < 10000 or 9000 <= new_first_free < 10000:
        first_free = 10000
        new_first_free = first_free + args.count

    # Store the werk_ids to reserve
    my_ids = get_werk_ids() + list(range(first_free, new_first_free))
    store_werk_ids(my_ids)

    # Store the new reserved werk ids
    with open("first_free", "w") as f:
        f.write(str(new_first_free) + "\n")

    sys.stdout.write(
        "Reserved %d additional IDs now. You have %d reserved IDs now.\n"
        % (args.count, len(my_ids))
    )

    if os.system("git commit -m 'Reserved %d Werk IDS' ." % args.count) == 0:  # nosec
        sys.stdout.write("--> Successfully committed reserved werk IDS. Please push it soon!\n")
    else:
        bail_out("Cannot commit.")


def use_markdown() -> bool:
    """
    as long as there is a single markdown file,
    we assume we should create and pick markdown werks.
    """
    for path in Path(".").iterdir():
        if path.name.endswith(".md"):
            return True
    return False


#                    _
#    _ __ ___   __ _(_)_ __
#   | '_ ` _ \ / _` | | '_ \
#   | | | | | | (_| | | | | |
#   |_| |_| |_|\__,_|_|_| |_|
#

# default config
editions: list[tuple[str, str]] = []
components: list[tuple[str, str]] = []
edition_components: dict[str, list[tuple[str, str]]] = {}
classes: list[tuple[str, str, str]] = []
levels: list[tuple[str, str]] = []
compatible: list[tuple[str, str]] = []
valid_choices: dict[str, set[str]] = {}
online_url = ""
current_version = None

g_current_version = None


def main(argv: Sequence[str] | None = None) -> None:
    goto_werksdir()
    load_config()
    global g_current_version
    g_current_version = current_version or load_current_version()
    if not g_current_version:
        raise SystemExit("Unable to determine project version")
    main_args = parse_arguments(argv or sys.argv[1:])
    main_args.func(main_args)
