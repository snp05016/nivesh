# Nivesh Agent Loops (OpenCode scanner, Codex issue loop)

`scripts/run-opencode-scanner.sh` runs the GitHub issue scanner with OpenCode;
`scripts/codex_issue_loop.sh` runs Codex against open issues in a loop.

Both agents read untrusted text (issue bodies, commit messages, scraped
documents). A prompt injection in any of it can run shell commands with the
agent's permissions, so:

## Never run them on the production host

Do **not** install these on the server (192.168.1.122) or in the checkout that
`backend/nivesh.service` serves from (`/home/saumyapatel/Desktop/nivesh`). That
checkout holds `backend/.env` (live API keys) and the live SQLite databases, and
uvicorn hot-reloads anything written under `backend/`.

Both scripts enforce this and exit with status 2 when:

- the repository is the production checkout (the hard-coded deploy path or the
  `WorkingDirectory` of the `nivesh` systemd unit), or
- `backend/.env` or any `backend/*.db` exists in the repository, or
- the agent would run with approvals/permissions disabled
  (`--dangerously-*`) and `NIVESH_AGENT_SANDBOXED=1` is not set.

## Required environment

Run from a dedicated clone on a non-production machine or user:

- a fresh `git clone` with **no** `backend/.env` and **no** database files;
- a fine-grained GitHub token scoped to this repository's issues only
  (`gh auth login --with-token`);
- egress limited to `github.com` (and the model provider) where possible;
- for the OpenCode scanner, which always passes `--dangerously-skip-permissions`:
  a disposable container or VM with no secrets mounted, with
  `NIVESH_AGENT_SANDBOXED=1` set inside it.

The Codex loop defaults to `codex exec --full-auto` (workspace-write sandbox,
network enabled for `gh`). Overriding `CODEX_CMD` with a `--dangerously-*` flag
also requires `NIVESH_AGENT_SANDBOXED=1`.

| Variable | Used by | Purpose |
|----------|---------|---------|
| `NIVESH_SCANNER_REPO` | scanner | Path to the dedicated clone (required) |
| `OPENCODE_BIN` | scanner | OpenCode binary (default `~/.opencode/bin/opencode`) |
| `NIVESH_AGENT_SANDBOXED` | both | Set to `1` only inside a secret-free container/VM |
| `CODEX_CMD` | Codex loop | Codex invocation (default sandboxed `--full-auto`) |

## Schedule (scanner)

On the sandbox host only:

```cron
0 */2 * * * NIVESH_SCANNER_REPO=/path/to/scanner-clone NIVESH_AGENT_SANDBOXED=1 /path/to/scanner-clone/scripts/run-opencode-scanner.sh
```

## Files

| File | Purpose |
|------|---------|
| `scripts/run-opencode-scanner.sh` | Scanner wrapper with guards, locking and logging (prompt is inline) |
| `logs/scanner-<timestamp>.log` | Per-run output; files older than 14 days are deleted each run |
| `logs/scanner-error.log` | Lock-contention messages |
| `/tmp/nivesh-scanner.lock` | `flock(1)` lock file |

## Remove the cron job from the production server

```bash
crontab -l | grep -v run-opencode-scanner | crontab -
crontab -l    # confirm no run-opencode-scanner entry remains
pkill -f codex_issue_loop.sh || true
```

If a scanner run on the server may have processed a malicious issue, rotate
the API keys that were in `backend/.env` there.

## View logs

```bash
ls -t logs/scanner-*.log | head -1 | xargs cat
cat logs/scanner-error.log
tail -f "$(ls -t logs/scanner-*.log | head -1)"
```
