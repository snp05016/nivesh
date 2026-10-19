"""Targets run inside the CAS parse child process by tests (never import heavy modules here)."""
import time


def sleeper(data, password):
    time.sleep(60)
    return {}


def raiser(data, password):
    raise RuntimeError(f"boom {password}")
