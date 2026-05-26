"""Parse a downloaded 10-K HTML file into clean text.

Strategy:
1. Regex-strip iXBRL metadata blocks (<ix:hidden>, <ix:header>, <ix:references>,
   <ix:resources>) from the raw HTML. These contain machine-readable XBRL facts
   that aren't part of the rendered filing. selectolax can't reliably target
   namespaced HTML5 tags with CSS, so we do it before parsing.
2. selectolax parses the rest, drops <script>/<style>/<head> nodes.
3. Drop any element with style="display:none" — SEC filings often hide metadata
   tables this way.
4. Collapse whitespace and runs of blank lines.
"""

from __future__ import annotations

import re
from pathlib import Path

from selectolax.parser import HTMLParser

_IXBRL_META = re.compile(
    r"<ix:(?:hidden|header|references|resources)\b[^>]*>.*?</ix:(?:hidden|header|references|resources)>",
    re.IGNORECASE | re.DOTALL,
)
_WS_INLINE = re.compile(r"[ \t\xa0]+")
_BLANKLINES = re.compile(r"\n{3,}")
_STRIP_TAGS = ("script", "style", "head", "noscript")


def parse_html(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = _IXBRL_META.sub("", raw)
    tree = HTMLParser(raw)
    for tag in _STRIP_TAGS:
        for node in tree.css(tag):
            node.decompose()
    for node in tree.css('[style*="display:none"]'):
        node.decompose()
    root = tree.body or tree.root
    text = root.text(separator="\n") if root is not None else ""
    text = _WS_INLINE.sub(" ", text)
    text = _BLANKLINES.sub("\n\n", text)
    return text.strip()


if __name__ == "__main__":
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/filings/AAPL/2023.html")
    out = parse_html(path)
    print(f"file:  {path}")
    print(f"chars: {len(out):,}")
    print(f"--- first 600 chars ---\n{out[:600]}")
    print(f"--- char range 5000-5600 ---\n{out[5000:5600]}")
