# Building wattbill

wattbill is one Go module, `scm.tallow.lan/energy/wattbill`: the command in `cmd/wattbill` and
three internal packages (`internal/billing`, `internal/tariff`, `internal/buildinfo`). This file
is the build contract: the release builders and CI build exactly as described here.

## 1. Toolchain

- Go 1.19 as packaged by Debian 12 (`golang-1.19-go`), with `CGO_ENABLED=0`. Every package is
  pure Go; nothing needs a C compiler.
- GNU make. The Makefile is the only supported entry point.
- The builders have no network access. Dependencies are built from `vendor/`.

## 2. go.mod

- The module path is `scm.tallow.lan/energy/wattbill`. It was `scm.tallow.lan/tools/wattbill`
  before 4.0.0; nothing may refer to the old path.
- The `go` directive is `1.19`, the Go release of the builders and the oldest one supported.
  go.mod has no `toolchain` line: Go 1.19 does not know the directive and stops at it.
- Required modules, each pinned to one release:
  - `scm.tallow.lan/kit/csvq` v1.6.0. Earlier releases neither skip the byte order mark of the
    portal exports nor trim padded fields (CHANGELOG 4.2.0).
  - `scm.tallow.lan/kit/money` v1.2.0. v1.3.0 groups thousands with commas, which the bill
    format does not allow (docs/wattbill.md).
- No `replace` or `exclude` directives.

## 3. Vendoring

- `vendor/` holds exactly what `go mod vendor` writes for go.mod. Vendored files are never edited
  by hand.
- go.mod and go.sum are tidy: `go mod tidy` changes neither.
- Released versions of the `scm.tallow.lan/kit` modules are in the read-only module mirror at
  `file:///srv/gomirror` (the `GOPROXY` of the build image, with `GOSUMDB=off`). The mirror is
  used only to update `vendor/`; builds never read it.

## 4. Make targets

- `make build` writes `bin/wattbill`, or `bin/wattbill.exe` when `GOOS=windows`.
- Variables: `GOOS` and `GOARCH` (default: the host), `COMMIT` (default `unknown`).
- The version is the first line of `VERSION`. `make build` stamps the version and `COMMIT` into
  `internal/buildinfo` with `-ldflags -X`, so that `wattbill --version` prints
  `wattbill VERSION (commit COMMIT)`. A build without the Makefile prints
  `wattbill devel (commit unknown)`.
- `make test` runs `go test ./...`, which also runs the vet checks of `go test`.

## 5. Reproducible builds

- The same source tree, `VERSION` and `COMMIT` give a byte-identical binary whatever directory the
  tree is checked out in.
- No binary contains the path of the directory it was built in.

## 6. Platforms

- Release targets: linux/amd64, linux/arm64, darwin/arm64, freebsd/amd64 and windows/amd64.
- `cmd/wattbill/progress_unix.go` prints progress on SIGUSR1 and is built for every Unix system.
  `cmd/wattbill/progress_windows.go` is the Windows stub.

## 7. Tariff tables

- The tables in `internal/tariff/tables` are compiled in with `go:embed`. Every `.csv` file there
  is embedded and loaded in file name order: `_base.csv` holds every region, and each other
  table overrides or adds regions.
- `wattbill regions` lists every region with the table it comes from.
