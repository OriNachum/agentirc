# PyPI Publishing

## Build

```bash
uv build
```

This produces `dist/agentirc_cli-<version>.tar.gz` and `dist/agentirc_cli-<version>-py3-none-any.whl`.

## Publish

```bash
uv publish
```

Or with twine:

```bash
twine upload dist/*
```

Set your PyPI token via `UV_PUBLISH_TOKEN` or `TWINE_PASSWORD` environment variable,
or pass `--token` / `-p` on the command line.

## Install

```bash
pip install agentirc-cli
```

Or with uv:

```bash
uv pip install agentirc-cli
```

To install as a CLI tool:

```bash
uv tool install agentirc-cli
```

This makes the `agentirc` command available globally.
