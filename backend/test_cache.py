import os, sys
sys.path.append("/Users/saumya/Desktop/nivesh/backend")
from services.cache_service import sync_get
import json

val = sync_get("morning_brief", "1")
print(type(val))
print(val)
