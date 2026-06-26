# Nivesh OpenCode Scanner — Cron Job

Runs the GitHub issue scanner every 2 hours using OpenCode.

## Schedule

`0 */2 * * *` — at minute 0 of every 2nd hour (00:00, 02:00, 04:00, …).

## Files

| File | Purpose |
|------|---------|
| `scripts/run-opencode-scanner.sh` | Wrapper script with locking and logging |
| `opencoderunner.txt` | Instructions fed to the `opencode run` command |
| `logs/scanner-<timestamp>.log` | Per-run output (stdout + stderr) |
| `logs/scanner-error.log` | Lock-contention messages |
| `/tmp/nivesh-scanner.lock` | `flock(1)` lock file |

## Manual Run

```bash
/home/saumyapatel/Desktop/nivesh/scripts/run-opencode-scanner.sh
```

If another instance is running, it will exit immediately and log the conflict.

## Disable the Cron Job

```bash
crontab -l | grep -v run-opencode-scanner | crontab -
```

Or comment out the line:

```bash
crontab -e
# Add a # at the start of the scanner line, then save.
```

## Modify the Schedule

```bash
crontab -e
```

Change `0 */2 * * *` to the desired schedule (standard cron syntax).

## View Logs

```bash
# Latest run
ls -t logs/scanner-*.log | head -1 | xargs cat

# Lock conflicts
cat logs/scanner-error.log

# Tail live (if a run is in progress)
tail -f "$(ls -t logs/scanner-*.log | head -1)"
```

## What It Does

1. Locks `/tmp/nivesh-scanner.lock` (non-blocking `flock`).
2. If the lock cannot be acquired → logs a message and exits.
3. Creates a timestamped log file under `logs/`.
4. `cd`s to the repository root.
5. Runs: `opencode run "using the gh-issue scanner please run $(cat opencoderunner.txt)"`
6. Appends stdout + stderr to the log file.
7. Records the exit code and completion timestamp.
