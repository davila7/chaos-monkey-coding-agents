The `orbis-postal` repository in /app (release 3.2.0, in preparation) does not package correctly: the build fails, and the packaging has further defects that a successful build does not show. Repair it so that the release passes every item of the checklist in /app/docs/packaging.md. The release is built offline from a clean copy of /app with `python -m build --no-isolation` (the sdist, then the wheel from the unpacked sdist), and a development wheel built with `python -m pip wheel --no-build-isolation --no-deps --no-index -w dist .` must have the same content. Both will be installed into fresh environments and checked with commands, records and plugins other than the ones in /app/tests.

Change the packaging, not the program: do not change what the code does, the data files, the tests, the docs or `tools/`, and keep the setuptools backend and the build tools installed in the image.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
