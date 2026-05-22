from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def pick_variant(subject_key: str, variants: list[str]) -> str:
    h = hashlib.sha256(subject_key.encode()).hexdigest()
    return variants[int(h[:8], 16) % len(variants)]


def _set_or_replace_attr(tag_html: str, attr: str, value: str) -> str:
    patt = re.compile(rf'\b{re.escape(attr)}="[^"]*"', re.IGNORECASE)
    if patt.search(tag_html):
        return patt.sub(f'{attr}="{value}"', tag_html, count=1)
    if tag_html.endswith("/>"):
        return tag_html[:-2] + f' {attr}="{value}"/>'
    if tag_html.endswith(">"):
        return tag_html[:-1] + f' {attr}="{value}">'
    return tag_html


def _replace_label_text(html: str, field_name: str, text: str) -> str:
    patt = re.compile(
        rf'(<label\b[^>]*\bfor="{re.escape(field_name)}"[^>]*>)(.*?)(</label>)',
        re.IGNORECASE | re.DOTALL,
    )
    return patt.sub(lambda m: f"{m.group(1)}{text}{m.group(3)}", html)


def _replace_placeholder(html: str, field_name: str, text: str) -> str:
    patt = re.compile(
        rf'(<input\b[^>]*\bname="{re.escape(field_name)}"[^>]*\bplaceholder=")([^"]*)(")',
        re.IGNORECASE,
    )
    return patt.sub(lambda m: f'{m.group(1)}{text}{m.group(3)}', html)


def _set_input_attr_by_name(html: str, field_name: str, attr: str, value: str) -> str:
    patt = re.compile(
        rf'<input\b[^>]*\bname="{re.escape(field_name)}"[^>]*>',
        re.IGNORECASE,
    )
    return patt.sub(lambda m: _set_or_replace_attr(m.group(0), attr, value), html)


def _set_all_input_autocomplete_off(html: str) -> str:
    patt = re.compile(r"<input\b[^>]*>", re.IGNORECASE)
    return patt.sub(lambda m: _set_or_replace_attr(m.group(0), "autocomplete", "off"), html)


def _inject_hidden_variant_input(html: str, variant_id: str) -> str:
    hidden = f'<input type="hidden" name="ui_variant" value="{variant_id}" />'
    return re.sub(r"</form>", hidden + "</form>", html, count=1, flags=re.IGNORECASE)


def _inject_visual_order_runtime(html: str) -> str:
    js = """<script>
document.addEventListener("DOMContentLoaded", function () {
  var ordered = document.querySelectorAll("input[data-visual-order]");
  ordered.forEach(function (inputEl) {
    var group = inputEl.closest(".form-group");
    if (group) {
      group.style.order = String(inputEl.getAttribute("data-visual-order") || "");
      group.style.display = group.style.display || "";
    }
  });
});
</script>"""
    if "</body>" in html:
        return html.replace("</body>", js + "\n</body>", 1)
    return html + js


def _enabled_variants(variant_config: dict) -> list[dict[str, Any]]:
    variants = variant_config.get("variants")
    if not isinstance(variants, list):
        return []
    out: list[dict[str, Any]] = []
    for item in variants:
        if not isinstance(item, dict):
            continue
        if not item.get("enabled", True):
            continue
        if not str(item.get("id") or "").strip():
            continue
        out.append(item)
    return out


def _text_bundle(variant: dict[str, Any], variant_config: dict[str, Any]) -> dict[str, dict[str, str]]:
    # Supports either direct labels/placeholders or locale-based texts.<locale>.*
    labels = variant.get("labels")
    placeholders = variant.get("placeholders")
    if isinstance(labels, dict) and isinstance(placeholders, dict):
        return {"labels": labels, "placeholders": placeholders}

    locale = str(variant.get("locale") or variant_config.get("default_locale") or "he")
    texts = variant.get("texts")
    if isinstance(texts, dict):
        local = texts.get(locale) or {}
        if isinstance(local, dict):
            return {
                "labels": local.get("labels") if isinstance(local.get("labels"), dict) else {},
                "placeholders": local.get("placeholders")
                if isinstance(local.get("placeholders"), dict)
                else {},
            }
    return {"labels": {}, "placeholders": {}}


def render_test_variant_safe(html: str, variant_config: dict, subject_key: str) -> tuple[str, dict]:
    """
    Takes a clean HTML template and returns a DOM-transformed variant suitable
    for A/B testing while preserving canonical backend field names.
    """
    enabled = _enabled_variants(variant_config if isinstance(variant_config, dict) else {})
    if not enabled:
        return html, {"applied": False, "reason": "no_enabled_variants"}

    variant_ids = [str(v["id"]) for v in enabled]
    variant_id = pick_variant(subject_key, variant_ids)
    variant = next((v for v in enabled if str(v.get("id")) == variant_id), enabled[0])

    out = html
    text_bundle = _text_bundle(variant, variant_config)

    labels = text_bundle.get("labels") or {}
    for field_name, text in labels.items():
        out = _replace_label_text(out, str(field_name), str(text))

    placeholders = text_bundle.get("placeholders") or {}
    for field_name, text in placeholders.items():
        out = _replace_placeholder(out, str(field_name), str(text))

    visual_order = variant.get("visual_order")
    if isinstance(visual_order, dict):
        for field_name, pos in visual_order.items():
            out = _set_input_attr_by_name(out, str(field_name), "data-visual-order", str(pos))
        out = _inject_visual_order_runtime(out)

    if bool(variant.get("autocomplete_off", False)):
        out = _set_all_input_autocomplete_off(out)

    out = _inject_hidden_variant_input(out, variant_id)
    return out, {"applied": True, "variant_id": variant_id}


def load_variant_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"default_locale": "he", "variants": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"default_locale": "he", "variants": []}
    if not isinstance(data, dict):
        return {"default_locale": "he", "variants": []}
    if not isinstance(data.get("variants"), list):
        data["variants"] = []
    return data


def append_variant_event(project_root: Path, *, event_type: str, payload: dict[str, Any]) -> None:
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / "form_variant_events.jsonl"
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": payload,
    }
    with out_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

