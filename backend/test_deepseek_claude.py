import logging
"""
Test script for verifying connectivity and responses from DeepSeek and Claude models.
"""
import os
from services.orchestrator import _deepseek_chat, reformat_with_claude

logging.info("Testing DeepSeek...")
try:
    res = _deepseek_chat([{"role": "user", "content": "Say hello"}])
    logging.info("DeepSeek success:", res)
except Exception as e:
    logging.info("DeepSeek error:", e)

logging.info("\nTesting Claude...")
try:
    res2 = reformat_with_claude("Test output", "TEST", "NSE")
    logging.info("Claude success:", res2)
except Exception as e:
    logging.info("Claude error:", e)
