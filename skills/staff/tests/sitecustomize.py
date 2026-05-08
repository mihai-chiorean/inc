"""Coverage shim for subprocess-invoked scripts.

When COVERAGE_PROCESS_START is set, the `coverage` package looks for
sitecustomize.py on PYTHONPATH and calls coverage.process_startup() if
present. This file exists only so subprocess-launched test scripts
record coverage data into .coverage.<pid> files alongside the parent.

After the tests run, `coverage combine` merges all .coverage.* files.
"""

try:
    import coverage  # type: ignore[import]
    coverage.process_startup()
except ImportError:
    pass
