# Personal Admin

## Overview

Minimal personal admin dashboard for random stuff.

### Features

- Redirections.

## Prerrequisites

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
uv run basedpyright

# Run development server
# This runs Flask's development server with HOST and PORT, always with 
# debug mode enabled.
uv run dev

# Run production server
# This runs the app behind Waitress on the same HOST and PORT.
# How you expose, supervise, or proxy that process is
# intentionally left outside this repo.
uv run start
```
