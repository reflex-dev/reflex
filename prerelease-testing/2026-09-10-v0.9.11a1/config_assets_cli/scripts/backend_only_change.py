"""Toggle a BACKEND-ONLY config knob in rxconfig.py (no frontend effect)."""
import sys
from pathlib import Path

p = Path("rxconfig.py")
s = p.read_text()
marker = "    backend_host="
if '"127.0.0.1"' in s:
    s = s.replace('backend_host="127.0.0.1"', 'backend_host="0.0.0.0"')
else:
    s = s.replace('backend_host="0.0.0.0"', 'backend_host="127.0.0.1"')
s = s.replace('cors_allowed_origins=["http://localhost:5300", "http://localhost:9700"]',
              'cors_allowed_origins=["http://localhost:5300", "http://localhost:9701"]') \
     .replace('cors_allowed_origins=["http://localhost:5300", "http://localhost:9701"]',
              'cors_allowed_origins=["http://localhost:5300", "http://localhost:9700"]') if False else s
p.write_text(s)
print(s)
