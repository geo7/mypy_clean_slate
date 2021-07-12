# Mypy Clean Slate

CLI tool for providing a clean slate for mypy usage within a project

It can be difficult to get a large project to the point where `mypy --strict` can be run on it. Rather than incrementally increasing the severity, either overall or per module, `mypy_clean_slate` enables one to ignore all previous errors so that `mypy --strict` (or similar) can be used immediately.


# Usage

```
usage: main.py [-h] [-n] [-r] [-a] [-o MYPY_REPORT_OUTPUT]

CLI tool for providing a clean slate for mypy usage within a project.

optional arguments:
  -h, --help            show this help message and exit
  -n, --none            Handle missing "-> None" hints on functions.
  -r, --generate_mypy_error_report
                        Generate 'mypy_error_report.txt' in the cwd.
  -a, --add_type_ignore
                        Add "# type: ignore[<error-code>]" to suppress all raised mypy errors.
  -o MYPY_REPORT_OUTPUT, --mypy_report_output MYPY_REPORT_OUTPUT
                        File to save report output to (default is mypy_error_report.txt)
```

See `./tests/test_mypy_clean_slate.py` for an example.

# Issues

## Handling lines with preexisting ignores.

If there are instances of `pylint: disable` or `noqa: ` ignores then these currently have
to be handled separately. eg:

```python
def add(a, b): # pylint: disable=invalid-name
    return a + b
```

would be manually rewritten as

```python
def add(a, b): # type: ignore[no-untyped-def] # pylint: disable=invalid-name
    return a + b
```

# TODO

* handle there being different types of ignores (pylint/flake8/etc) already within the
  code.
