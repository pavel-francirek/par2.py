# par2.py

[![CI](https://github.com/pavel-francirek/par2.py/actions/workflows/ci.yml/badge.svg)](https://github.com/pavel-francirek/par2.py/actions/workflows/ci.yml)

Simple script for file data integrity checks using par2

Requires Python 3.11+ and the `par2` command-line tools (`apt install par2`).

## Usage

```bash
par2.py <directory>            # verify: check existing .dir.par2 sets
par2.py --create <directory>   # also create missing recovery sets
par2.py --silent <directory>   # no output, only the exit status
par2.py --json <directory>     # machine-readable: one JSON object on stdout
par2.py --help                 # full help
```

The `--json` output is designed for automation and LLM skill calls: a single
JSON object with `status` (`ok`/`warning`/`critical`), `exit_code`, `root` and
per-directory `path`/`status`/`messages`.

Exit status: `0` all healthy, `1` warnings (skipped directories, recoverable
errors, unprotected files), `2` critical (usage error, missing directory or
unrecoverable corruption).

## Development

```bash
pip install pytest ruff
python -m pytest    # run tests
ruff check .        # lint
```

pros:
- recursive directory scan
- CLI for periodical run (cron)
- check new files, unrecoverable and recoverable errors - can be used for system checks (nagios/icinga)

### TODO:
- parsing par2 arguments (redudancy level)
