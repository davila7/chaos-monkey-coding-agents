# Deploy tool

Every run of the deploy tool writes a record to `/app/deploy/records/<id>.rec`. Record ids increase with each run.

Record fields:

- `started_at`: when the run began, in the requesting operator's local time with its UTC offset. Operators work from different time zones. Service logs use UTC.
- `mode`: `apply` stops and restarts services on the target hosts. `dry-run` resolves configuration and checks it, but stops and starts nothing and writes nothing to service logs.
- `environment`: the environment for that run. This is the value of `${env}` while the run resolves configuration.
- `hosts`: the hosts the run targets, comma separated, or `all` for every host of the environment as listed in /app/etc/fleet.conf.
- `config_rev`: the configuration revision the run asked the hosts to load. See status-service.md for what a host actually loaded.
- `release`: the release being rolled out.

## Apply runs

On each target host, services are handled one at a time in alphabetical order of their names. For each service the deploy tool stops the old process if one is running, then starts the new one unless the service is disabled. Services later in the order keep running their old process, with the listeners it already holds, until their turn comes.

A service that cannot open one of its listeners logs `startup aborted`, closes any listener it already opened and exits. It stays down until a later run starts it. The run continues with the next service.

When a listener's port is still held by the old process of the same service, which happens while that process finishes closing, the new process logs a bind warning and retries. A retry that ends in `ready` is a successful start.

## Logs

Service logs are in /app/logs. `<service>.log` is the current file, `<service>.log.1` the one before it and `<service>.log.2.gz` the oldest kept one (gzip). Older files are deleted. Log lines do not carry ports.
