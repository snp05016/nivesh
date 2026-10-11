"""ml-engine/models/ — LightGBM model wrapper (lgb_model) and artifact loader (model_loader).

Intentionally no eager imports: importing the package must not pull in heavy
optional dependencies. Import submodules directly, e.g.
`from models.model_loader import ModelLoader`.
"""
