# par2.py

[![CI](https://github.com/pavel-francirek/par2.py/actions/workflows/ci.yml/badge.svg)](https://github.com/pavel-francirek/par2.py/actions/workflows/ci.yml)

Simple script for file data integrity checks using par2

Requires Python 3.11+ and the `par2` command-line tools (`apt install par2`).

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
