# Mypy Clean Slate

CLI tool for providing a clean slate for mypy usage within a project

## Motivation

It can be difficult to get a large project to the point where `mypy --strict` can be run on it. Rather than incrementally increasing the severity of mypy, either overall or per module, `mypy_clean_slate` enables one to ignore all previous errors so that `mypy --strict` (or similar) can be used almost immediately. This enables all code written from that point on to be checked with `mypy --strict` (or whichever flags are preferred), gradually removing the `type: ignore` comments from that point onwards.

Often running `mypy_clean_slate` will cover all errors cleanly in a single pass, but there are cases when not all error output is generated first time, and it can be necessary to run a couple of times, checking the diffs. Example of this scenario is given.

`mypy_clean_slate` works by parsing the output of `mypy --strict --show-error-codes`, and adding the relevant `type: ignore[code]` to each line. Only errors from the report are considered, notes are not handled. Meaning something such as `error: Function is missing a type annotation  [no-untyped-def]` will have `# type: ignore[no-untyped-def]` appended to the end of the line, whereas `note: (Skipping most remaining errors due to unresolved imports or missing stubs; fix these first)` will be ignored.


# Usage

```
usage: mypy_clean_slate [-h] [-r] [-a] [-o MYPY_REPORT_OUTPUT]

CLI tool for providing a clean slate for mypy usage within a project.

optional arguments:
  -h, --help            show this help message and exit
  -r, --generate_mypy_error_report
                        Generate 'mypy_error_report.txt' in the cwd.
  -a, --add_type_ignore
                        Add "# type: ignore[<error-code>]" to suppress all
                        raised mypy errors.
  -o MYPY_REPORT_OUTPUT, --mypy_report_output MYPY_REPORT_OUTPUT
                        File to save report output to (default is
                        mypy_error_report.txt)
```

See `./tests/test_mypy_clean_slate.py` for a basic, self contained, before/after example.



# Examples

## Simple example

Given a project with only:

```txt
➜  simple_example git:(master) ✗ tree
.
`-- simple.py

0 directories, 1 file
```

Containing:

```python
# simple.py
def f(x):
    return x + 1
```

The report can be generated, and `simple.py` updated, using `mypy_clean_slate -ra`, resulting in:


```python
def f(x):  # type: ignore[no-untyped-def]
    return x + 1
```

And `mypy --strict` will now pass.

## Project example, using `pingouin`

Project `pingouin` is located at: https://github.com/raphaelvallat/pingouin, and commit `ea8b5605a1776aaa0e89dd5c0e3df4320950fb38` is used for this example. `mypy_clean_slate` needs to be run a couple of times here.

First, generate report and apply `type: ignore[<error code>]`

```sh
mypy_clean_slate -ra
```

Looking at a subset of `git diff`:

```diff

(venv) ➜ pingouin git:(master) ✗ git diff | grep 'type' | head
+import sphinx_bootstrap_theme # type: ignore[import]
+from outdated import warn_if_outdated # type: ignore[import]
+import numpy as np # type: ignore[import]
+from scipy.integrate import quad # type: ignore[import]
+ from scipy.special import gamma, betaln, hyp2f1 # type: ignore[import]
+ from mpmath import hyp3f2 # type: ignore[import]
+ from scipy.stats import binom # type: ignore[import]
+import numpy as np # type: ignore[import]
+from scipy.stats import norm # type: ignore[import]
+import numpy as np # type: ignore[import]
```

Changes are added and committed with message `'mypy_clean_slate first pass'` (commit message used makes no functional difference), and the report re-generated:

```bash
mypy_clean_slate -r
```

Which reports `Found 1107 errors in 39 files (checked 42 source files)`. So, re-running `mypy_clean_slate`

```bash
mypy_clean_slate -a
```

And looking again at the diff:

```diff

(venv) ➜ pingouin git:(master) ✗ gd | grep 'type' | head
+latex_elements = { # type: ignore[var-annotated]
+def setup(app): # type: ignore[no-untyped-def]
@@ -27,4 +27,4 @@ from outdated import warn_if_outdated # type: ignore[import]
+set_default_options() # type: ignore[no-untyped-call]
+def _format_bf(bf, precision=3, trim='0'): # type: ignore[no-untyped-def]
if type(bf) == str:
+def bayesfactor_ttest(t, nx, ny=None, paired=False, tail='two-sided', r=.707): # type: ignore[no-untyped-def]
+ def fun(g, t, n, r, df): # type: ignore[no-untyped-def]
+def bayesfactor_pearson(r, n, tail='two-sided', method='ly', kappa=1.): # type: ignore[no-untyped-def]
+ def fun(g, r, n): # type: ignore[no-untyped-def]
```

 Committing these with `'mypy_clean_slate second pass'`, and re-running `mypy_clean_slate -r` outputs the following:

```txt
(venv) ➜ pingouin git:(master) ✗ cat mypy_error_report.txt
Success: no issues found in 42 source files
```

Can now rebase / amend commits as necessary, but could now update CI/pre-commit or whatever to use `mypy --strict` (or a subset of its flags) going forwards.


# Handling of existing comments and `pylint`

Lines which contain existing comments such as:

```python
def ThisFunction(something): # pylint: disable=invalid-name
    return f"this is {something}"
```

Will be updated to:

```python
def ThisFunction(something):   # type: ignore[no-untyped-def] # pylint: disable=invalid-name
    return f"this is {something}"
```

As the `type:` comment needs to precede pylints.

# Issues

## Generating report

The report generation is pretty straightforward, `mypy . --strict --show-error-codes`, so might not be worth having as part of this script. The user can generate the report to a text file and just pass the path to that as an argument.

## Handling `-> None`

Report output for functions which don't return is pretty consistent, so these could be automated if considered worth it.

## Integration with other tooling

I've tried to consider `pylint` comments, but no doubt there are many other arguments for different tools which aren't taken into consideration.
