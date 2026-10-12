#!/usr/bin/env python3
"""Builds the /app tree for this environment into the directory given as argv[1].

The output depends only on SEED. The script resolves every configuration the way
docs/config-notes.md describes, replays every apply run on every host, and asserts
that the planned story holds before it writes anything.
"""
import gzip
import io
import json
import os
import posixpath
import random
import shutil
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 7311
GEN = Path(__file__).resolve().parent
HOST = "app-07"
HOST_ENV = "prod-b"
UTC = timezone.utc

# Planned outcome; the replay below must reproduce exactly this.
EXPECT_DEPLOY = "d-1194"
EXPECT_FAILURES = [
    ("geo", "admin", 9512, "ingest"),
    ("tagging", "admin", 9446, "recommend"),
]

SERVICES = [
    ("gateway", "edge", 10, "public HTTP entry point"),
    ("auth", "edge", 12, "token issuing and validation"),
    ("session", "edge", 14, "session store front end"),
    ("router", "edge", 16, "internal request routing"),
    ("callbacks", "edge", 18, "outbound partner callbacks"),
    ("geo", "edge", 20, "address and region lookup"),
    ("tagging", "edge", 22, "item tags and labels"),
    ("ratings", "edge", 24, "star ratings"),
    ("reviews", "edge", 26, "written reviews"),
    ("catalog", "core", 10, "product catalog"),
    ("ledger", "core", 12, "double entry ledger"),
    ("billing", "core", 14, "invoices and charges"),
    ("pricing", "core", 16, "price rules"),
    ("recommend", "core", 18, "recommendations"),
    ("inventory", "core", 20, "stock levels"),
    ("cart", "core", 22, "shopping carts"),
    ("checkout", "core", 24, "order placement"),
    ("profile", "core", 26, "customer profiles"),
    ("search", "core", 28, "product search index"),
    ("quota", "core", 30, "per tenant quotas"),
    ("metrics", "core", 32, "metrics aggregation"),
    ("ingest", "worker", 12, "partner feed ingestion"),
    ("notify", "worker", 14, "notification fan out"),
    ("mailer", "worker", 16, "outbound email"),
    ("sms", "worker", 18, "outbound text messages"),
    ("push", "worker", 20, "mobile push"),
    ("scheduler", "worker", 22, "delayed jobs"),
    ("fraud", "worker", 24, "fraud scoring"),
    ("tax", "worker", 26, "tax calculation"),
    ("inbox", "worker", 28, "customer inbox"),
    ("thumbnail", "media", 10, "image thumbnails"),
    ("transcode", "media", 12, "video transcoding"),
    ("media", "media", 14, "media storage front end"),
    ("feed", "media", 16, "activity feed"),
    ("export", "batch", 10, "data exports"),
    ("report", "batch", 12, "scheduled reports"),
    ("archive", "batch", 14, "cold storage archiver"),
    ("backup", "batch", 16, "database backups"),
    ("reindex", "batch", 18, "search reindexing"),
    ("ledger-close", "batch", 20, "daily ledger close"),
]
SVC_NAMES = sorted(s[0] for s in SERVICES)
SVC_PROFILE = {s[0]: s[1] for s in SERVICES}
SVC_OFFSET = {s[0]: s[2] for s in SERVICES}
SVC_DESC = {s[0]: s[3] for s in SERVICES}
SVC_ADMIN = {s[0]: 9800 + 2 * i for i, s in enumerate(SERVICES)}
PROFILE_BASE = {"edge": 9300, "core": 9400, "worker": 9500, "batch": 9600, "media": 9700}
PROFILE_DESC = {
    "edge": "services that terminate client traffic",
    "core": "stateful services behind the gateway",
    "worker": "queue consumers",
    "media": "media pipeline",
    "batch": "scheduled batch jobs",
}

FLEET = {
    "prod-a": ["app-01", "app-02", "app-03", "app-04"],
    "prod-b": ["app-05", "app-06", "app-07", "app-08"],
    "prod-c": ["app-09", "app-10", "app-11", "app-12"],
    "stage": ["stg-01", "stg-02"],
    "qa": ["qa-01"],
    "perf": ["perf-01"],
    "dr-east": ["dr-01", "dr-02"],
}
HOST_ENVS = {h: e for e, hs in FLEET.items() for h in hs}
ALL_HOSTS = sorted(HOST_ENVS)
REGIONS = {"prod-a": "eu-west", "prod-b": "eu-central", "prod-c": "us-east", "stage": "eu-west",
           "qa": "eu-west", "perf": "us-east", "dr-east": "us-east"}

TEAMS = ["team-orbit", "team-harbor", "team-lumen", "team-quarry", "team-sable", "team-tundra", "team-vesper"]
FLAGS = ["fast-path", "lazy-index", "bulk-api", "v2-pricing", "geo-routing", "audit-trail", "soft-delete",
         "async-write", "dual-read", "edge-cache", "strict-schema", "warm-start"]

KEY_POOL = {
    "drain_s": [5, 10, 15, 20, 30, 45, 60],
    "cache_ttl_s": [30, 60, 120, 300, 600, 900, 1800],
    "trace_sample": ["0.01", "0.02", "0.05", "0.1", "0.25"],
    "pool_size": [4, 8, 12, 16, 24, 32],
    "read_replica": ["on", "off"],
    "request_timeout_ms": [500, 800, 1200, 2500, 4000, 8000],
    "max_body_kb": [64, 128, 256, 512, 1024, 4096],
    "log_level": ["debug", "info", "warn"],
    "retry_budget": [0, 1, 2, 3, 5],
    "circuit_open_ms": [1000, 2000, 5000, 10000, 30000],
    "queue_depth": [64, 128, 256, 512, 2048],
    "batch_size": [10, 50, 100, 250, 500],
    "keepalive_s": [15, 30, 60, 120],
    "rate_limit_rps": [50, 100, 200, 500, 1000, 5000],
    "idle_timeout_s": [30, 60, 90, 300],
    "worker_threads": [2, 4, 8, 16, 32],
    "warmup_s": [0, 5, 10, 30],
    "shard_count": [1, 2, 4, 8, 16],
    "tls_profile": ["modern", "intermediate", "compat-2019"],
    "compress": ["gzip", "br", "off"],
    "dns_ttl_s": [5, 30, 60, 300],
    "slow_log_ms": [100, 250, 500, 1000, 2000],
    "heap_mb": [256, 512, 768, 1024, 2048, 4096],
    "gc_mode": ["throughput", "latency", "balanced"],
    "health_interval_s": [2, 5, 10, 15],
    "upstream_pool": ["pool-a", "pool-b", "pool-c", "pool-shared"],
    "cache_mb": [64, 128, 256, 512, 1024],
    "max_conns": [256, 512, 1024, 4096],
    "max_inflight": [16, 32, 64, 128, 256],
    "hedge_after_ms": [0, 50, 100, 250],
    "jitter_ms": [0, 10, 25, 100],
    "probe_path": ["/healthz", "/readyz", "/status"],
    "sticky_sessions": ["on", "off"],
    "lb_policy": ["round-robin", "least-conn", "ring-hash"],
    "backoff_ms": [50, 100, 200, 500, 1000],
    "outlier_eject_pct": [0, 10, 20, 50],
    "buffer_kb": [16, 32, 64, 256],
    "flush_interval_ms": [100, 250, 500, 1000],
    "ack_timeout_ms": [1000, 3000, 5000, 15000],
    "spill_dir": ["/var/spill", "/scratch/spill", "/tmp/spill"],
}
NOISE_KEYS = sorted(KEY_POOL)


def pick_value(rng, key):
    if key == "feature_flags":
        return ",".join(sorted(rng.sample(FLAGS, rng.randint(1, 3))))
    return str(rng.choice(KEY_POOL[key]))


# ------------------------------------------------------------------ config model


class Conf:
    def __init__(self, header, top, sections):
        self.header = header
        self.top = top
        self.sections = sections

    def render(self):
        out = list(self.header) + [""] + list(self.top)
        for name, lines in self.sections:
            out += ["", f"[{name}]"] + list(lines)
        return "\n".join(out).rstrip("\n") + "\n"

    def blocks(self, name):
        return [lines for n, lines in self.sections if n == name]

    def set_key(self, name, key, value):
        """Sets key in the first block of section name, adding the line if absent."""
        blk = self.blocks(name)[0]
        for i, line in enumerate(blk):
            if line.split("=")[0].strip() == key and not line.startswith("#"):
                blk[i] = f"{key} = {value}"
                return
        blk.append(f"{key} = {value}")


def section_lines(rng, svc, n_min, n_max):
    team = rng.choice(TEAMS)
    lines = [f"# {svc}: owner {team}, reviewed 2026-01-{rng.randint(5, 28):02d}"]
    if n_max > 10:
        lines.append(f"# runbook ops/runbooks/{svc}.md, pager {team}-oncall")
    keys = rng.sample(NOISE_KEYS + ["feature_flags"], rng.randint(n_min, n_max))
    for k in keys:
        lines.append(f"{k} = {pick_value(rng, k)}")
    return lines


class SafePorts:
    """Hands out ports that no planned listener uses, so incidental moves never collide."""

    def __init__(self):
        self.offset = {p: 60 for p in PROFILE_BASE}
        self.admin = 9881

    def next_offset(self, profile):
        self.offset[profile] += 1
        return self.offset[profile]

    def next_admin(self):
        self.admin += 2
        return self.admin


def base_config(rng, safe):
    cfg = {}
    for prof, base in PROFILE_BASE.items():
        header = [f"# Profile: {prof} ({PROFILE_DESC[prof]})."]
        top = [f"port_base = {base}", f"log_level = {rng.choice(['info', 'warn'])}"]
        if prof == "batch":
            top += ["include = ../shared/batch-window.conf", "include = ../hosts/${host}.conf"]
        elif prof == "media":
            top += ["include = ../shared/limits.conf", "include = ../hosts/${host}.conf",
                    "include = ../environments/${env}.conf"]
        else:
            top += ["include = ../shared/limits.conf", "include = ../environments/${env}.conf",
                    "include = ../hosts/${host}.conf"]
        members = [s for s in SVC_NAMES if SVC_PROFILE[s] == prof]
        sections = [[s, section_lines(rng, s, 2, 5)] for s in rng.sample(members, max(1, len(members) // 2))]
        cfg[f"profiles/{prof}.conf"] = Conf(header, top, sections)

    for env, hosts in FLEET.items():
        header = [f"# Environment overlay: {env}",
                  f"# Hosts: {', '.join(hosts)} (see /app/etc/fleet.conf)."]
        top = [f"region = {REGIONS[env]}", f"log_level = {rng.choice(['info', 'warn'])}",
               f"trace_sample = {pick_value(rng, 'trace_sample')}", f"tls_profile = {pick_value(rng, 'tls_profile')}"]
        order = list(SVC_NAMES)
        rng.shuffle(order)
        sections = [[s, section_lines(rng, s, 28, 41)] for s in order]
        conf = Conf(header, top, sections)
        for s in rng.sample(SVC_NAMES, 3):
            if s in ("tagging", "recommend", "geo", "ingest", "ratings"):
                continue
            if rng.random() < 0.5:
                conf.set_key(s, "port_offset", safe.next_offset(SVC_PROFILE[s]))
            else:
                conf.set_key(s, "admin_port", safe.next_admin())
        if env in ("perf", "qa"):
            conf.set_key("metrics", "enabled", "false")
        if env == "prod-b":
            conf.set_key("tagging", "admin_port", 9436)
            conf.set_key("ratings", "enabled", "false")
            conf.set_key("ratings", "admin_port", 9446)
            conf.blocks("search")[0].append("include = ../overrides/search-canary.conf")
        for s in rng.sample(SVC_NAMES, 6):
            conf.sections.append([s, [f"# amendment r03{rng.randint(10, 79)}"] + section_lines(rng, s, 1, 3)[1:]])
        cfg[f"environments/{env}.conf"] = conf

    for h in ALL_HOSTS:
        header = [f"# Host overrides: {h}"]
        top = [f"rack = r{rng.randint(1, 40):02d}", f"zone = {REGIONS[HOST_ENVS[h]]}-{rng.choice('abc')}",
               f"nic = ens{rng.choice([3, 4, 5, 6])}"]
        sections = [[s, section_lines(rng, s, 1, 4)] for s in rng.sample(SVC_NAMES, rng.randint(2, 5))
                    if s not in ("tagging", "recommend", "geo", "ingest")]
        conf = Conf(header, top, sections)
        if h != HOST and rng.random() < 0.3:
            s = rng.choice([x for x, _ in sections] or ["search"])
            if not conf.blocks(s):
                conf.sections.append([s, []])
            conf.set_key(s, "port_offset", safe.next_offset(SVC_PROFILE[s]))
        cfg[f"hosts/{h}.conf"] = conf

    cfg["shared/limits.conf"] = Conf(
        ["# Fleet wide limits."],
        ["max_conns = 1024", "request_timeout_ms = 2500", "slow_log_ms = 500"],
        [[s, section_lines(rng, s, 1, 3)] for s in rng.sample(SVC_NAMES, 5)])
    cfg["shared/batch-window.conf"] = Conf(
        ["# Batch window, UTC."],
        ["window_start = 01:00", "window_end = 05:00", "max_parallel = 2"], [])
    cfg["shared/ports-legacy.conf"] = Conf(
        ["# Port plan from before the admin range split. Kept for reference."],
        ["admin_range = 9440-9459"],
        [["tagging", ["admin_port = 9441"]], ["recommend", ["port_offset = 41"]],
         ["geo", ["admin_port = 9442"]], ["ratings", ["admin_port = 9443"]]])
    cfg["overrides/search-canary.conf"] = Conf(
        ["# Canary listener for search."], [], [["search", ["port_offset = 44"]]])
    cfg["overrides/app-07-profiler.conf"] = Conf(
        ["# Profiler sidecar layout for app-07, first draft."], [],
        [["recommend", ["port_offset = 31"]], ["tagging", ["admin_port = 9447"]]])
    cfg["overrides/maintenance.conf"] = Conf(
        ["# Maintenance window settings."], ["drain_s = 120"],
        [["ingest", ["port_offset = 46"]], ["thumbnail", ["enabled = false"]]])
    return cfg


def noise_mutation(rng, cfg, rev):
    path = rng.choice(sorted(p for p in cfg if p.startswith(("environments/", "hosts/", "profiles/", "shared/limits"))))
    conf = cfg[path]
    if path.startswith("environments/") and rng.random() < 0.3:
        s = rng.choice(SVC_NAMES)
        conf.sections.append([s, [f"# amendment r{rev:04d}"] + section_lines(rng, s, 1, 2)[1:]])
        return path, f"amend {s} in {path}"
    if not conf.sections:
        key = rng.choice(NOISE_KEYS)
        conf.top.append(f"{key} = {pick_value(rng, key)}")
        return path, f"set {key} in {path}"
    name, lines = rng.choice(conf.sections)
    key = rng.choice(NOISE_KEYS)
    blk = conf.blocks(name)[0]
    for i, line in enumerate(blk):
        if line.split("=")[0].strip() == key:
            new = line
            while new == line:
                new = f"{key} = {pick_value(rng, key)}"
            blk[i] = new
            break
    else:
        blk.append(f"{key} = {pick_value(rng, key)}")
    return path, f"tune {key} for {name} in {path}"


def service_files():
    out = {}
    for s in SVC_NAMES:
        lines = [f"# {s}: {SVC_DESC[s]}", f"name = {s}", f"port_offset = {SVC_OFFSET[s]}",
                 f"admin_port = {SVC_ADMIN[s]}", f"data_dir = /var/lib/{s}",
                 f"include = ../../config/profiles/{SVC_PROFILE[s]}.conf"]
        if s == "catalog":
            lines.append("cache_mb = 512")
        if s == "export":
            lines.append(f"admin_port = {SVC_ADMIN[s]}")
        out[f"/app/services/{s}/service.conf"] = "\n".join(lines) + "\n"
    return out


def resolve(files, env, host, svc):
    vals = {}

    def read(path, in_service):
        section = None
        for raw in files[path].splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if section is None:
                if k == "include":
                    target = posixpath.normpath(posixpath.join(
                        posixpath.dirname(path), v.replace("${env}", env).replace("${host}", host)))
                    read(target, False)
                else:
                    vals[k] = v
            elif not in_service and section == svc and k != "include":
                vals[k] = v

    read(f"/app/services/{svc}/service.conf", True)
    return {
        "enabled": vals.get("enabled", "true") != "false",
        "main": int(vals["port_base"]) + int(vals["port_offset"]),
        "admin": int(vals["admin_port"]),
    }


# ------------------------------------------------------------------ timeline


def t(s):
    return datetime.fromisoformat(s).astimezone(UTC)


REV_FIRST, REV_LAST = 380, 419
PLANNED_REV_DATES = {
    405: "2026-03-01T06:10:00+00:00", 406: "2026-03-01T15:20:00+00:00",
    412: "2026-03-09T11:00:00+00:00",
    417: "2026-03-20T14:30:00+00:00", 418: "2026-03-20T21:05:00+00:00", 419: "2026-03-23T09:40:00+00:00",
}
LOG_START = t("2026-02-14T00:00:00+00:00")
LOG_END = t("2026-03-24T18:00:00+00:00")
OPERATORS = ["ops-rota", "ci-nyc", "release-bot", "ops-apac"]


def operator_offset(op, when):
    if op == "ops-rota":
        return timedelta(hours=1)
    if op == "ci-nyc":
        return timedelta(hours=-4) if when >= t("2026-03-08T07:00:00+00:00") else timedelta(hours=-5)
    if op == "release-bot":
        return timedelta(0)
    return timedelta(hours=9)


def fmt_local(when, op):
    off = operator_offset(op, when)
    local = (when + off).replace(tzinfo=None)
    sign = "+" if off >= timedelta(0) else "-"
    mins = abs(int(off.total_seconds())) // 60
    return local.strftime("%Y-%m-%dT%H:%M:%S") + f"{sign}{mins // 60:02d}:{mins % 60:02d}"


def rev_dates(rng):
    dates = {REV_FIRST: t("2026-02-01T09:00:00+00:00")}
    segments = [(381, 404, "2026-02-03", "2026-02-28"), (407, 411, "2026-03-02", "2026-03-08"),
                (413, 416, "2026-03-10", "2026-03-18")]
    for lo, hi, d0, d1 in segments:
        a, b = t(d0 + "T08:00:00+00:00"), t(d1 + "T08:00:00+00:00")
        n = hi - lo + 1
        for i, r in enumerate(range(lo, hi + 1)):
            dates[r] = a + (b - a) * i / max(1, n - 1) + timedelta(minutes=rng.randint(0, 600))
    for r, s in PLANNED_REV_DATES.items():
        dates[r] = t(s)
    for r in range(REV_FIRST, REV_LAST):
        assert dates[r] < dates[r + 1], r
    return dates


def latest_rev(dates, when):
    return max(r for r, d in dates.items() if d <= when)


def build_records(rng, dates):
    recs = []

    def add(when, mode, env, hosts, op, rev=None, **extra):
        recs.append({"when": when, "mode": mode, "env": env, "hosts": hosts, "op": op,
                     "rev": rev if rev is not None else latest_rev(dates, when), **extra})

    app07_applies = [
        ("2026-02-12T08:15", "all", "ops-rota"), ("2026-02-15T13:40", "app-07,app-08", "ci-nyc"),
        ("2026-02-18T09:05", "all", "ops-rota"), ("2026-02-21T22:30", "app-06,app-07", "ops-apac"),
        ("2026-02-24T10:20", "all", "release-bot"), ("2026-02-27T07:50", "app-05,app-07", "ops-rota"),
        ("2026-03-01T09:30", "app-07", "ops-rota"), ("2026-03-04T11:10", "all", "ci-nyc"),
        ("2026-03-07T08:45", "app-07,app-08", "ops-rota"), ("2026-03-10T14:05", "all", "release-bot"),
        ("2026-03-13T09:20", "app-05,app-06,app-07", "ops-apac"), ("2026-03-16T23:35", "all", "ci-nyc"),
        ("2026-03-18T10:00", "app-07", "ops-rota"),
    ]
    for when, hosts, op in app07_applies:
        add(t(when + ":00+00:00"), "apply", "prod-b", hosts, op)
    add(t("2026-03-21T02:40:00+00:00"), "apply", "prod-b", "all", "ci-nyc", target=True)
    add(t("2026-03-21T10:00:00+00:00"), "apply", "prod-a", "all", "ops-rota")
    add(t("2026-03-22T06:00:00+00:00"), "dry-run", "prod-b", "app-07", "ops-rota")
    add(t("2026-03-22T14:15:00+00:00"), "apply", "prod-c", "all", "ci-nyc")
    add(t("2026-03-23T15:10:00+00:00"), "apply", "prod-b", "app-05,app-06,app-08", "ops-rota")
    add(t("2026-03-24T08:30:00+00:00"), "dry-run", "prod-b", "all", "ops-apac")

    others = ["prod-a", "prod-c", "stage", "qa", "perf", "dr-east", "prod-b"]
    day = t("2026-02-02T00:00:00+00:00")
    while day < t("2026-03-20T00:00:00+00:00"):
        for _ in range(rng.choice([1, 1, 2, 2, 3])):
            when = day + timedelta(minutes=rng.randint(30, 23 * 60))
            env = rng.choice(others)
            mode = "apply" if rng.random() < 0.65 else "dry-run"
            if env == "prod-b":
                if t("2026-03-01T00:00:00+00:00") <= when <= t("2026-03-02T00:00:00+00:00"):
                    continue
                pool = [h for h in FLEET[env] if h != HOST] if mode == "apply" else FLEET[env]
            else:
                pool = FLEET[env]
            if rng.random() < 0.4:
                hosts = "all" if not (env == "prod-b" and mode == "apply") else ",".join(pool)
            else:
                hosts = ",".join(sorted(rng.sample(pool, rng.randint(1, len(pool)))))
            rev = latest_rev(dates, when)
            if rng.random() < 0.1 and rev > REV_FIRST:
                rev -= 1
            add(when, mode, env, hosts, rng.choice(OPERATORS), rev)
        day += timedelta(days=1)

    recs.sort(key=lambda r: r["when"])
    rel_count = {}
    for i, r in enumerate(recs):
        r["id"] = f"d-{1100 + i}"
        key = (r["env"], r["when"].date())
        rel_count[key] = rel_count.get(key, 0) + 1
        r["release"] = f"r-{r['when'].strftime('%Y.%m.%d')}-{rel_count[key]}"
        r["host_list"] = FLEET[r["env"]] if r["hosts"] == "all" else r["hosts"].split(",")
    return recs


def render_record(r):
    return "\n".join([
        f"id = {r['id']}",
        f"started_at = {fmt_local(r['when'], r['op'])}",
        f"mode = {r['mode']}",
        f"environment = {r['env']}",
        f"hosts = {r['hosts']}",
        f"config_rev = {r['rev']}",
        f"release = {r['release']}",
        f"requested_by = {r['op']}",
    ]) + "\n"


# ------------------------------------------------------------------ replay


def replay(rng, recs, snapshots, svc_files):
    files_cache = {}

    def files_at(rev):
        if rev not in files_cache:
            f = dict(svc_files)
            f.update({f"/app/config/{p}": text for p, text in snapshots[rev].items()})
            files_cache[rev] = f
        return files_cache[rev]

    pid_counter = [2400]
    hosts = {h: {"runs": [], "procs": {}} for h in ALL_HOSTS}
    events = []
    failures = {h: [] for h in ALL_HOSTS}
    running = {h: {} for h in ALL_HOSTS}
    holders = {h: {} for h in ALL_HOSTS}
    intervals = {s: [] for s in SVC_NAMES}

    for r in recs:
        if r["mode"] != "apply":
            continue
        for h in r["host_list"]:
            env = HOST_ENVS[h]
            loaded, note = r["rev"], ""
            if h == HOST and r.get("target"):
                loaded = r["rev"] - 1
                note = f"fetch of r{r['rev']:04d} failed (checksum mismatch); continued with r{loaded:04d}"
            files = files_at(loaded)
            now = r["when"] + timedelta(seconds=rng.randint(40, 75))
            for svc in SVC_NAMES:
                cfg = resolve(files, env, h, svc)
                old = running[h].pop(svc, None)
                if old:
                    pid, ports, since = old
                    for p in ports:
                        del holders[h][p]
                    hosts[h]["procs"][str(pid)]["exited_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if h == HOST:
                        events.append((now, svc, "INFO", "shutdown requested by deploy agent"))
                        events.append((now + timedelta(milliseconds=rng.randint(300, 900)), svc, "INFO",
                                       f"drained connections={rng.randint(0, 40)}"))
                        events.append((now + timedelta(milliseconds=rng.randint(1000, 1400)), svc, "INFO", "stopped"))
                        intervals[svc].append((since, now))
                    now += timedelta(milliseconds=1500)
                if not cfg["enabled"]:
                    now += timedelta(milliseconds=rng.randint(200, 600))
                    continue
                pid_counter[0] += rng.randint(3, 180)
                pid = pid_counter[0]
                hosts[h]["procs"][str(pid)] = {
                    "cmd": f"/opt/svc/{svc}/bin/serve --conf /app/services/{svc}/service.conf --env {env}",
                    "started_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "exited_at": None}
                ev = []
                ev.append((now, "INFO", f"starting pid={pid} conf=/app/services/{svc}/service.conf"))
                ev.append((now + timedelta(milliseconds=rng.randint(80, 300)), "INFO", f"environment {env}"))
                step = now + timedelta(milliseconds=rng.randint(400, 900))
                opened, failed = [], None
                for lname in ("main", "admin"):
                    port = cfg[lname]
                    if port in holders[h]:
                        failed = (lname, port, holders[h][port][0])
                        ev.append((step, "ERROR", f"listener {lname}: bind failed: address already in use"))
                        ev.append((step + timedelta(milliseconds=12), "ERROR", "startup aborted; closing open listeners"))
                        ev.append((step + timedelta(milliseconds=40), "INFO", "exited status=1"))
                        break
                    if h == HOST and svc == "notify" and lname == "admin" and r.get("target"):
                        ev.append((step, "WARN", "listener admin: bind failed: address already in use; retry 1/3 in 2s"))
                        step += timedelta(seconds=2)
                    holders[h][port] = (svc, pid)
                    opened.append(port)
                    ev.append((step, "INFO", f"listener {lname} ready"))
                    step += timedelta(milliseconds=rng.randint(30, 200))
                if failed:
                    for p in opened:
                        del holders[h][p]
                    hosts[h]["procs"][str(pid)]["exited_at"] = step.strftime("%Y-%m-%dT%H:%M:%SZ")
                    failures[h].append((r["id"], svc) + failed)
                else:
                    running[h][svc] = (pid, opened, step)
                    ev.append((step + timedelta(milliseconds=rng.randint(100, 900)), "INFO",
                               f"startup complete in {rng.randint(900, 4200)}ms"))
                if h == HOST:
                    events.extend((a, svc, b, c) for a, b, c in ev)
                now = step + timedelta(seconds=rng.randint(1, 3))
            hosts[h]["runs"].append({
                "deploy": r["id"], "requested": r["rev"], "loaded": loaded, "note": note,
                "ports": {str(p): v[1] for p, v in sorted(holders[h].items())}})
    for svc, (pid, ports, since) in running[HOST].items():
        intervals[svc].append((since, LOG_END + timedelta(days=1)))
    return hosts, events, failures, intervals


# ------------------------------------------------------------------ logs

PATHS = {"edge": ["/v1/items", "/v1/session", "/v1/token", "/v1/lookup", "/v1/tags", "/v1/reviews"],
         "core": ["/v1/orders", "/v1/accounts", "/v1/prices", "/v1/stock", "/v1/carts", "/v1/query"],
         "worker": ["queue=standard", "queue=bulk", "queue=retry", "queue=priority"],
         "media": ["/v1/assets", "/v1/renditions", "/v1/frames"],
         "batch": ["job=hourly", "job=nightly", "job=adhoc"]}


def background_lines(rng, svc, n, intervals, port_pool):
    spans = [(max(a, LOG_START), min(b, LOG_END)) for a, b in intervals]
    spans = [(a, b) for a, b in spans if b > a]
    total = sum((b - a).total_seconds() for a, b in spans)
    if total <= 0:
        return []
    prof = SVC_PROFILE[svc]
    out = []
    for _ in range(n):
        x = rng.random() * total
        for a, b in spans:
            d = (b - a).total_seconds()
            if x < d:
                when = a + timedelta(seconds=x)
                break
            x -= d
        roll = rng.random()
        if roll < 0.82:
            if prof in ("worker", "batch"):
                msg = (f"job id={rng.getrandbits(32):08x} {rng.choice(PATHS[prof])} state=done "
                       f"items={rng.randint(1, 900)} dur_ms={rng.randint(3, 4000)}")
            else:
                msg = (f"req id={rng.getrandbits(32):08x} method={rng.choice(['GET', 'GET', 'GET', 'POST', 'PUT'])} "
                       f"path={rng.choice(PATHS[prof])}/{rng.randint(1, 99999)} status={rng.choice([200] * 12 + [201, 204, 304, 404])} "
                       f"dur_ms={rng.randint(1, 900)}")
            out.append((when, svc, "INFO", msg))
        elif roll < 0.9:
            out.append((when, svc, "WARN", f"upstream 10.{rng.randint(16, 31)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}:"
                                            f"{rng.choice(port_pool)} slow dur_ms={rng.randint(1500, 9000)}"))
        elif roll < 0.95:
            out.append((when, svc, "ERROR", f"upstream 10.{rng.randint(16, 31)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}:"
                                             f"{rng.choice(port_pool)} connection reset by peer"))
        elif roll < 0.98:
            out.append((when, svc, "INFO", f"gc pause_ms={rng.randint(2, 180)} heap_used_mb={rng.randint(80, 1900)}"))
        else:
            out.append((when, svc, "WARN", f"slow request id={rng.getrandbits(32):08x} dur_ms={rng.randint(2000, 15000)}"))
    return out


def fmt_line(e):
    when, svc, level, msg = e
    return f"{when.strftime('%Y-%m-%dT%H:%M:%S')}.{when.microsecond // 1000:03d}Z {svc} {level} {msg}"


def gz_bytes(text):
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=6) as g:
        g.write(text.encode())
    return buf.getvalue()


# ------------------------------------------------------------------ status state encoding


def keystream(n):
    x = 0x2545F491
    out = bytearray(n)
    for i in range(n):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        out[i] = (x >> 16) & 0xFF
    return out


def encode_state(state):
    packed = zlib.compress(json.dumps(state, sort_keys=True, separators=(",", ":")).encode(), 9)
    return bytes(a ^ b for a, b in zip(packed, keystream(len(packed))))


# ------------------------------------------------------------------ main


def main(out_dir):
    out = Path(out_dir)
    rng = random.Random(SEED)
    safe = SafePorts()

    cfg = base_config(rng, safe)
    dates = rev_dates(rng)
    snapshots = {REV_FIRST: {p: c.render() for p, c in sorted(cfg.items())}}
    changes = {}
    for rev in range(REV_FIRST + 1, REV_LAST + 1):
        summaries = []
        if rev == 405:
            cfg["environments/prod-b.conf"].sections.append(
                ["geo", ["# r0405: admin listener moved next to the worker range", "admin_port = 9512"]])
            summaries.append("prod-b listener layout update")
        elif rev == 406:
            blk = cfg["environments/prod-b.conf"].blocks("geo")[-1]
            blk[:] = ["# r0405: admin listener moved next to the worker range",
                      "# r0406: moved again after the 2026-03-01 apply", "admin_port = 9861"]
            summaries.append("prod-b listener layout update")
        elif rev == 412:
            cfg["hosts/app-07.conf"].sections.append(
                ["recommend", ["# r0412: profiler sidecar on this host needs the usual listener", "port_offset = 46"]])
            summaries.append("app-07 host overrides update")
        elif rev == 417:
            cfg["environments/prod-b.conf"].sections.append(
                ["tagging", ["# r0417: admin listener joins the shared admin range", "admin_port = 9446"]])
            summaries.append("prod-b listener layout update")
        elif rev == 418:
            cfg["profiles/edge.conf"].sections.append(["tagging", ["# r0418", "admin_port = 9452"]])
            summaries.append("edge profile listener layout update")
        elif rev == 419:
            cfg["profiles/batch.conf"].top.append("max_parallel = 3")
            cfg["environments/prod-a.conf"].set_key("billing", "cache_ttl_s", 600)
            summaries.append("batch parallelism and prod-a billing cache")
        else:
            for _ in range(rng.randint(1, 3)):
                summaries.append(noise_mutation(rng, cfg, rev)[1])
        snapshots[rev] = {p: c.render() for p, c in sorted(cfg.items())}
        changed = sorted(p for p in snapshots[rev] if snapshots[rev][p] != snapshots[rev - 1][p])
        assert changed, rev
        changes[rev] = (summaries, changed)

    # Files the planned story depends on must not change after the revision the host loaded.
    for rev in (418, 419):
        for p in ("environments/prod-b.conf", "hosts/app-07.conf", "profiles/core.conf", "shared/limits.conf"):
            assert p not in changes[rev][1], (rev, p)

    svc_files = service_files()
    recs = build_records(rng, dates)
    hosts_state, events, failures, intervals = replay(rng, recs, snapshots, svc_files)

    # ---- the story checks
    target = [r for r in recs if r.get("target")][0]
    assert target["id"] == EXPECT_DEPLOY, target["id"]
    assert target["hosts"] == "all" and target["rev"] == 418
    applies_here = [r for r in recs if r["mode"] == "apply" and HOST in r["host_list"]]
    assert applies_here[-1] is target
    assert recs[-1]["mode"] == "dry-run"
    got = [(svc, l, p, holder) for (_, svc, l, p, holder) in failures[HOST]]
    assert got == EXPECT_FAILURES, got
    assert failures[HOST][-1][0] == EXPECT_DEPLOY
    for h in ALL_HOSTS:
        if h != HOST:
            assert not failures[h], (h, failures[h])
    live = dict(svc_files)
    live.update({f"/app/config/{p}": x for p, x in snapshots[REV_LAST].items()})
    assert resolve(live, HOST_ENV, HOST, "tagging")["admin"] == 9452
    assert resolve(live, HOST_ENV, HOST, "recommend")["main"] == 9446
    run = [x for x in hosts_state[HOST]["runs"] if x["deploy"] == EXPECT_DEPLOY][0]
    assert run["loaded"] == 417
    holder_pid = run["ports"]["9446"]
    assert hosts_state[HOST]["procs"][str(holder_pid)]["cmd"].startswith("/opt/svc/recommend/")
    assert "9452" not in run["ports"]

    # ---- write
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    def write(rel, data, mode=0o644):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            data = data.encode()
        p.write_bytes(data)
        os.chmod(p, mode)

    for path, text in sorted(svc_files.items()):
        write(path[len("/app/"):], text)
    for p, text in sorted(snapshots[REV_LAST].items()):
        write(f"config/{p}", text)
    index = []
    for rev in range(REV_FIRST + 1, REV_LAST + 1):
        summaries, changed = changes[rev]
        when = dates[rev].strftime("%Y-%m-%dT%H:%M:%SZ")
        index.append(f"r{rev:04d}  {when}  {'; '.join(summaries)}")
        write(f"config-history/r{rev:04d}/CHANGES", "\n".join(
            [f"rev = {rev}", f"date = {when}", f"author = {rng.choice(TEAMS)}",
             f"summary = {'; '.join(summaries)}", f"files = {', '.join(changed)}"]) + "\n")
        for p in changed:
            write(f"config-history/r{rev:04d}/prev/{p}", snapshots[rev - 1][p])
    write("config-history/INDEX", f"r{REV_FIRST:04d}  {dates[REV_FIRST].strftime('%Y-%m-%dT%H:%M:%SZ')}  initial import\n"
          + "\n".join(index) + "\n")

    for r in recs:
        write(f"deploy/records/{r['id']}.rec", render_record(r))

    write("etc/host.conf", f"name = {HOST}\nenvironment = {HOST_ENV}\n")
    write("etc/fleet.conf", "".join(f"{e} = {', '.join(hs)}\n" for e, hs in FLEET.items()))

    for doc in sorted((GEN / "docs").iterdir()):
        write(f"docs/{doc.name}", doc.read_text())
    for prog in sorted((GEN / "bin").iterdir()):
        write(f"bin/{prog.name}", prog.read_text(), 0o755)
    write("var/statusd/state.bin", encode_state({"hosts": hosts_state}))

    port_pool = sorted({PROFILE_BASE[SVC_PROFILE[s]] + SVC_OFFSET[s] for s in SVC_NAMES} | {9446, 9452, 9436, 9512})
    by_svc = {s: [] for s in SVC_NAMES}
    for e in events:
        if LOG_START <= e[0] <= LOG_END:
            by_svc[e[1]].append(e)
    stats = {}
    for svc in SVC_NAMES:
        n = int(rng.uniform(4500, 13000))
        lines = by_svc[svc] + background_lines(rng, svc, n, intervals[svc], port_pool)
        lines.sort(key=lambda e: (e[0], e[2], e[3]))
        text = [fmt_line(e) for e in lines]
        a, b = int(len(text) * 0.34), int(len(text) * 0.68)
        write(f"logs/{svc}.log.2.gz", gz_bytes("".join(x + "\n" for x in text[:a])))
        write(f"logs/{svc}.log.1", "".join(x + "\n" for x in text[a:b]))
        write(f"logs/{svc}.log", "".join(x + "\n" for x in text[b:]))
        stats[svc] = len(text)
    print(f"records={len(recs)} revisions={REV_LAST - REV_FIRST} log_lines={sum(stats.values())} "
          f"target={target['id']}")


if __name__ == "__main__":
    main(sys.argv[1])
