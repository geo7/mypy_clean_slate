from __future__ import annotations

import pathlib
import textwrap

from mypy_clean_slate import __version__, main


def test_version() -> None:
    # Ensure toml version is in sync with package version.
    with open("pyproject.toml") as f:
        pyproject_version = [line for line in f if line.startswith("version = ")]
    assert len(pyproject_version) == 1
    assert pyproject_version[0].strip().split(" = ")[-1].replace('"', "") == __version__


def test_mypy_clean_slate_usage(tmp_path: pathlib.Path) -> None:
    # atm this is a pretty broad usage test - just checks that things are, pretty much,
    # working as expected.
    py_file_before_fix = textwrap.dedent(
        """
    from __future__ import annotations


    def add(*, arg_1, arg_2):
        return arg_1 + arg_2


    add(arg_1=1, arg_2="s") # inline comment.


    def useless_sub(*, arg_1: float, arg_2: Sequence):
        return add(arg_1=arg_1, arg_2="what") - arg_2


    useless_sub(arg_1=3, arg_2=4)
    useless_sub(arg_1=3, arg_2="4")


    def has_preexisting_ignore(arg_1: Sequence):  # type: ignore[name-defined]
        return None
    """,
    ).strip()

    py_file_after_fix = textwrap.dedent(
        """
from __future__ import annotations


def add(*, arg_1, arg_2):  # type: ignore[no-untyped-def]
    return arg_1 + arg_2


add(arg_1=1, arg_2="s")  # type: ignore[no-untyped-call] # inline comment.


def useless_sub(*, arg_1: float, arg_2: Sequence):  # type: ignore[name-defined, no-untyped-def]
    return add(arg_1=arg_1, arg_2="what") - arg_2  # type: ignore[no-untyped-call]


useless_sub(arg_1=3, arg_2=4)
useless_sub(arg_1=3, arg_2="4")


def has_preexisting_ignore(arg_1: Sequence):  # type: ignore[name-defined, no-untyped-def]
    return None
    """.strip(),
    )

    python_file = pathlib.Path(tmp_path, "file_to_check.py")
    python_file.write_text(py_file_before_fix, encoding="utf8")

    # there's probably a much nicer way to write these tests.
    report_output = pathlib.Path(tmp_path, "testing_report_output.txt")
    report_output.write_text(
        main.generate_mypy_error_report(path_to_code=python_file, mypy_flags=[""]),
        encoding="utf8",
    )

    main.add_type_ignores(report_output=report_output)
    assert python_file.read_text(encoding="utf8").strip() == py_file_after_fix


def test_no_duplicate_codes_added(tmp_path: pathlib.Path) -> None:
    """Ensure duplicate ignore messages aren't applied."""
    py_file_before_fix = textwrap.dedent(
        """
    from __future__ import annotations

    object().foo, object().bar
    """,
    ).strip()

    py_file_after_fix = textwrap.dedent(
        """
    from __future__ import annotations

    object().foo, object().bar  # type: ignore[attr-defined]
    """,
    ).strip()

    python_file = pathlib.Path(tmp_path, "file_to_check.py")
    python_file.write_text(py_file_before_fix, encoding="utf8")

    report_output = pathlib.Path(tmp_path, "testing_report_output.txt")
    report_output.write_text(
        main.generate_mypy_error_report(path_to_code=python_file, mypy_flags=[""]),
        encoding="utf8",
    )

    main.add_type_ignores(report_output=report_output)
    assert python_file.read_text(encoding="utf8").strip() == py_file_after_fix


def test_custom_mypy_flags(tmp_path: pathlib.Path) -> None:
    """Ensure custom mypy flags are respected."""
    py_file_before_fix = textwrap.dedent(
        """
    def f(x):
        return x ** 2

    def main() -> int:
        y = f(12)
        return 0

    if __name__ == '__main__':
        raise SystemExit(main())
    """,
    ).strip()

    py_file_after_fix = textwrap.dedent(
        """
    def f(x):
        return x ** 2

    def main() -> int:
        y = f(12)  # type: ignore[no-untyped-call]
        return 0

    if __name__ == '__main__':
        raise SystemExit(main())
    """,
    ).strip()

    python_file = pathlib.Path(tmp_path, "file_to_check.py")
    python_file.write_text(py_file_before_fix, encoding="utf8")

    # there's probably a much nicer way to write these tests.
    report_output = pathlib.Path(tmp_path, "testing_report_output.txt")
    report_output.write_text(
        main.generate_mypy_error_report(
            path_to_code=python_file,
            mypy_flags=["--disallow-untyped-calls"],
        ),
        encoding="utf8",
    )

    main.add_type_ignores(report_output=report_output)
    assert python_file.read_text(encoding="utf8").strip() == py_file_after_fix


def test_remove_used_ignores(tmp_path: pathlib.Path) -> None:
    """Ensure unused ignores raised as errors are removed."""
    py_file_before_fix = textwrap.dedent(
        """
    def f(x : float) -> float:
        return x ** 2  # type: ignore

    def main() -> int:
        x = f(12)  # type: ignore[no-untyped-call]
        y = f("foo")  # type: ignore[no-untyped-call, arg-type]
        z = f("foo")  # type: ignore[arg-type, no-untyped-call]
        return 0

    if __name__ == '__main__':
        raise SystemExit(main())
    """,
    ).strip()

    py_file_after_fix = textwrap.dedent(
        """
    def f(x : float) -> float:
        return x ** 2

    def main() -> int:
        x = f(12)
        y = f("foo")  # type: ignore[arg-type]
        z = f("foo")  # type: ignore[arg-type]
        return 0

    if __name__ == '__main__':
        raise SystemExit(main())
    """,
    ).strip()

    python_file = pathlib.Path(tmp_path, "file_to_check.py")
    python_file.write_text(py_file_before_fix, encoding="utf8")

    # there's probably a much nicer way to write these tests.
    report_output = pathlib.Path(tmp_path, "testing_report_output.txt")
    report_output.write_text(
        main.generate_mypy_error_report(
            path_to_code=python_file,
            mypy_flags=[""],
        ),
        encoding="utf8",
    )
    main.remove_unused_ignores(report_output=report_output)
    main.add_type_ignores(report_output=report_output)
    assert python_file.read_text(encoding="utf8").strip() == py_file_after_fix


def test_hash_in_string_literal() -> None:
    """Ensure that '#' in a string literal is not treated as a comment."""
    line = 'my_string = "hello #world"'
    code, comment = main.extract_code_comment(line=line)
    assert code == line
    assert comment == ""
