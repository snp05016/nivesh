# ML Architecture Map

```mermaid
graph TD
    subaxis1["Backend (Python 3.14)"]
    Backend[FastAPI Backend]
    PillarLLM[LLM Engine]
    PillarQuant[Quant Engine]
    Fusion[Confidence Fusion]
    DB[(SQLite/PG)]
    Tracker[Outcome Tracker]
    end

    subaxis2["ML Microservice (Python 3.10)"]
    MLRouter[FastAPI :8001]
    Inference[Inference Engine]
    LGBM[LightGBM Model]
    TRA[TRA PyTorch Model]
    Features[Feature Computer Alpha158]
    end
    
    subaxis3["Training Pipeline"]
    Train[train_lightgbm.py]
    WalkForward[walk_forward.py]
    Registry[model_registry.py]
    Artifacts[(Artifacts)]
    end

    Backend -->|Request OHLCV| MLRouter
    MLRouter --> Features
    Features --> Inference
    Inference --> LGBM
    Inference -.->|Disabled| TRA
    Inference -->|Fallback| Heuristic[Technical Heuristic]
    LGBM --> MLRouter
    MLRouter -->|ML Confidence| Fusion
    
    PillarLLM --> Fusion
    PillarQuant --> Fusion
    
    Fusion --> Backend
    Backend -->|Log Prediction| DB
    
    Tracker -->|Fetch 30d Outcome| DB
    Tracker -->|Update Brier/ECE| DB
    
    Train -->|Read CSV/Parquet| WalkForward
    WalkForward --> Train
    Train -->|Save| Registry
    Registry --> Artifacts
    Artifacts -->|Deploy| LGBM
```

## Component Boundaries
- **FastAPI Backend**: Orchestrates the agents, computes Quant signals, merges confidence pillars.
- **ML Microservice**: Isolated environment to run `lightgbm` and `torch` (which lag behind Python 3.14). Exposes stateless REST endpoints.
- **Training Pipeline**: Batch processes executed offline. Currently disorganized but functional for basic LightGBM walk-forward validation.
