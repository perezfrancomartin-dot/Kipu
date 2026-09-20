#!/usr/bin/env python3
"""Genera el Identity Reference Sheet (7 angulos) del modelo base.

Usa la identidad fija en identity/master_identity.json y genera una imagen
por cada angulo estandar: frente, 3/4 izquierda, perfil izquierdo,
3/4 derecha, perfil derecho, cuerpo completo, espalda.

Uso:
    APIMART_API_KEY=sk-... python3 tools/generate_reference_sheet.py
    ... --variants 2   # generar mas de 1 opcion por angulo
"""
import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from generate import IDENTITY_PATH, PRIMARY_MODEL, FALLBACK_MODEL, SPECS  # noqa: E402

ANGLES = [
    ("frente", "front view, facing camera directly, full face visible, shoulders squared, arms relaxed at sides"),
    ("3-4-izquierda", "three-quarter left view, body and face angled toward the left, camera capturing left side of face"),
    ("perfil-izquierdo", "full left profile view, face and body turned 90 degrees left, clean side silhouette"),
    ("3-4-derecha", "three-quarter right view, body and face angled toward the right, camera capturing right side of face"),
    ("perfil-derecho", "full right profile view, face and body turned 90 degrees right, clean side silhouette"),
    ("cuerpo-completo", "full body shot head to toe, standing neutral pose, facing camera, entire figure visible in frame"),
    ("espalda", "back view, facing directly away from camera, full back and hair visible, standing neutral pose"),
]

OUT_ROOT = pathlib.Path(__file__).resolve().parent.parent / "identity" / "reference_sheet"


def load_identity():
    data = json.loads(IDENTITY_PATH.read_text())
    desc = data["description"]
    return {
        "fragment": data["prompt_fragment"],
        "wardrobe": desc["wardrobe_default"],
        "background": desc["background_default"],
        "grooming": desc["grooming"],
    }


def build_prompt(identity, angle_desc):
    return (
        f"{identity['fragment']}, {identity['grooming']}, {angle_desc}, "
        f"{identity['wardrobe']}, {identity['background']}, "
        f"studio photography, identity reference sheet, sharp focus, consistent facial identity"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=PRIMARY_MODEL)
    ap.add_argument("--no-fallback", action="store_true")
    ap.add_argument("--variants", type=int, default=1, help="imagenes por angulo (default 1)")
    ap.add_argument("--slug", default="master", help="nombre de la corrida")
    args = ap.parse_args()

    import os
    api_key = os.environ.get("APIMART_API_KEY")
    if not api_key:
        sys.exit("ERROR: falta APIMART_API_KEY en el entorno.")

    identity = load_identity()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = OUT_ROOT / f"{stamp}_{args.slug}"
    folder.mkdir(parents=True, exist_ok=True)

    specs = {**SPECS, "n": args.variants}
    models = [args.model]
    if not args.no_fallback and args.model == PRIMARY_MODEL:
        models.append(FALLBACK_MODEL)

    manifest = {"identity_fragment": identity["fragment"], "angles": {}}

    for angle_slug, angle_desc in ANGLES:
        prompt = build_prompt(identity, angle_desc)
        data = None
        used_model = None
        for model in models:
            try:
                data = call_api_with_specs(model, prompt, api_key, specs)
                used_model = model
                break
            except Exception as exc:  # noqa: BLE001
                print(f"[fallo] {angle_slug} / {model}: {exc}", file=sys.stderr)
        if data is None:
            print(f"[ERROR] no se pudo generar '{angle_slug}', se omite.", file=sys.stderr)
            continue

        urls = [item["url"] for item in data.get("data", []) if item.get("url")]
        if not urls:
            print(f"[ERROR] sin URLs para '{angle_slug}'.", file=sys.stderr)
            continue

        import requests
        paths = []
        for i, url in enumerate(urls, start=1):
            suffix = "" if len(urls) == 1 else f"_v{i}"
            dest = folder / f"{angle_slug}{suffix}.jpg"
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            dest.write_bytes(r.content)
            paths.append(str(dest))
            print(f"[ok] {dest}")

        manifest["angles"][angle_slug] = {
            "prompt": prompt,
            "model": used_model,
            "files": paths,
        }

    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\nReference sheet en: {folder}")


def call_api_with_specs(model, prompt, api_key, specs):
    import requests
    from generate import API_URL, NEGATIVE_PROMPT

    payload = {
        "model": model,
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        **specs,
    }
    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    main()
