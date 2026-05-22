"""
Full HTML obfuscation layer applied on top of CRO variant rendering.

- Random name tokens per request with client-side JS mapping reversal
- XOR-encoded labels and placeholders (decoded by injected JS)
- Stripped id, autocomplete, pattern, maxlength, inputmode attributes
- Optional field order shuffle

Purely server-side string manipulation; no external HTML parser dependency.
"""

from __future__ import annotations

import base64
import json
import random
import re
import string
from typing import Any


def _xor_u8(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _b64_xor(data: str, key: str) -> str:
    """XOR-encode UTF-8 text with key, return URL-safe base64."""
    b = data.encode("utf-8")
    k = key.encode("utf-8")
    return base64.urlsafe_b64encode(_xor_u8(b, k)).decode("ascii").rstrip("=")


def _gen_key(length: int = 16) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def _gen_token(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _extract_inputs(html: str) -> list[dict[str, Any]]:
    """Find all <input> tags and return their attributes as dicts."""
    out: list[dict[str, Any]] = []
    for m in re.finditer(r'<input\b([^>]*)>', html, re.IGNORECASE):
        attrs_str = m.group(1)
        attrs: dict[str, str] = {}
        for am in re.finditer(r'\b([a-zA-Z0-9_-]+)="([^"]*)"', attrs_str):
            attrs[am.group(1).lower()] = am.group(2)
        attrs["_raw_start"] = m.start()
        attrs["_raw_end"] = m.end()
        attrs["_raw_html"] = m.group(0)
        out.append(attrs)
    return out


def _replace_attr_in_tag(tag_html: str, attr: str, new_value: str | None) -> str:
    """Replace or strip an attribute inside an HTML tag string."""
    attr = attr.lower()
    patt = re.compile(rf'\b{re.escape(attr)}="[^"]*"', re.IGNORECASE)
    if new_value is None:
        return patt.sub("", tag_html)
    if patt.search(tag_html):
        return patt.sub(f'{attr}="{new_value}"', tag_html, count=1)
    # insert if missing
    if tag_html.endswith("/>"):
        return tag_html[:-2] + f' {attr}="{new_value}"/>'
    if tag_html.endswith(">"):
        return tag_html[:-1] + f' {attr}="{new_value}">'
    return tag_html


def _extract_labels(html: str) -> list[dict[str, Any]]:
    """Find all <label> tags and return their text + attrs."""
    out: list[dict[str, Any]] = []
    for m in re.finditer(r'<label\b([^>]*)>(.*?)</label>', html, re.IGNORECASE | re.DOTALL):
        attrs_str = m.group(1)
        attrs: dict[str, str] = {}
        for am in re.finditer(r'\b([a-zA-Z0-9_-]+)="([^"]*)"', attrs_str):
            attrs[am.group(1).lower()] = am.group(2)
        out.append({
            "_start": m.start(),
            "_end": m.end(),
            "_raw": m.group(0),
            "_text": m.group(2),
            "attrs": attrs,
        })
    return out


def apply_obfuscation(
    html: str,
    *,
    shuffle_order: bool = False,
    encode_labels: bool = True,
    encode_placeholders: bool = True,
) -> tuple[str, dict[str, Any]]:
    """
    Apply full obfuscation to rendered HTML.

    Returns (transformed_html, metadata) where metadata contains the mapping
    so the server can decode POST data if needed (though the JS mapping handles
    client-side reversal before submission).
    """
    key = _gen_key(16)
    out = html
    meta: dict[str, Any] = {
        "applied": True,
        "key": key,
        "field_map": {},
    }

    # --- 1. Extract and map input names ---
    inputs = _extract_inputs(out)
    if not inputs:
        return html, {"applied": False, "reason": "no_inputs"}

    # Build name mapping (skip hidden inputs like ui_variant)
    name_map: dict[str, str] = {}  # original_name -> random_token
    token_to_name: dict[str, str] = {}  # random_token -> original_name

    for inp in inputs:
        orig = inp.get("name", "").strip()
        if not orig or orig == "ui_variant":
            continue
        if orig not in name_map:
            token = _gen_token(10)
            name_map[orig] = token
            token_to_name[token] = orig

    meta["field_map"] = token_to_name

    # Replace name attributes in HTML (iterate in reverse to preserve positions)
    replacements: list[tuple[int, int, str]] = []
    for inp in inputs:
        orig = inp.get("name", "").strip()
        if not orig or orig not in name_map:
            continue
        new_tag = _replace_attr_in_tag(inp["_raw_html"], "name", name_map[orig])
        replacements.append((inp["_raw_start"], inp["_raw_end"], new_tag))

    # Apply tag replacements in reverse order
    for start, end, new_tag in sorted(replacements, key=lambda x: x[0], reverse=True):
        out = out[:start] + new_tag + out[end:]

    # --- 2. Strip dangerous attributes from ALL inputs ---
    # After name replacement, re-extract and strip
    inputs2 = _extract_inputs(out)
    replacements2: list[tuple[int, int, str]] = []
    for inp in inputs2:
        tag = inp["_raw_html"]
        # Strip id, autocomplete, pattern, maxlength, inputmode
        for attr in ("id", "autocomplete", "pattern", "maxlength", "inputmode"):
            tag = _replace_attr_in_tag(tag, attr, None)
        # Clean extra whitespace
        tag = re.sub(r"\s+", " ", tag)
        replacements2.append((inp["_raw_start"], inp["_raw_end"], tag))

    for start, end, new_tag in sorted(replacements2, key=lambda x: x[0], reverse=True):
        out = out[:start] + new_tag + out[end:]

    # --- 3. Encode labels and placeholders ---
    label_data: list[dict[str, Any]] = []
    if encode_labels:
        labels = _extract_labels(out)
        label_replacements: list[tuple[int, int, str]] = []
        for lbl in labels:
            text = lbl["_text"].strip()
            if not text:
                continue
            enc = _b64_xor(text, key)
            # Replace the text inside label with a span that gets decoded
            new_lbl = lbl["_raw"].replace(
                lbl["_text"],
                f'<span data-xor-label="{enc}"></span>',
            )
            label_replacements.append((lbl["_start"], lbl["_end"], new_lbl))
            label_data.append({"text": text, "enc": enc})

        for start, end, new_lbl in sorted(label_replacements, key=lambda x: x[0], reverse=True):
            out = out[:start] + new_lbl + out[end:]

    placeholder_data: list[dict[str, Any]] = []
    if encode_placeholders:
        # Find all inputs with placeholders
        inputs3 = _extract_inputs(out)
        ph_replacements: list[tuple[int, int, str]] = []
        for inp in inputs3:
            ph = inp.get("placeholder", "").strip()
            if not ph:
                continue
            enc = _b64_xor(ph, key)
            new_tag = _replace_attr_in_tag(inp["_raw_html"], "placeholder", enc)
            # Mark it as XOR-encoded placeholder
            new_tag = _replace_attr_in_tag(new_tag, "data-xor-ph", "1")
            ph_replacements.append((inp["_raw_start"], inp["_raw_end"], new_tag))
            placeholder_data.append({"text": ph, "enc": enc})

        for start, end, new_tag in sorted(ph_replacements, key=lambda x: x[0], reverse=True):
            out = out[:start] + new_tag + out[end:]

    # --- 4. Inject JS decoder + name mapper ---
    js_payload = _build_js_payload(key, token_to_name, label_data, placeholder_data)
    if "</body>" in out:
        out = out.replace("</body>", js_payload + "\n</body>", 1)
    else:
        out += js_payload

    return out, meta


def _build_js_payload(
    key: str,
    token_to_name: dict[str, str],
    label_data: list[dict[str, Any]],
    placeholder_data: list[dict[str, Any]],
) -> str:
    """Build the inline JS that decodes XOR text and maps names back on submit."""
    # Serialize token_to_name as a flat JS object
    mapping_js = json.dumps(token_to_name, ensure_ascii=False)

    # We don't need to ship label_data/placeholder_data to client since the
    # enc values are already in the HTML; the key is enough to decode.
    js = f"""<script>
(function(){{
  var KEY = "{key}";
  function xorDecode(encB64){{
    var s = atob(encB64.replace(/-/g,'+').replace(/_/g,'/'));
    var out = "";
    for(var i=0;i<s.length;i++){{
      out += String.fromCharCode(s.charCodeAt(i) ^ KEY.charCodeAt(i % KEY.length));
    }}
    return out;
  }}
  // Decode labels
  document.querySelectorAll("[data-xor-label]").forEach(function(el){{
    el.textContent = xorDecode(el.getAttribute("data-xor-label"));
  }});
  // Decode placeholders
  document.querySelectorAll("[data-xor-ph]").forEach(function(el){{
    var enc = el.getAttribute("placeholder");
    if(enc && enc.length > 0){{
      el.setAttribute("placeholder", xorDecode(enc));
    }}
  }});
  // Name mapping: before submit, rewrite token names to canonical names
  var NAME_MAP = {mapping_js};
  var form = document.querySelector("form");
  if(form){{
    form.addEventListener("submit", function(e){{
      Object.keys(NAME_MAP).forEach(function(token){{
        var inputs = form.querySelectorAll('[name="' + token + '"]');
        inputs.forEach(function(inp){{
          inp.setAttribute("name", NAME_MAP[token]);
        }});
      }});
    }});
  }}
}})();
</script>"""
    return js


def decode_post_data(
    post_data: dict[str, Any],
    field_map: dict[str, str],
) -> dict[str, Any]:
    """
    If the client JS failed to rewrite names, decode server-side.
    field_map: token -> original_name (same as meta['field_map'])
    """
    out: dict[str, Any] = {}
    for k, v in post_data.items():
        real = field_map.get(k, k)
        out[real] = v
    return out

