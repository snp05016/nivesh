# Microsoft Qlib Integration for Nivesh

This directory contains the integration engine for Microsoft Qlib.

## ⚠️ CRITICAL PYTHON VERSION BLOCKER
Qlib officially supports **Python 3.8 to 3.10**. It heavily relies on PyTorch, LightGBM, numba, and Cython extensions for its high-performance C++ backend.
Your current backend `venv` runs **Python 3.14.5**. Attempting to `pip install pyqlib` here will fail due to missing wheels for Python 3.14.

### The Solution: The Microservice Architecture
To actually run Qlib alongside Nivesh, you must decouple it:
1. Spin up a separate Docker container running `python:3.10-slim`.
2. Install `pyqlib` inside that container.
3. Expose it via a fast gRPC or local FastAPI port (e.g., `localhost:8001`).
4. Nivesh (Python 3.14) will call the Qlib container (Python 3.10) to fetch model predictions and `.bin` data.

## Getting Indian Market Data into Qlib
Since Qlib does not natively pull NSE data, you must write a script to download it and convert it.

### Step 1: Download the CSVs
Create a script to download NIFTY 500 data via `yfinance` into a folder (e.g., `~/.qlib/csv_data/in/`).
The CSV **must** be named `<ticker>.csv` (e.g., `RELIANCE.NS.csv`) and contain exactly these columns:
`date, open, high, low, close, volume, vwap`

### Step 2: Convert to `.bin` Format
Run Qlib's dump script (from the Qlib repo) to convert the CSVs into the high-speed binary format:
```bash
python scripts/dump_bin.py dump_all \
    --csv_path ~/.qlib/csv_data/in/ \
    --qlib_dir ~/.qlib/qlib_data/in_data \
    --freq day \
    --date_field_name date \
    --symbol_field_name symbol
```

### Step 3: Run the Engine
Once the `.bin` files exist in `~/.qlib/qlib_data/in_data`, the `QlibEngine` in this folder can instantly query the data or run machine learning backtests on it.
