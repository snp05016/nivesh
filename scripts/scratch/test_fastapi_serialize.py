import json

class _SafeJSONEncoder(json.JSONEncoder):
    pass

result = {
    "summary": "• Market is good",
    "movers": ["AAPL"],
    "mood": "positive",
    "generated_at": "12:00",
    "priority_items": []
}

# Simulate _dcache_set
json_str = json.dumps(result, cls=_SafeJSONEncoder)

# Simulate _dcache_get
cached = json.loads(json_str)

# Simulate FastAPI returning it
from fastapi.encoders import jsonable_encoder
fastapi_response = jsonable_encoder(cached)

print(fastapi_response)
print(fastapi_response == result)
