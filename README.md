# Personal Admin

## Overview

Minimal personal admin dashboard for random stuff.

### Features

- Redirects.
- Notepad.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)

## Getting started

```bash
# Copy .env.example to create the required settings file
# and edit variables accordingly
cp .env.example .env
vim .env

# Install dependencies
uv sync --all-groups

# Format, lint, and typecheck
uv run ruff format .
uv run ruff check --fix .
uv run python -m basedpyright

# Run the Django development server on HOST:PORT.
# This bootstraps migrations, collects admin static assets,
# and ensures the configured admin user exists.
uv run dev

# Run the production server behind Waitress on HOST:PORT.
# This also runs migrations, collects admin static assets,
# and ensures the configured admin user exists before serving traffic.
uv run start

# Run the test suite
uv run python manage.py test
```
