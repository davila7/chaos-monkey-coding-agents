The release build of `tidecalc` in /app is broken: the wheel and the sdist built from the repository do not match what a release must contain. Repair the packaging so that a build passes every rule in /app/docs/packaging.md. The build backend kept in the repository (`backend/kiln.py`) and its configuration are described in /app/docs/kiln.md. From /app, the wheel and the sdist are built with:

    python -m pip wheel --no-build-isolation --no-deps --no-index -w dist .
    python tools/build_sdist.py dist

`tools/smoke.sh` is a quick check of a build; it does not cover the whole checklist. Do not change the backend or what the package code does. The release will be built from /app with an unmodified copy of the backend, installed into a fresh environment and checked against the full checklist, including commands, formats, translations and stations that the smoke check does not use.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
