import os
import sys
import logging
import json
import subprocess
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from training.dataset_builder import fetch_nifty50, load_csv
from training.feature_pipeline import build_feature_matrix
from training.validation import WalkForwardConfig, generate_splits, run_walk_forward, summarize_results
from training.model_registry import evaluate_deployment_guardrails
from evaluate_truth import BaselineModel, run_regime_analysis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOG = logging.getLogger("evaluate_alpha158")

OUTPUT_DIR = Path(".ml-alpha158-candidate")
DATA_FILE = "nifty50_data.csv"
FEATURE_FILE = "nifty50_features.parquet"

def prepare_data():
    if not os.path.exists(DATA_FILE):
        _LOG.info("Fetching NIFTY 50 historical data...")
        df = fetch_nifty50(start_date="2018-01-01")
        df.to_csv(DATA_FILE, index=False)
    else:
        df = load_csv(DATA_FILE)

    if not os.path.exists(FEATURE_FILE):
        _LOG.info("Building feature matrix (this may take a while)...")
        feat_df = build_feature_matrix(df, min_history=120)
        feat_df.to_parquet(FEATURE_FILE)
    else:
        feat_df = pd.read_parquet(FEATURE_FILE)
        
    return df, feat_df

def write_markdown(filename: str, content: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / filename, "w") as f:
        f.write(content)

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 0. Prepare Data
    _LOG.info("=== 0. Preparing Data ===")
    df, feat_df = prepare_data()
    
    # 1. Train Alpha158 Candidate
    _LOG.info("=== 1. Training Alpha158 Candidate ===")
    train_cmd = [
        sys.executable, "-m", "training.train_alpha158",
        "--target", "direction_20d",
        "--data-path", DATA_FILE
    ]
    
    try:
        subprocess.run(train_cmd, check=True)
    except subprocess.CalledProcessError as e:
        _LOG.error("Training failed.")
        sys.exit(1)
        
    # We must determine the model_version from the registry
    from training.model_registry import list_model_versions, load_model_artifact
    versions = list_model_versions(status="candidate")
    if not versions:
        _LOG.error("No candidate models found in registry.")
        sys.exit(1)
        
    latest_version = versions[-1]
    _LOG.info(f"Loaded candidate version: {latest_version}")
    
    artifact = load_model_artifact(model_version=latest_version, status="candidate")
    metadata = artifact["metadata"]
    metrics = _read_json(Path("models/registry/candidate") / latest_version / "validation_metrics.json")
    calib = _read_json(Path("models/registry/candidate") / latest_version / "calibration_report.json")
    
    # Generate TRAINING_REPORT.md
    write_markdown("TRAINING_REPORT.md", f"""# Training Report
- Version: {latest_version}
- Features: {metadata.get("num_features")}
- Final Trees: {metadata.get("num_trees")}
""")

    # Generate CALIBRATION_REPORT.md
    write_markdown("CALIBRATION_REPORT.md", f"""# Calibration Report
- Best Method: {calib.get("best_method")}
- ECE: {calib.get("ece")}
- MCE: {calib.get("mce")}
- Brier Score: {calib.get("brier_score")}
""")

    # 2. Baseline Comparison & Stress Test Setup
    _LOG.info("=== 2. Baseline Comparison & Stress Tests ===")
    from config import FEATURE_LIST
    feature_cols = [c for c in FEATURE_LIST if c in feat_df.columns]
    
    config = WalkForwardConfig(
        folds=[(2019, 2020), (2020, 2021), (2021, 2022), (2022, 2023), (2023, 2024)],
        target_col="direction_20d",
        min_train_samples=500
    )
    splits = generate_splits(feat_df, config, feature_cols)
    
    val_returns = []
    for s in splits:
        val_df = feat_df[(feat_df["date"].dt.year == s.val_year)].dropna(subset=["direction_20d"])
        val_returns.append(val_df["forward_return_20d"].values)
        
    _LOG.info("Running baselines...")
    baselines = ["mom20", "mom60", "sma_cross", "random", "bullish"]
    
    # Note: to run baselines we need all features for them even if alpha158 doesn't use them.
    all_cols = [c for c in feat_df.columns if c not in ["symbol", "date", "forward_return_20d", "forward_return_60d", "direction_20d", "direction_60d"]]
    all_splits = generate_splits(feat_df, config, all_cols)
    
    base_results = {}
    for b in baselines:
        def baseline_factory(base=b):
            return BaselineModel(base, all_cols)
        b_res = run_walk_forward(baseline_factory, all_splits, return_col="forward_return_20d", val_returns=val_returns)
        base_results[b] = summarize_results(b_res)
        
    stress_results = []
    for fold in metrics:
        if fold.get("val_year") in [2020, 2022]:
            stress_results.append({
                "year": fold.get("val_year"),
                "hit_rate": fold.get("hit_rate"),
                "roc_auc": fold.get("roc_auc")
            })

    # Generate BASELINE_COMPARISON.md
    bc_md = "# Baseline Comparison\\n\\n| Model | Hit Rate | Brier Score | Precision |\\n|---|---|---|---|\\n"
    agg_hit = sum([f["hit_rate"] for f in metrics if "hit_rate" in f]) / len(metrics) if metrics else 0
    bc_md += f"| **Alpha158 Candidate** | {agg_hit:.4f} | {calib.get('brier_score', 0):.4f} | N/A |\\n"
    for b in baselines:
        bc_md += f"| {b} | {base_results[b]['mean_hit_rate']} | {base_results[b]['mean_brier_score']} | {base_results[b]['mean_precision']} |\\n"
    write_markdown("BASELINE_COMPARISON.md", bc_md)
    
    # Generate STRESS_TEST_REPORT.md
    st_md = "# Regime Stress Test Report\\n\\n| Period | Hit Rate | ROC AUC |\\n|---|---|---|\\n"
    for st in stress_results:
        st_md += f"| {st['year']} | {st['hit_rate']:.4f} | {st.get('roc_auc', 'N/A')} |\\n"
    write_markdown("STRESS_TEST_REPORT.md", st_md)
    
    # 3. Model Registry & Guardrails
    write_markdown("MODEL_REGISTRY_ENTRY.md", f"""# Model Registry Entry\n```json\n{json.dumps(metadata, indent=2)}\n```\n""")

    guardrails = evaluate_deployment_guardrails(latest_version, status="candidate")
    
    write_markdown("DEPLOYMENT_RECOMMENDATION.md", f"""# Deployment Recommendation
- Passed Guardrails: {guardrails['passed']}
- Hit Rate: {guardrails['mean_hit_rate']:.4f} (Required: > 0.53)
- Brier Score: {guardrails['brier_score']:.4f} (Required: < 0.2529)

### Reasons for Rejection
{chr(10).join(['- ' + str(r) for r in guardrails['reasons_for_rejection']]) if guardrails['reasons_for_rejection'] else "None. Model passed all guardrails."}
""")

    # Generate FINAL_REPORT.md
    write_markdown("FINAL_REPORT.md", f"""# Final Report
The Alpha158 Candidate (`{latest_version}`) was evaluated.
Guardrail status: **{"PASSED" if guardrails['passed'] else "FAILED"}**
""")

    _LOG.info("=== Evaluation Complete. Reports generated in .ml-alpha158-candidate/ ===")
    
def _read_json(path):
    with open(path, "r") as f:
        return json.load(f)

if __name__ == "__main__":
    main()
