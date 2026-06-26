import logging
"""Utility functions and helpers for data processing and date manipulation.

This module provides reusable functions for saving data, validating paths,
manipulating dates, and class decorators used across dataflows.
"""

import os
import re
import json
import pandas as pd
from datetime import date, timedelta, datetime
from typing import Annotated

SavePathType = Annotated[str, "File path to save data. If None, data is not saved."]

# Tickers can contain letters, digits, dot, dash, underscore, and caret
# (for index symbols like ^GSPC). Anything else is rejected so the value
# never escapes a containing directory when interpolated into a path.
_TICKER_PATH_RE = re.compile(r"^[A-Za-z0-9._\-\^]+$")


def safe_ticker_component(value: str, *, max_len: int = 32) -> str:
    """Validate ``value`` is safe to interpolate into a filesystem path.

    Tickers come from user CLI input or from LLM tool calls, both of which
    can be influenced by attacker-controlled content (e.g. prompt injection
    embedded in fetched news). Without validation, a value like
    ``"../../../etc/foo"`` flows into ``os.path.join`` / ``Path /`` and
    escapes the configured cache, checkpoint, or results directory.

    Returns ``value`` unchanged when it matches the allowed pattern; raises
    ``ValueError`` otherwise.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"ticker must be a non-empty string, got {value!r}")
    if len(value) > max_len:
        raise ValueError(f"ticker exceeds {max_len} chars: {value!r}")
    if not _TICKER_PATH_RE.fullmatch(value):
        raise ValueError(
            f"ticker contains characters not allowed in a filesystem path: {value!r}"
        )
    # The regex above allows '.', so values like '.', '..', '...' would pass,
    # and as a path component they traverse the parent directory. Reject any
    # value that's only dots.
    if set(value) == {"."}:
        raise ValueError(f"ticker cannot consist solely of dots: {value!r}")
    return value


def save_output(data: pd.DataFrame, tag: str, save_path: SavePathType = None) -> None:
    """Saves a pandas DataFrame to a CSV file.

    Args:
        data (pd.DataFrame): The DataFrame containing data to save.
        tag (str): A tag or label for the data being saved, used for logging.
        save_path (SavePathType, optional): The file path where the CSV will be saved.
            If None, the data is not saved. Defaults to None.
    """
    if save_path:
        data.to_csv(save_path, encoding="utf-8")
        logging.info(f"{tag} saved to {save_path}")


def get_current_date():
    """Retrieves the current date in YYYY-MM-DD format.

    Returns:
        str: The current date formatted as a string ('YYYY-MM-DD').
    """
    return date.today().strftime("%Y-%m-%d")


def decorate_all_methods(decorator):
    """Class decorator that applies a given decorator to all callable methods in a class.

    Args:
        decorator (callable): The decorator function to apply to each method.

    Returns:
        callable: A class decorator that modifies the methods of the class.
    """
    def class_decorator(cls):
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value):
                setattr(cls, attr_name, decorator(attr_value))
        return cls

    return class_decorator


def get_next_weekday(date):
    """Calculates the next weekday for a given date, skipping weekends.

    Args:
        date (datetime | str): The starting date, either as a datetime object or a
            string in 'YYYY-MM-DD' format.

    Returns:
        datetime: The original date if it is a weekday, or the following Monday
            if the original date falls on a weekend.
    """

    if not isinstance(date, datetime):
        date = datetime.strptime(date, "%Y-%m-%d")

    if date.weekday() >= 5:
        days_to_add = 7 - date.weekday()
        next_weekday = date + timedelta(days=days_to_add)
        return next_weekday
    else:
        return date
