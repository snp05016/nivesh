# Dead Code & Zombie Paths

1. **`models/tra.py`**:
   The TRA (Temporal Routing Adaptor) PyTorch model is extensively defined and imported. However, there is no corresponding `train_tra.py`. Since it's untrained, it acts as dead weight in the container.

2. **`pipeline/tra_sequence.py`**:
   Logic to convert DataFrame OHLCV rows into 3D tensors `[batch, seq_len, features]` for TRA prediction. It is bypassed because TRA is never loaded successfully in production.

3. **Inference TRA paths (`inference.py:_predict_tra`)**:
   Dead fallback code because `self._tra_model` is structurally `None`. 

4. **Ensemble Mode (`model_type="ensemble"`)**:
   `inference.py` supports ensembling LightGBM and TRA `0.6 * raw_lgb + 0.4 * raw_tra`. Since TRA is dead, invoking this mode would either crash or rely solely on fallback heuristics.

*Recommendation*: Keep the TRA code as structural scaffolding but mark it explicitly as `[UNIMPLEMENTED]` or segregate it into an `experimental/` module to prevent confusion during LightGBM hardening.
