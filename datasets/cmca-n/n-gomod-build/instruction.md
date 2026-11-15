The Go module in /app (`wattbill`, a command that prices electricity meter readings with regional tariffs compiled into the program, release 4.2.0 in preparation) does not build on the release builders, and its build has further defects that a successful build does not show. Repair it so that it meets the contract in /app/docs/BUILDING.md, with the program behaving as /app/docs/wattbill.md describes.

The repaired module will be checked from clean copies of /app with Go 1.19 as installed in the image and no network access, building from `vendor/` only: `make test` must pass; `make build COMMIT=...` must give byte-identical binaries in two different directories; `make build GOOS=windows GOARCH=amd64` must work, and the platform files must be selected correctly for the other release targets; a build with a different version in `VERSION` must report it. go.mod, go.sum and `vendor/` will be compared with what `go mod tidy` and `go mod vendor` write from the module mirror in the image. The built program will then be run on meter readings and regions other than the ones in /app, and its output, errors and exit status compared line by line with the expected ones.

You may change go.mod, go.sum, `vendor/` (through the go command), the Makefile and the Go source files that are not tests. Do not change the tests, the tariff tables, the docs, CHANGELOG.md or `VERSION`; do not add, rename or remove files outside `vendor/`; and keep Go and make as installed in the image.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
