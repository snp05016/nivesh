# RD-Agent Air-Gapped Sandbox

This sandbox runs [Microsoft RD-Agent](https://github.com/microsoft/RD-Agent) inside a Docker container with **zero network access at runtime**. All market data must be injected via the `./historic_csv/` volume before the container starts — the container cannot download anything from the internet during execution.

---

## Directory Layout

```
ml-engine/sandbox/
├── Dockerfile.rdagent          # Image definition (network allowed at build time only)
├── docker-compose.sandbox.yml  # Runtime config: network_mode=none enforced here
├── historic_csv/               # ← You populate this with NSE bhavcopy CSVs
│   ├── 2024-01-02_bhavcopy.csv
│   ├── 2024-01-03_bhavcopy.csv
│   └── ...
├── workspace/                  # RD-Agent writes factors, models, reports here
└── README.md                   # This file
```

---

## Step 1 — Populate `./historic_csv/` with NSE Bhavcopy Files

The container expects **NSE equity bhavcopy CSV files** in the `./historic_csv/` directory. Each file represents one trading day.

### Option A — Download via NSE directly (run on a networked machine)

```bash
# Example: download the last 30 trading days of bhavcopy ZIPs from NSE and extract
mkdir -p ml-engine/sandbox/historic_csv

# Using the NSE bhavcopy URL pattern (date format: DDMMYY)
# Replace dates with actual trading days
BASE_URL="https://nsearchives.nseindia.com/content/historical/EQUITIES"
for DATE in 220124 230124 240124; do   # DDMMYY format
    curl -L -o /tmp/bhavcopy_${DATE}.zip \
        "${BASE_URL}/${DATE:4:2}${DATE:2:2}${DATE:0:2}/cm${DATE}bhav.csv.zip"
    unzip -o /tmp/bhavcopy_${DATE}.zip -d ml-engine/sandbox/historic_csv/
done
```

### Option B — Use the Nivesh Harvester

The `nivesh-harvester` module can bulk-download and stage bhavcopy CSVs:

```bash
cd nivesh-harvester
python harvest.py --output ../ml-engine/sandbox/historic_csv/ --days 252
```

### Option C — Manual placement

Copy any pre-downloaded CSV files directly:

```bash
cp ~/Downloads/cm*.csv ml-engine/sandbox/historic_csv/
```

**Expected CSV schema** (NSE Bhavcopy columns):

| Column    | Description              |
|-----------|--------------------------|
| `SYMBOL`  | NSE ticker (e.g. RELIANCE) |
| `SERIES`  | Equity series (EQ)       |
| `OPEN`    | Opening price (₹)        |
| `HIGH`    | Day high (₹)             |
| `LOW`     | Day low (₹)              |
| `CLOSE`   | Closing price (₹)        |
| `TOTTRDQTY` | Total traded quantity  |
| `TOTTRDVAL` | Total traded value (₹) |
| `TIMESTAMP` | Trade date (DD-MMM-YYYY) |

---

## Step 2 — Build the Docker Image

> **Network access is only required at build time.** The image caches all Python
> packages (rdagent, qlib, numpy, pandas) during `docker build`. After a
> successful build, no internet connection is needed.

```bash
cd ml-engine/sandbox

# Build the image (requires internet, ~5–10 min first time)
docker compose -f docker-compose.sandbox.yml build
```

---

## Step 3 — Run the Air-Gapped Sandbox

```bash
cd ml-engine/sandbox

# Create workspace dir if it doesn't exist
mkdir -p workspace

# Start the container — network_mode: "none" is enforced automatically
docker compose -f docker-compose.sandbox.yml up
```

The container will:
1. Read bhavcopy CSVs from `/data/historic_csv` (mounted read-only)
2. Run the `rdagent.app.qlib.loop` research iteration
3. Write generated factor code, backtest results, and model artefacts to `./workspace/`

### Verify Zero Network Access

To confirm the air-gap is active, run a connectivity test inside a running container:

```bash
# Start a shell inside the container (for debugging only)
docker run --rm --network=none \
    -v "$(pwd)/historic_csv:/data/historic_csv:ro" \
    ml-engine-sandbox-rdagent \
    python -c "import urllib.request; urllib.request.urlopen('https://example.com')"
# Expected: OSError: [Errno 101] Network is unreachable
```

---

## Step 4 — Inspect Research Output

After a successful run, RD-Agent artefacts appear in `./workspace/`:

```
workspace/
├── factor_code/        # Generated Alpha factor Python modules
├── backtest_results/   # Qlib backtest reports (Sharpe, IC, max drawdown)
├── model_checkpoints/  # Trained LightGBM / linear model files
└── logs/               # RD-Agent iteration logs
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: rdagent` | Image not built yet | Run `docker compose build` |
| `OSError: [Errno 2] No such file or directory: '/data/historic_csv'` | Volume not mounted | Verify `./historic_csv/` exists on host |
| `Network is unreachable` (during run) | Expected — air-gap working | This is correct behaviour |
| `Network is unreachable` (during build) | Docker daemon has no internet | Check host network, build from networked machine |
| Container exits immediately | rdagent loop config missing | Check `./workspace/` for a `config.yaml`; see rdagent docs |
| Permission denied on `./workspace/` | Host dir owned by root | Run `chmod 777 workspace/` on host |

---

## Security Notes

- `network_mode: "none"` removes all network interfaces from the container.
  The LLM code-generation loop in RD-Agent **cannot exfiltrate data or download
  AI-generated code** from external sources at runtime.
- The CSV mount is **read-only** (`:ro`). The container cannot modify or delete source data.
- The container runs as non-root user `rduser` (UID created in Dockerfile).
- Resource limits (4 CPU, 8 GB RAM) are set in `docker-compose.sandbox.yml`.
