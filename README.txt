REMOTE SWE JOB BOARD — LOCAL SCREENING APP FOR UBUNTU

FIRST TIME (ONE COMMAND)
1. Clone the public repository or download and extract its source ZIP.
2. In a terminal, enter the app folder and run:
   python3 app.py --install
This adds Remote SWE Job Board to your applications menu, creates a desktop
shortcut where supported, and opens your saved list in your default browser.
If Ubuntu asks, right-click the desktop shortcut and choose Allow Launching.
Keep the extracted folder in place. No Python packages or accounts are required.
Requires Python 3.10+ (included in modern Ubuntu).

AFTER THAT: JUST CLICK REMOTE SWE JOB BOARD
The launcher opens the browser app. Repeated clicks reuse the existing app.
It automatically imports jobs when last refreshed over 24 hours ago, then daily
while running. The computer must be on; reopening catches up after time offline.
Refresh jobs triggers an immediate update. New listings appear as pages arrive.
Closing the browser tab leaves the small local server running until logout/reboot.
No cloud account, Notion connection, cron setup, or password is required.

SCREEN JOBS
Newest published jobs are on top; missing publication dates appear last.
Use seniority, location, source, tech stack, and status filters.
Worldwide / Panama listed means a source label, not verified employer eligibility.
Needs review includes unknown countries and LATAM regional restrictions.
US work-authorization requirements and explicit excluded regions are flagged.
Descriptions are screened from the source feed; restrictions missing from it can
still exist on the employer page, so verify eligibility before applying.
Click View description or open the original listing.
Change Status and type Comments; edits save automatically to disk.
Wait for Saved before closing. Failed saves are shown with a retry link.

DATA AND BACKUPS
Your jobs, statuses, and comments live in:
   ~/.local/share/remote-swe-board/jobs.sqlite3
They survive browser cleanup, refreshes, and replacing the downloaded app folder.
Back up notes & statuses downloads a JSON backup. Restore backup merges it into
the app and restores its screening fields. Export filtered CSV includes notes.
The application runs only on 127.0.0.1, the local computer.
Do not share your personal backup if your comments are private.

COVERAGE AND AUTO REFRESH
Five public sources: Himalayas, Remote OK, We Work Remotely, Remotive, Jobicy.
Himalayas: two keyword searches (software engineer and developer), up to 100
pages per search, 20 raw listings per page. Keyword results include unrelated
roles, which are filtered. The source can return fewer rows than that limit.
WWR: frontend, backend, full-stack RSS feeds.
Remote OK and Remotive: currently available public feeds.
Jobicy: available engineering feed with pagination (up to 20 pages).
Feeds have their own windows and restrictions; this is not the entire market.
Some roles also appear on multiple boards. Identical application links, or the
same company/title/location, are merged. This conservative heuristic can still
leave duplicates or merge similar requisitions. Source failures are displayed.
Successfully imported pages are saved even if a later page fails.
Rows disappear from the default view only when the source supplies an expiry date;
absence from a rolling feed does not imply the employer closed the role.
Older rows may need checking. Archived and rejected statuses remain available.
New jobs are sorted by publication timestamp, not by download time.

MANUAL RUN (OPTIONAL)
   python3 app.py
For another local port: python3 app.py --port 8766
For importer diagnostics without opening a browser:
   python3 app.py --import-now --pages 100
These commands must run from the extracted folder or use its full path.

UPDATING
Keep personal data where it is. Replace the extracted app folder with a newer
version; run --install again if you moved it, then reboot to restart the server.
Backup first. Local output/jobs.json, if present, is used only for an empty database.
Generated job snapshots are excluded from this repository. A fresh clone imports
current jobs automatically on its first launch.

TESTS
   python3 -m unittest -v

SOURCES
https://himalayas.app
https://remoteok.com
https://weworkremotely.com
https://remotive.com
https://jobicy.com
Original source links and attribution are included in the app.
