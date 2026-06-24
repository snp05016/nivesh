import os
import sys
import logging
import numpy as np
import pandas as pd
from pathlib import Path
import json

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from training.dataset_builder import fetch_nifty50, load_csv
from training.feature_pipeline import build_feature_matrix
from training.validation import WalkForwardConfig, generate_splits, run_walk_forward, summarize_results
from training.metrics import aggregate_fold_results

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOG = logging.getLogger("evaluate_truth")

DATA_FILE = "nifty50_data.csv"
FEATURE_FILE = "nifty50_features.parquet"
OUTPUT_DIR = Path("../.ml-truth")

def prepare_data():
    if not os.path.exists(DATA_FILE):
        _LOG.info("Fetching NIFTY 50 historical data...")
        df = fetch_nifty50(start_date="2018-01-01")
        df.to_csv(DATA_FILE, index=False)
    else:
        _LOG.info("Loading existing NIFTY 50 data...")
        df = load_csv(DATA_FILE)

    if not os.path.exists(FEATURE_FILE):
        _LOG.info("Building feature matrix (this may take a while)...")
        feat_df = build_feature_matrix(df, min_history=120)
        feat_df.to_parquet(FEATURE_FILE)
    else:
        _LOG.info("Loading existing feature matrix...")
        feat_df = pd.read_parquet(FEATURE_FILE)
        
    return df, feat_df

class BaselineModel:
    def __init__(self, baseline_type: str, feature_names: list[str] = None):
        self.baseline_type = baseline_type
        self.feature_names = feature_names or []
        
    def fit(self, X, y, **kwargs):
        pass # Baselines don't train
        
    def predict_proba(self, X):
        n = len(X)
        if self.baseline_type == "random":
            return np.random.uniform(0, 1, n)
        elif self.baseline_type == "bullish":
            return np.ones(n) * 0.99
        elif self.baseline_type == "bearish":
            return np.ones(n) * 0.01
        elif self.baseline_type == "rsi":
            rsi_idx = self.feature_names.index("rsi_14")
            rsi = X[:, rsi_idx]
            return np.where(rsi < 30, 0.9, 0.1)
        elif self.baseline_type == "mom20":
            mom_idx = self.feature_names.index("momentum_20d")
            mom = X[:, mom_idx]
            return np.where(mom > 0, 0.9, 0.1)
        elif self.baseline_type == "mom60":
            mom_idx = self.feature_names.index("momentum_60d")
            mom = X[:, mom_idx]
            return np.where(mom > 0, 0.9, 0.1)
        elif self.baseline_type == "sma_cross":
            mom60_idx = self.feature_names.index("momentum_60d")
            mom120_idx = self.feature_names.index("momentum_120d")
            mom60 = X[:, mom60_idx]
            mom120 = X[:, mom120_idx]
            return np.where((mom60 > 0) & (mom120 > 0), 0.9, 0.1)
        return np.ones(n) * 0.5

def run_evaluation():
    df, feat_df = prepare_data()
    _LOG.info(f"Feature matrix shape: {feat_df.shape}")
    
    config = WalkForwardConfig(
        folds=[(2019, 2020), (2020, 2021), (2021, 2022), (2022, 2023), (2023, 2024)],
        target_col="direction_20d",
        min_train_samples=500
    )
    
    # Exclude metadata and target columns from features
    exclude_cols = ["symbol", "date", "forward_return_20d", "forward_return_60d", "direction_20d", "direction_60d"]
    feature_cols = [c for c in feat_df.columns if c not in exclude_cols]
    
    splits = generate_splits(feat_df, config, feature_cols)
    if not splits:
        _LOG.error("Failed to generate splits!")
        return

    val_returns = []
    for s in splits:
        # Extract forward returns for the validation set rows to compute financial metrics
        val_df = feat_df[(feat_df["date"].dt.year == s.val_year)].dropna(subset=["direction_20d"])
        val_returns.append(val_df["forward_return_20d"].values)
    
    results = {}
    
    # 1. Run LightGBM
    import lightgbm as lgb
    def lgb_factory():
        return lgb.LGBMClassifier(n_estimators=100, learning_rate=0.05, max_depth=5, random_state=42, n_jobs=-1)
    
    _LOG.info("=== Running LightGBM ===")
    lgb_res = run_walk_forward(lgb_factory, splits, return_col="forward_return_20d", val_returns=val_returns)
    results["LightGBM"] = summarize_results(lgb_res)
    
    # 2. Run Baselines
    baselines = ["random", "bullish", "bearish", "rsi", "mom20", "mom60", "sma_cross"]
    for b in baselines:
        _LOG.info(f"=== Running Baseline: {b} ===")
        def baseline_factory(base=b):
            return BaselineModel(base, feature_cols)
        b_res = run_walk_forward(baseline_factory, splits, return_col="forward_return_20d", val_returns=val_returns)
        results[b] = summarize_results(b_res)
        
    # 3. Ablation Study
    _LOG.info("=== Running Ablation Study ===")
    ablation_results = {}
    base_alpha = [c for c in feature_cols if not c.startswith("sector_") and not c.startswith("volatility") and not c.startswith("momentum")]
    alpha_sector = base_alpha + [c for c in feature_cols if c.startswith("sector_")]
    alpha_sector_vol = alpha_sector + [c for c in feature_cols if c.startswith("volatility")]
    
    ablation_groups = {
        "Base_Alpha158": base_alpha,
        "Alpha_Sector": alpha_sector,
        "Alpha_Sector_Vol": alpha_sector_vol,
        "All_Features": feature_cols
    }
    for name, cols in ablation_groups.items():
        _LOG.info(f"Ablation: {name} ({len(cols)} features)")
        ablation_splits = generate_splits(feat_df, config, cols)
        res = run_walk_forward(lgb_factory, ablation_splits, return_col="forward_return_20d", val_returns=val_returns)
        ablation_results[name] = summarize_results(res)
        
    results["Ablation"] = ablation_results
    
    # 4. Regime Analysis
    _LOG.info("=== Running Regime Analysis ===")
    regime_results = run_regime_analysis(feat_df, lgb_factory, splits, val_returns, feature_cols)
    results["Regime"] = regime_results
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "eval_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    # Generate Markdown Reports
    generate_markdown_reports(results, lgb_res)
    
    # 5. SHAP Feature Importance
    _LOG.info("=== Generating SHAP Feature Importance ===")
    run_shap_analysis(feat_df, lgb_factory, feature_cols)
    
    _LOG.info("Evaluation complete! Results saved to .ml-truth/")

def run_regime_analysis(feat_df, lgb_factory, splits, val_returns, feature_cols):
    import lightgbm as lgb
    regime_metrics = {"Bull": [], "Bear": [], "Sideways": []}
    
    for idx, split in enumerate(splits):
        # Determine regime for the validation year using average 20D return
        val_df = feat_df[feat_df["date"].dt.year == split.val_year]
        if val_df.empty: continue
        avg_20d_ret = val_df["forward_return_20d"].mean()
        
        regime = "Sideways"
        if avg_20d_ret > 0.005: regime = "Bull"
        elif avg_20d_ret < -0.002: regime = "Bear"
            
        model = lgb_factory()
        model.fit(split.X_train, split.y_train)
        y_prob = model.predict_proba(split.X_val)[:, 1] if hasattr(model, "predict_proba") else model.predict(split.X_val)
        y_pred = (y_prob >= 0.5).astype(int)
        y_true = split.y_val.astype(int)
        
        hit_rate = np.mean(y_pred == y_true)
        returns = val_returns[idx][y_pred == 1]
        
        sharpe = 0.0
        if len(returns) > 0:
            excess = returns - (0.05/252)
            std = np.std(returns)
            sharpe = (np.mean(excess) / std * np.sqrt(252)) if std > 0 else 0.0
            
        regime_metrics[regime].append({"hit_rate": float(hit_rate), "sharpe": float(sharpe), "year": split.val_year})
    
    return regime_metrics

def run_shap_analysis(feat_df, lgb_factory, feature_cols):
    import shap
    # Train a single model on all available data for SHAP
    X = feat_df[feature_cols].values
    y = feat_df["direction_20d"].values
    valid_idx = ~np.isnan(y)
    X = X[valid_idx]
    y = y[valid_idx]
    
    model = lgb_factory()
    model.fit(X, y)
    
    # SHAP is expensive, sample 5000 rows
    sample_idx = np.random.choice(len(X), min(len(X), 5000), replace=False)
    X_sample = X[sample_idx]
    
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)
    
    # LightGBM binary classification shap values might be a list of 2 arrays or a single array
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
        
    mean_abs_shap = np.mean(np.abs(shap_values), axis=0)
    shap_imp = sorted(zip(feature_cols, mean_abs_shap), key=lambda x: x[1], reverse=True)
    
    with open(OUTPUT_DIR / "FEATURE_IMPORTANCE.md", "a") as f:
        f.write("\n\n## Top SHAP Importance\n\n| Feature | Mean |SHAP| |\n|---|---|\n")
        for fname, imp in shap_imp[:30]:
            f.write(f"| {fname} | {imp:.4f} |\n")

def generate_markdown_reports(results, lgb_res):
    # 1. BASELINE_COMPARISON.md
    with open(OUTPUT_DIR / "BASELINE_COMPARISON.md", "w") as f:
        f.write("# Baseline Comparison: ML vs Naive\n\n| Model | Hit Rate | Sharpe | Brier Score | Precision |\n|---|---|---|---|---|\n")
        f.write(f"| **LightGBM** | {results['LightGBM']['mean_hit_rate']} | {np.mean([r.sharpe_ratio for r in lgb_res]) if hasattr(lgb_res[0], 'sharpe_ratio') else 'N/A'} | {results['LightGBM']['mean_brier_score']} | {results['LightGBM']['mean_precision']} |\n")
        for b in ["random", "bullish", "bearish", "rsi", "mom20", "mom60", "sma_cross"]:
            if b in results:
                f.write(f"| {b} | {results[b]['mean_hit_rate']} | N/A | {results[b]['mean_brier_score']} | {results[b]['mean_precision']} |\n")

    # 2. FEATURE_IMPORTANCE.md
    with open(OUTPUT_DIR / "FEATURE_IMPORTANCE.md", "w") as f:
        f.write("# Feature Importance (Native LightGBM Gain)\n\n")
        f.write("| Feature | Importance |\n|---|---|\n")
        if lgb_res and hasattr(lgb_res[-1], "feature_importance"):
            for fname, imp in lgb_res[-1].feature_importance[:30]:
                f.write(f"| {fname} | {imp:.4f} |\n")
                
    # 3. ABLATION_STUDY.md
    with open(OUTPUT_DIR / "ABLATION_STUDY.md", "w") as f:
        f.write("# Ablation Study\n\n| Feature Set | Hit Rate | Brier Score |\n|---|---|---|\n")
        for name, res in results.get("Ablation", {}).items():
            f.write(f"| {name} | {res['mean_hit_rate']} | {res['mean_brier_score']} |\n")
            
    # Write empty stubs for the rest, the user can read the JSON or I can fill them.
    for report in ["REGIME_ANALYSIS.md", "MODEL_STRENGTHS.md", "MODEL_WEAKNESSES.md", "FINAL_VERDICT.md"]:
        with open(OUTPUT_DIR / report, "w") as f:
            f.write(f"# {report.split('.')[0].replace('_', ' ')}\n\nSee `eval_results.json` for detailed metrics.")

if __name__ == "__main__":
    run_evaluation()
