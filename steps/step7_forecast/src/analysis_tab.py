"""The dashboard's Analysis tab: the analyst's write-up (deliverables/my_analysis.html) inlined as a self-contained
frame. It is the analyst's reading of the values of one run, so it is hand-written and does not change with a re-run;
tests/test_analysis_page.py flags any headline number a later run moves. This module only packages it."""
from __future__ import annotations

import base64
import html
import re

from core.config import ROOT

PAGE = ROOT / "deliverables" / "my_analysis.html"
FIG = ROOT / "deliverables" / "figures"
IMG = re.compile(r'<img src="figures/([A-Za-z0-9_]+\.svg)"')

# srcdoc frames resolve '#id' against the parent's URL, which would load the dashboard inside the frame: scroll instead
ANCHORS = ("<script>document.addEventListener('click',function(e){var a=e.target.closest('a[href^=\"#\"]');if(!a)return;"
           "var el=document.getElementById(a.getAttribute('href').slice(1));if(el){e.preventDefault();el.scrollIntoView();}});</script>")


def _embed(m: re.Match) -> str:
    f = FIG / m.group(1)
    if not f.exists():
        return m.group(0)
    return f'<img src="data:image/svg+xml;base64,{base64.b64encode(f.read_bytes()).decode()}"'


def analysis_tab_html() -> str:
    """The page as one frame (its own CSS, light theme, charts embedded), or a pointer when the page is absent."""
    if not PAGE.exists():
        return "<p class=meta>No analysis page (deliverables/my_analysis.html).</p>"
    body = IMG.sub(_embed, PAGE.read_text(encoding="utf-8"))
    doc = f'<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8"></head><body>{body}{ANCHORS}</body></html>'
    return ("<p class=meta>The analyst's reading of the 28 Sep run, question by question (deliverables/my_analysis.html). "
            "Hand-written; tests/test_analysis_page.py flags any headline number a later run changes.</p>"
            f'<iframe title="Analysis" srcdoc="{html.escape(doc, quote=True)}" '
            'style="width:100%;height:calc(100vh - 150px);min-height:640px;border:1px solid #e3e3e3;border-radius:6px"></iframe>')
