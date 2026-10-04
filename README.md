# Remote SWE Job Board

A local browser app for finding remote software engineering jobs, checking location restrictions for Panama, and tracking applications with saved statuses and notes.

Built with Python's standard library, SQLite, and HTML/JavaScript. Runs on Ubuntu/Linux with Python 3.10+; no additional Python packages are required.

## Quick start

```bash
git clone https://github.com/cws1121/remote-swe-board.git
cd remote-swe-board
python3 app.py
```

The app opens in your default browser at `http://127.0.0.1:8765` and imports jobs from public feeds. The first refresh can take a few minutes.

To add an application menu entry and desktop shortcut:

```bash
python3 app.py --install
```

Keep the cloned folder in place after installing the launcher.

## Features

- Fetch jobs from Himalayas, Remote OK, We Work Remotely, Remotive, and Jobicy.
- Filter by seniority, geography, technology, source, and application status.
- Review source location labels and work authorization restrictions.
- Save screening notes and statuses locally, with JSON backup/restore and CSV export.
- Refresh daily while the app is running, or manually from the browser.

Source labels do not establish employer eligibility. Review the original listing before applying.

## Data

Personal jobs, statuses, and comments are stored outside the repository in `~/.local/share/remote-swe-board/jobs.sqlite3`. To select another data directory, set `REMOTE_SWE_DATA_DIR`.

Generated snapshots in `output/`, databases, backups, environment files, and local Notion configuration are excluded from Git. A fresh clone imports current jobs automatically; an optional local `output/jobs.json` seeds an empty database.

## Commands

```bash
# Use another local port
python3 app.py --port 8766

# Run without opening a browser
python3 app.py --no-browser

# Import jobs without running the browser server
python3 app.py --import-now --pages 100

# Run the existing test suite
python3 -m unittest -v
```

See [README.txt](README.txt) for source coverage, screening details, backups, and update instructions.

## Updating or repairing the Ubuntu launcher

From your cloned application folder:

```bash
git pull --ff-only
python3 app.py --install
```

Run the installation command again after moving the folder. It replaces the old
menu entry, refreshes the desktop application database, and updates the desktop
shortcut to the current path. Close and reopen the applications menu afterward.
Your SQLite data, statuses, and notes remain in the separate data directory.
