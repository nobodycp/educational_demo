# Regenerate ``frontend/templates/bango.html`` from ``frontend/static/bango.source.html``.
# Run from project root:  PYTHONPATH=. python tools/emit_bango_jinja.py
# pylint: skip-file
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "frontend" / "static" / "bango.source.html"
OUT = ROOT / "frontend" / "templates" / "bango.html"

from backend.bango_template import BANGO_CLASS_LOGICAL  # noqa: E402


def jinja_expr(q: str) -> str:
    return "{{ bcls['" + q + "'] }}"


def main() -> None:
    s = STATIC.read_text(encoding="utf-8")
    s = s.replace(
        "<!DOCTYPE html>\n",
        "<!DOCTYPE html>\n"
        "<!-- lab: bango = Jinja+XOR; source: static/bango.source.html; "
        "emit: tools/emit_bango_jinja.py; served: /<seg1>/<seg2>/bango (not file://) -->\n",
        1,
    )
    s = s.replace(
        "    __DEMO_BANGO_SHELL_INJECT__\n",
        "    {% if bango_shell_inject %}{{ bango_shell_inject|safe }}{% endif %}\n",
    )
    s = s.replace("#pangoFinalForm", "#{{ bcls['bango-form'] }}")
    s = s.replace('id="pangoFinalForm"', 'id="{{ bcls[\'bango-form\'] }}"')
    s = s.replace(
        'class="bango-section bango-section--split"',
        "class=\"{{ bcls['bango-section'] }} {{ bcls['bango-section--split'] }}\"",
    )
    for logical in sorted(BANGO_CLASS_LOGICAL, key=len, reverse=True):
        j = jinja_expr(logical)
        s = s.replace(f".{logical}", f".{j}")
        s = s.replace(f'class="{logical}"', f'class="{j}"')
        s = s.replace(f"class='{logical}'", f"class='{j}'")
    first_body = s.find("<body")
    if first_body == -1:
        raise SystemExit("no body")
    gt = s.find(">", first_body) + 1
    inj = (
        "\n  <div"
        " style=\"position:absolute;clip:rect(0,0,0,0);width:1px;height:1px;overflow:hidden\""
        " data-ui-map=\"{{ bango_ui_map_json|e }}\""
        " data-ui-key=\"{{ bango_xor_key|e }}\""
        " aria-hidden=\"true\">.</div>\n"
    )
    s = s[:gt] + inj + s[gt:]
    s = s.replace(
        "  __BANGO_SCRIPTS_INCLUDE__",
        "  {% include 'bango_scripts.html' %}\n",
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(s, encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
