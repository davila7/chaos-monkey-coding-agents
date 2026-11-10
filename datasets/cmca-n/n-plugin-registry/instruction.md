The `xport` tool in /app writes tabular datasets in eight output formats, all implemented in the single module /app/xport/formats.py. Replace that module with the `xport/formats/` package described in /app/docs/plugins.md: a registry, the plugin interface it defines, and one plugin module per format. Follow every rule in that document: layout, registration and discovery, name collisions, listing order, option checking and its messages, the public API, and unchanged behavior. What each format writes is in /app/docs/formats.md; the command line is in /app/docs/cli.md. From /app, the unit tests run with:

    python -m unittest discover -s tests -t .

The result will be compared with the original module on datasets, format names, aliases and options other than the ones in /app/samples and /app/tests, so output must stay byte for byte the same for any input, not only for the files you can see. Reviewers will also add format plugins of their own to check the registry. Do not change anything under /app/tests, /app/samples or /app/docs.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
