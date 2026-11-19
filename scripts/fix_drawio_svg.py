"""Force a white background and drop light-dark() colors from a draw.io SVG export."""

import re
import sys

COLOR = r"(?:rgb\([^)]*\)|#[0-9a-fA-F]{3,8}|[a-zA-Z]+)"
path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    svg = f.read()
svg, n = re.subn(rf"light-dark\(\s*({COLOR})\s*,\s*{COLOR}\s*\)", r"\1", svg)
# GUI saves may use "color-scheme: light dark"; force light either way.
svg = svg.replace(
    "background: transparent; background-color: transparent;",
    "background: #FFFFFF; background-color: #FFFFFF;",
)
svg = svg.replace("color-scheme: light dark;", "color-scheme: light;")
with open(path, "w", encoding="utf-8") as f:
    f.write(svg)
print(f"replaced {n}, left {svg.count('light-dark(')}")
