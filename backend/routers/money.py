"""Money cluster routes, mounted once by main.py (spec 2.6).

Each feature router lives in routers/<name>.py and is included here when its
module exists, so packages land independently and never edit this file. Only a
missing feature module is skipped; any other import error propagates.
"""
import importlib
import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

FEATURE_ROUTERS = ("money_holdings", "money_imports", "money_xray", "money_tax", "money_replay")

router = APIRouter()


def include_feature(target: APIRouter, name: str, package: str = "routers") -> bool:
    """Include `<package>.<name>.router` into `target`; False when that module does not exist."""
    module_name = f"{package}.{name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name != module_name:
            raise  # the module exists but one of its own imports is missing
        logger.info("[money] %s not installed; skipping", module_name)
        return False
    target.include_router(module.router)
    return True


for _name in FEATURE_ROUTERS:
    include_feature(router, _name)
