The build of the herbarium specimen database in /app (release 2.0.0, in preparation) fails. Repair it so that it meets the release contract in /app/docs/BUILDING.md: a fresh build with `python3 tools/stratum.py build` must succeed and produce the database, views and exports described in /app/docs/schema.md, and a 1.6.0 database must upgrade to the same schema and rows. The build tool and its configuration are described in /app/docs/stratum.md. Do not change the build tool or the files in /app/seeds. The release will be built from a clean copy of /app with a newer export from the collection system, and other 1.6.0 databases will be upgraded with it.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
