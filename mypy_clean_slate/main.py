from __future__ import annotations

import argparse
import io
import itertools
import logging
import pathlib
import re
import shlex
import subprocess
import sys
import textwrap
import tokenize
import warnings
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


T = TypeVar("T")
# contains (file_path, line_number, error_code); file to update, line within that file to
# append `type: ignore[<error-code>]`
FileUpdate = tuple[str, int, str]

log = logging.getLogger(__name__)


DEFAULT_REPORT_FILE = "mypy_error_report.txt"
MYPY_IGNORE_REGEX = re.compile(r"type:\s*ignore(?:\[(?P<error_codes>[^\]]*)\])?")
MYPY_IGNORE_WITH_COMMENT_REGEX = re.compile(r"#\s*type:\s*ignore(?:\[(?P<error_codes>[^\]]*)\])?")


def raise_if_none(*, value: T | None) -> T:
    if value is None:
        msg = "None value"
        raise RuntimeError(msg)
    return value


def generate_mypy_error_report(
    *,
    path_to_code: pathlib.Path,
    mypy_flags: list[str],
) -> str:
    """Run mypy and generate report with errors."""
    no_arguments_passed = (len(mypy_flags) == 0) or ((len(mypy_flags) == 1) and mypy_flags[0] == "")

    if no_arguments_passed:
        # If no flags are passed we just assume we want to get things ready to
        # use with --strict going forwards.
        mypy_command = [
            "mypy",
            f"{str(path_to_code)}",
            # Want error codes output from mypy to re-add in ignores.
            "--show-error-codes",
            # pretty output will format reports in an unexpected way for parsing.
            "--no-pretty",
            "--strict",  # Default is to assume we want to aim for --strict.
        ]
    else:
        mypy_command = [
            "mypy",
            f"{str(path_to_code)}",
            # Leaving --show-error-codes and --no-pretty as the error codes are
            # necessary to enable parsing the report output and writing back to
            # the files. --no-pretty is needed as, if there's a config setting
            # to use pretty the report output is altered and not parsed
            # properly.
            "--show-error-codes",
            "--no-pretty",
            *mypy_flags,
        ]

    print(f"Generating mypy report using: {' '.join(mypy_command)}")

    # Mypy is likely to return '1' here (otherwise pointless using this script)
    mypy_process = subprocess.run(
        mypy_command,
        capture_output=True,
    )
    # don't think there's any need to check stderr
    return mypy_process.stdout.decode()


def exit_if_no_errors(
    *,
    report: Sequence[str],
) -> None:
    # A report with no errors will contain this substring, so if this substring
    # exists there's nothing to be done.
    success_check = "Success: no issues found in"
    if any(report_line.startswith(success_check) for report_line in report):
        msg = (
            "Generated mypy report contains line starting with: "
            f"{success_check}, so there's probably nothing that needs to be done. "
            "Full report: \n"
            f"{report}"
        )
        raise SystemExit(msg)


# --- Add ` # type: ignore[<error-code>]` to lines which throw errors.


def extract_code_comment(*, line: str) -> tuple[str, str]:
    """
    Break line into code,comment if necessary.

    When there are lines containing ignores for tooling such as pylint the mypy ignore should be
    placed before the pylint disable. Therefore it's necessary to split lines into code,comment.
    """
    # if '#' isn't in line then there's definitely no trailing code comment.
    if "#" not in line:
        return line, ""

    # generate_tokens wants a "callable returning a single line of input"
    reader = io.StringIO(line).readline

    # TODO(geo7): Handle multiline statements properly.
    # https://github.com/geo7/mypy_clean_slate/issues/114
    try:
        comment_tokens = [t for t in tokenize.generate_tokens(reader) if t.type == tokenize.COMMENT]
    except tokenize.TokenError as er:
        warnings.warn(f"TokenError encountered: {er} for line {line}.", UserWarning, stacklevel=2)
        return line, ""

    # Line doesn't contain a comment
    if len(comment_tokens) == 0:
        return line, ""
    # If there's an inline comment then only expect a single one.
    if len(comment_tokens) > 1:
        msg = f"Expected there to be a single comment token, have {len(comment_tokens)}"
        raise ValueError(
            msg,
        )

    comment_token = comment_tokens[0]
    python_code = line[0 : comment_token.start[1]]
    python_comment = line[comment_token.start[1] :]
    return python_code, python_comment


def read_mypy_error_report(
    *,
    path_to_error_report: pathlib.Path,
) -> list[str]:
    error_report_lines = path_to_error_report.read_text().split("\n")
    # eg: "Found 1 error in 1 file (checked 5 source files)", have no use for this.
    summary_regex = re.compile(r"^Found [0-9]+ errors? in [0-9]+")
    error_report_lines_no_summary = [
        line for line in error_report_lines if summary_regex.match(line) is None
    ]
    # typically a '' at the end of the report - any lines which are just '' (or ' ') are
    # of no use though.
    error_report_lines_filtered = [line for line in error_report_lines_no_summary if line.strip()]
    # return list sorted by file path (file path is at the start of all lines in error report).
    return sorted(error_report_lines_filtered)


def update_files(*, file_updates: list[FileUpdate]) -> None:
    # update each line with `# type: ignore[<error-code[s]>]`
    for pth_and_line_num, grp in itertools.groupby(
        file_updates,
        key=lambda x: (x[0], x[1]),
    ):
        file_path, line_number = pth_and_line_num
        error_codes = {x[2] for x in grp}
        file_lines = pathlib.Path(file_path).read_text(encoding="utf8").split("\n")

        python_code, python_comment = extract_code_comment(line=file_lines[line_number])

        if python_comment:
            error_codes |= _get_codes_from_line(python_comment)
            python_comment = MYPY_IGNORE_WITH_COMMENT_REGEX.sub("", python_comment)

        # In some cases it's possible for there to be multiple spaces added
        # before '# type: ...' whereas we'd like to ensure only two spaces are
        # added.
        python_code = python_code.rstrip()
        mypy_ignore = f"# type: ignore[{', '.join(sorted(error_codes))}]"

        if python_comment:
            line_update = f"{python_code}  {mypy_ignore} {python_comment}"
        else:
            line_update = f"{python_code}  {mypy_ignore}"

        # check to see if the line contains a trailing comment already - it it does then this line
        # needs to be handled separately.
        file_lines[line_number] = line_update.rstrip(" ")
        new_text = "\n".join(file_lines)
        with open(file_path, "w", encoding="utf8") as file:
            file.write(new_text)


def line_contains_error(*, error_message: str) -> bool:
    """Ensure that the line contains an error message to extract."""
    return bool(re.match(r".*error.*\[.*\]$", error_message))


def line_is_unused_ignore(*, error_message: str) -> bool:
    """
    Return true if line relates to an unused ignore.

    These are treated differently to other messages, in this case the current
    type: ignore needs to be removed rather than adding one.
    """
    return bool(re.match('.*unused.ignore.*|Unused "type: ignore', error_message))


def extract_file_line_number_and_error_code(
    *,
    error_report_lines: list[str],
) -> list[FileUpdate]:
    file_updates: list[FileUpdate] = []
    for error_line in error_report_lines:
        if (not line_contains_error(error_message=error_line)) or line_is_unused_ignore(
            error_message=error_line,
        ):
            continue

        # Call to untyped function "main" in typed context [no-untyped-call]'
        file_path, line_number, *_ = error_line.split(":")
        # mypy will report the first line as '1' rather than '0'.
        line_num = int(line_number) - 1
        if error_message := re.match(r"^.*\[(.*)\]$", error_line):
            file_updates.append((file_path, line_num, error_message.group(1)))
        else:
            # haven't seen anything else yet, though there might be other error types which need to
            # be handled.
            msg = f"Unexpected line format: {error_line}"
            raise RuntimeError(msg)

    # Ensure that the returned updates are unique. For example we might have
    # file_updates as something like  [('f.py', 0, 'attr-defined'), ('f.py', 0,
    # 'attr-defined')] given code such as object().foo, object().bar - leading
    # to igore[attr-defined, attr-defined] instead of ignore[attr-defined]
    return sorted(set(file_updates), key=lambda x: (x[0], x[1], x[2]))


def add_type_ignores(
    *,
    report_output: pathlib.Path,
) -> None:
    """Add `# type: ignore` to all lines which fail on given mypy command."""
    error_report_lines = read_mypy_error_report(path_to_error_report=report_output)
    exit_if_no_errors(report=error_report_lines)
    # process all lines in report.
    file_updates = extract_file_line_number_and_error_code(
        error_report_lines=error_report_lines,
    )
    update_files(file_updates=file_updates)


def _parse_codes(error_codes: str) -> Iterable[str]:
    for c in error_codes.split(","):
        yield c.strip()


def _get_codes_from_line(line: str) -> set[str]:
    error_codes_found: set[str] = set()
    for mo in MYPY_IGNORE_WITH_COMMENT_REGEX.finditer(line):
        if error_codes := mo.group("error_codes"):
            error_codes_found.update(_parse_codes(error_codes))
    return error_codes_found


def remove_unused_ignores(*, report_output: pathlib.Path) -> None:
    """Remove ignores which are no longer needed, based on report output."""
    report_lines = report_output.read_text().split("\n")
    ignores_lines: list[FileUpdate] = sorted(
        [
            (line.split(":", 2)[0], int(line.split(":", 2)[1]), line.split(":", 2)[2])
            for line in report_lines
            if line_is_unused_ignore(error_message=line)
        ],
        key=lambda x: (x[0], x[1]),
    )

    for file_path, grp in itertools.groupby(ignores_lines, key=lambda x: x[0]):
        _grp = sorted(grp)
        file_lines = pathlib.Path(file_path).read_text().split("\n")
        for _, line_n, error_code in _grp:
            _line_n = int(line_n) - 1  # Decrease by 1 as mypy indexes from 1 not zero

            mo = MYPY_IGNORE_REGEX.search(error_code)
            if mo and (error_codes := mo.group("error_codes")):
                unused_ignores: set[str] = set(_parse_codes(error_codes))
            else:
                unused_ignores = set()

            orig_line = file_lines[_line_n]

            if (
                unused_ignores
                and (ignores_found := _get_codes_from_line(orig_line))
                and (ignores_to_keep := sorted(ignores_found - unused_ignores))
            ):
                file_lines[_line_n] = MYPY_IGNORE_WITH_COMMENT_REGEX.sub(
                    f"# type: ignore[{', '.join(ignores_to_keep)}]", orig_line
                ).rstrip()
            else:
                file_lines[_line_n] = MYPY_IGNORE_WITH_COMMENT_REGEX.sub("", orig_line).rstrip()

        # Write updated file out.
        with open(file_path, "w", encoding="utf8") as file:
            file.write("\n".join(file_lines))


# --- Call functions above.
def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(
            """
            CLI tool for providing a clean slate for mypy usage within a project.

            Default expectation is to want to get a project into a state that it
            will pass mypy when run with `--strict`, if this isn't the case custom
            flags can be passed to mypy via the `--mypy_flags` argument.
            """,
        ).strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # Hard-coding this as the usage is dynamic otherwise, based on where the
        # parser is defined. I'm using print_help() to generate the output of
        # --help into the README so need this to be consistent. Otherwise,
        # creating the parser from within mod.py will put mod.py into the usage
        # rather than the script entry point for the CLI.
        usage="mypy_clean_slate [options]",
    )
    parser.add_argument(
        "-r",
        "--generate_mypy_error_report",
        help=("Generate 'mypy_error_report.txt' in the cwd."),
        action="store_true",
    )

    parser.add_argument(
        "-p",
        "--path_to_code",
        help=("Where code is that needs report generating for it."),
        default=pathlib.Path("."),
    )

    parser.add_argument(
        "-a",
        "--add_type_ignore",
        help=('Add "# type: ignore[<error-code>]" to suppress all raised mypy errors.'),
        action="store_true",
    )

    parser.add_argument(
        "--remove_unused",
        help=(
            'Remove unused instances of "# type: ignore[<error-code>]" '
            "if raised as an error by mypy."
        ),
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "-o",
        "--mypy_report_output",
        help=f"File to save report output to (default is {DEFAULT_REPORT_FILE})",
    )

    parser.add_argument(
        "--mypy_flags",
        type=str,
        default="",
        help=(
            "Custom flags to pass to mypy (provide them as a single string, "
            "default is to use --strict)"
        ),
    )

    return parser


def main() -> int:
    logging.basicConfig(level=logging.DEBUG)
    parser = create_parser()
    args = parser.parse_args()

    if args.mypy_report_output is None:
        report_output = pathlib.Path(DEFAULT_REPORT_FILE)
    else:
        report_output = pathlib.Path(args.mypy_report_output)

    if args.generate_mypy_error_report:
        report = generate_mypy_error_report(
            path_to_code=args.path_to_code,
            mypy_flags=shlex.split(args.mypy_flags),
        )
        report_output.write_text(report, encoding="utf8")

    if args.remove_unused:
        remove_unused_ignores(report_output=report_output)

    if args.add_type_ignore:
        add_type_ignores(report_output=report_output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
