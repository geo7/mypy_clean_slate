from __future__ import annotations

import argparse
import itertools
import pathlib
import re
import subprocess
import sys
from typing import Sequence, Tuple, TypeVar

T = TypeVar("T")
# contains (file_path, line_number, error_code); file to update, line within that file to
# append `type: ignore[<error-code>]`
FileUpdate = Tuple[str, int, str]


def raise_if_none(*, value: T | None) -> T:
    if value is None:
        raise RuntimeError("None value")
    return value


# --- generate mypy report


def generate_mypy_error_report() -> str:
    """Run mypy and generate report with errors."""
    print("creating report.")
    # Mypy is likely to return '1' here (otherwise pointless using this script)
    mypy_process = subprocess.run(  # pylint: disable=subprocess-run-check
        [
            "mypy",
            ".",
            "--show-error-codes",
            "--strict",
        ],
        capture_output=True,
    )
    # don't think there's any need to check stderr
    return mypy_process.stdout.decode()


def assert_report_contains_errors(
    *,
    report: Sequence[str],
) -> None:
    success_check = "Success: no issues found in"
    assert not any(report_line.startswith(success_check) for report_line in report), (
        "Generated mypy report contains line starting with: "
        f"{success_check}, so there's probably nothing that needs to be done. "
        "Full report: \n"
        f"{report}"
    )


# --- Add ` # type: ignore[<error-code>]` to lines which throw errors.


def read_mypy_error_report(
    *,
    file_path: pathlib.Path,
) -> list[str]:
    error_lines = file_path.read_text().split("\n")
    # eg: "Found 1 error in 1 file (checked 5 source files)", have no use for this.
    summary_regex = re.compile(r"^Found [0-9]+ errors? in [0-9]+")
    error_lines_no_summary = [
        line for line in error_lines if summary_regex.match(line) is None
    ]
    # typically a '' at the end of the report - any lines which are just '' (or ' ') are
    # of no use though.
    error_lines_no_blank = [line for line in error_lines_no_summary if line.strip()]
    # return list sorted by file path.
    return sorted(error_lines_no_blank)


def update_files(*, file_updates: list[FileUpdate]) -> None:
    # update each line with `# type: ignore[<error-code[s]>]`
    for pth_and_line_num, grp in itertools.groupby(
        file_updates, key=lambda x: (x[0], x[1])
    ):
        fpth, l_num = pth_and_line_num
        error_codes = ", ".join(x[2] for x in grp)
        file_lines = pathlib.Path(fpth).read_text().split("\n")
        file_lines[l_num] = file_lines[l_num] + f" # type: ignore[{error_codes}]"

        new_text = "\n".join(file_lines)
        with open(fpth, "w") as file:
            file.write(new_text)


def extract_file_line_number_and_error_code(
    *, error_lines: list[str]
) -> list[FileUpdate]:
    file_updates = []
    for error_line in error_lines:
        # example error_line format:
        # 'check.py:13: error: \
        # Call to untyped function "main" in typed context [no-untyped-call]'
        file_path, line_number, *_ = error_line.split(":")
        # mypy will report the first line as '1' rather than '0'.
        line_num = int(line_number) - 1

        if re.match(r"^.*\[.*\]$", error_line):
            # this is (should be) a line with a well formed error message.
            error_message = raise_if_none(
                value=re.match(r"^.*\[(.*)\]$", error_line)
            ).group(1)
            file_updates.append((file_path, line_num, error_message))
        else:
            # haven't seen anything else yet, though there might be other error types
            # which need to be handled.
            raise RuntimeError("Not expecting this.")
    return file_updates


def add_type_ignores(
    *,
    report_output: pathlib.Path = pathlib.Path("mypy_error_report.txt"),
) -> None:
    """Add `# type: ignore` to all lines which fail on given mypy command."""
    error_lines = read_mypy_error_report(file_path=report_output)
    assert_report_contains_errors(report=error_lines)

    # process all lines in report.
    file_updates = extract_file_line_number_and_error_code(error_lines=error_lines)
    update_files(file_updates=file_updates)


# --- Call functions above.


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CLI tool for providing a clean slate for mypy usage within a project."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-n",
        "--none",
        help=('Handle missing "-> None" hints on functions.'),
        action="store_true",
    )
    parser.add_argument(
        "-r",
        "--generate_mypy_error_report",
        help=("Generate 'mypy_error_report.txt' in the cwd."),
        action="store_true",
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
        # default="mypy_error_report.txt",
    )

    args = parser.parse_args()

    if args.mypy_report_output is None:
        report_output = pathlib.Path("mypy_error_report.txt")
    else:
        report_output = pathlib.Path(args.mypy_report_output)

    if args.generate_mypy_error_report:
        report = generate_mypy_error_report()
        report_output.write_text(report)

    if args.add_type_ignore:
        add_type_ignores(report_output=report_output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
