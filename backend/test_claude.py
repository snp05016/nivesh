import logging
import os
from services.orchestrator import SONNET_MODEL, HAIKU_MODEL, DEEPSEEK_MODEL
import anthropic

claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
logging.info("Client initialized")
try:
    response = claude_client.messages.create(
        model=SONNET_MODEL,
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}],
    )
    logging.info("Sonnet success:", response.content)
except Exception as e:
    logging.info(f"Sonnet error: {e}")

