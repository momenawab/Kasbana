# Stampn Ops host collector

This is the only privileged component in Stampn Ops. It is intentionally
separate from Django and has one API: `GET /v1/snapshot`.

## Guarantees

- no published port, no Caddy route, no shell endpoint, no Docker `exec`;
- bearer authentication uses `X-Ops-Collector-Token` and constant-time compare;
- host facts are read from `/host`; Docker calls are limited by code to list,
  inspect, stats and log-tail APIs;
- it returns bounded data only. The application owns persistence and alerting.

`/var/run/docker.sock` is privileged by nature despite a `:ro` mount. Keep this
service image reviewed, pinned, and private to the compose network. Never mount
that socket in the Django application or a browser-facing service.
