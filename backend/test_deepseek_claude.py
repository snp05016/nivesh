"""
Test script for verifying connectivity and responses from DeepSeek and Claude models.
"""
import os
from services.orchestrator import _deepseek_chat, reformat_with_claude

print("Testing DeepSeek...")
try:
    res = _deepseek_chat([{"role": "user", "content": "Say hello"}])
    print("DeepSeek success:", res)
except Exception as e:
    print("DeepSeek error:", e)

print("\nTesting Claude...")
try:
    res2 = reformat_with_claude("Test output", "TEST", "NSE")
    print("Claude success:", res2)
except Exception as e:
    print("Claude error:", e)
