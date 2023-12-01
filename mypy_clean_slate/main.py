from __future__ import annotations

import argparse
import io
import itertools
import pathlib
import re
import subprocess
import sys
import tokenize
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Sequence


T = TypeVar("T")
# contains (file_path, line_number, error_code); file to update, line within that file to
# append `type: ignore[<error-code>]`
FileUpdate = tuple[str, int, str]


def raise_if_none(*, value: T | None) -> T:
    if value is None:
        msg = "None value"
        raise RuntimeError(msg)
    return value


# --- generate mypy report


def generate_mypy_error_report(
    *,
    path_to_code: pathlib.Path,
) -> str:
    """Run mypy and generate report with errors."""
    mypy_command = [
        "mypy",
        f"{str(path_to_code)}",
        "--show-error-codes",
        "--strict",
    ]

    print(f"Generating mypy report using: {' '.join(mypy_command)}")

    # Mypy is likely to return '1' here (otherwise pointless using this script)
    mypy_process = subprocess.run(  # pylint: disable=subprocess-run-check
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
    """Break line into code,comment if necessary.

    When there are lines containing ignores for tooling such as pylint the mypy ignore should be
    placed before the pylint disable. Therefore it's necessary to split lines into code,comment.
    """
    # if '#' isn't in line then there's definitely no trailing code comment.
    if "#" not in line:
        return line, ""

    # generate_tokens wants a "callable returning a single line of input"
    reader = io.StringIO(line).readline

    comment_tokens = [t for t in tokenize.generate_tokens(reader) if t.type == tokenize.COMMENT]

    # If there's an inline comment then only expect a single one.
    if len(comment_tokens) != 1:
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
        error_codes = ", ".join(x[2] for x in grp)
        file_lines = pathlib.Path(file_path).read_text(encoding="utf8").split("\n")

        python_code, python_comment = extract_code_comment(line=file_lines[line_number])
        mypy_ignore = f"# type: ignore[{error_codes}]"

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
    if re.match(r".*error.*\[.*\]$", error_message):
        return True
    return False


def extract_file_line_number_and_error_code(
    *,
    error_report_lines: list[str],
) -> list[FileUpdate]:
    file_updates: list[tuple[str, int, str]] = []
    for error_line in error_report_lines:
        if not line_contains_error(error_message=error_line):
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

    return file_updates


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


# --- Call functions above.


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("CLI tool for providing a clean slate for mypy usage within a project."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        "-o",
        "--mypy_report_output",
        help=("File to save report output to (default is mypy_error_report.txt)"),
    )

    args = parser.parse_args()

    if args.mypy_report_output is None:
        report_output = pathlib.Path("mypy_error_report.txt")
    else:
        report_output = pathlib.Path(args.mypy_report_output)

    if args.generate_mypy_error_report:
        report = generate_mypy_error_report(path_to_code=args.path_to_code)
        report_output.write_text(report, encoding="utf8")

    if args.add_type_ignore:
        add_type_ignores(report_output=report_output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
