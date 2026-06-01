# Pujia Admin

Minimal admin dashboard for `pujia.ar`.

## Features

- Redirects: edit redirect targets for one or more `pujia.ar/*` paths.

## Local Development

```bash
uv run flask --app app run --host 127.0.0.1 --port 8043
```

## Production

- App: `127.0.0.1:8043`
- Systemd user service: `pujia-admin.service`
- Admin host: `https://admin.pujia.ar`
- Secrets/config source: `.env` in the project root
- Redirect data: `ADMIN_DATA_PATH`

Copy `.env.example` to `.env` and set `ADMIN_SECRET_KEY`,
`ADMIN_BASIC_AUTH_USERS`, and `ADMIN_BASIC_AUTH_PASSWORD`. The systemd service
runs `scripts/sync-basic-auth` before startup to generate nginx's htpasswd file
from `.env`.

After pulling changes on the host, run `uv sync --frozen` before restarting the
service so `.venv/bin/waitress-serve` exists.

To install or refresh the user systemd unit from the current clone:

```bash
scripts/install-systemd
```

Nginx sends missing `pujia.ar` paths to the app with
`X-Pujia-Redirect-Request: 1`. Existing static files in `/var/www/pujia.ar`
continue to be served directly.

The checked-in nginx configs use `__ADMIN_HTPASSWD_PATH__` as a placeholder;
replace it with `ADMIN_BASIC_AUTH_HTPASSWD_PATH` from `.env` when installing.
