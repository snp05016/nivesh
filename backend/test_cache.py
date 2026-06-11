import anthropic

client = anthropic.Anthropic(api_key="placeholder")
try:
    req = client.messages.with_raw_response.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}],
        extra_body={"cache_control": {"type": "ephemeral"}}
    )
    print("Success")
except Exception as e:
    print(f"Error: {e}")
