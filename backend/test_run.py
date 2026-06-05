import json
from services.orchestrator import analyze

result = analyze("SUZLON", "NSE")
print(json.dumps(result, indent=2, ensure_ascii=False))
