#!/usr/bin/env python3
"""Generador de imagenes de campana via APIMART.

Specs fijas de marca (activewear/streetwear femenino, estetica pilates):
1080x1350 (4:5), 50 steps, cfg 7.5, DPM++ 2M Karras, 4 variantes.

Uso:
    APIMART_API_KEY=sk-... python3 tools/generate.py --prompt "..." [--slug parque-olive]
    ... --model flux-2-pro     # fallback si nano-banana-pro falla
"""
import argparse
import json
import os
import pathlib
import sys
import time

import requests

API_URL = "https://api.apimart.io/v1/images/generations"
PRIMARY_MODEL = "nano-banana-pro"
FALLBACK_MODEL = "flux-2-pro"

NEGATIVE_PROMPT = (
    "artificial skin, plastic look, oversaturated colors, symmetrical face, "
    "uncanny valley, illustration, painting, cartoon, anime, blurry, low quality, "
    "watermark, text, deformed hands, extra fingers, bad anatomy, distorted body, "
    "unnatural pose, heavy makeup, airbrushed skin, perfect symmetry, "
    "studio fake background"
)

SPECS = {
    "width": 1080,
    "height": 1350,
    "steps": 50,
    "cfg_scale": 7.5,
    "sampler": "DPM++ 2M Karras",
    "n": 4,
}

OUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "output"
IDENTITY_PATH = pathlib.Path(__file__).resolve().parent.parent / "identity" / "master_identity.json"


def load_identity_fragment():
    if not IDENTITY_PATH.exists():
        return None
    data = json.loads(IDENTITY_PATH.read_text())
    return data.get("prompt_fragment")


def call_api(model, prompt, api_key, timeout=300):
    payload = {
        "model": model,
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        **SPECS,
    }
    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def download(urls, slug):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = OUT_DIR / f"{stamp}_{slug}"
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, url in enumerate(urls, start=1):
        dest = folder / f"v{i}.jpg"
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        dest.write_bytes(r.content)
        paths.append(dest)
    return folder, paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--slug", default="shot")
    ap.add_argument("--model", default=PRIMARY_MODEL)
    ap.add_argument("--no-fallback", action="store_true")
    ap.add_argument("--no-identity", action="store_true", help="no anteponer el master identity al prompt")
    args = ap.parse_args()

    api_key = os.environ.get("APIMART_API_KEY")
    if not api_key:
        sys.exit("ERROR: falta APIMART_API_KEY en el entorno.")

    prompt = args.prompt
    if not args.no_identity:
        fragment = load_identity_fragment()
        if fragment:
            prompt = f"{fragment}, {prompt}"

    models = [args.model]
    if not args.no_fallback and args.model == PRIMARY_MODEL:
        models.append(FALLBACK_MODEL)

    data = None
    for model in models:
        try:
            data = call_api(model, prompt, api_key)
            print(f"[ok] modelo usado: {model}")
            break
        except Exception as exc:  # noqa: BLE001
            print(f"[fallo] {model}: {exc}", file=sys.stderr)
    if data is None:
        sys.exit("ERROR: ningun modelo respondio.")

    urls = [item["url"] for item in data.get("data", []) if item.get("url")]
    if not urls:
        print(json.dumps(data, indent=2)[:2000], file=sys.stderr)
        sys.exit("ERROR: la respuesta no trajo URLs.")

    folder, paths = download(urls, args.slug)
    meta = {
        "prompt": prompt,
        "prompt_original": args.prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "specs": SPECS,
        "urls": urls,
    }
    (folder / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    print(f"Carpeta: {folder}")
    for p in paths:
        print(f"Imagen lista: {p}")


if __name__ == "__main__":
    main()
