"""Post a clip to Snapchat Spotlight via the official Public Profile API.

Flow (host: businessapi.snapchat.com/v1):
  1. Create a media container, handing Snapchat an AES-256 key + IV we generate.
  2. Upload the clip ENCRYPTED with that key (AES-256-CBC) in chunks, then FINALIZE.
  3. Create the Spotlight referencing the media_id.
  4. Poll until it leaves review (SUBMITTED -> LIVE / REJECTED).

Requires an approved Snap Business API app + a Public Profile. Auth is OAuth:
we mint a fresh access token from the refresh token on each run.

NOTE: Snapchat's Business API wraps request/response bodies in nested objects and
the exact field names can shift by access tier. The shapes below follow the
documented Public Profile / Spotlight pattern — verify against the live docs on
your first successful post and adjust if a field name differs.
"""
import base64
import os
import secrets
import time

import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ..config import env

API = "https://businessapi.snapchat.com/v1"
TOKEN_URL = "https://accounts.snapchat.com/login/oauth2/access_token"
CHUNK = 8 * 1024 * 1024  # 8 MB upload chunks


def _access_token():
    """Mint a fresh access token from the refresh token (Snap tokens are short
    lived). Falls back to a static SNAPCHAT_ACCESS_TOKEN if that's all there is."""
    rt, cid, cs = env("SNAPCHAT_REFRESH_TOKEN"), env("SNAPCHAT_CLIENT_ID"), env("SNAPCHAT_CLIENT_SECRET")
    if rt and cid and cs:
        r = requests.post(TOKEN_URL, data={
            "grant_type": "refresh_token", "refresh_token": rt,
            "client_id": cid, "client_secret": cs}, timeout=30)
        r.raise_for_status()
        return r.json()["access_token"]
    return env("SNAPCHAT_ACCESS_TOKEN")


def _encrypt(path, key, iv):
    data = open(path, "rb").read()
    padder = padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return enc.update(padded) + enc.finalize()


def post(clip_path, caption, target="SPOTLIGHT"):
    profile_id = env("SNAPCHAT_PROFILE_ID")
    token = _access_token()
    if not token or not profile_id:
        raise RuntimeError(
            "Snapchat needs SNAPCHAT_PROFILE_ID + OAuth creds "
            "(SNAPCHAT_CLIENT_ID/SECRET/REFRESH_TOKEN)."
        )
    H = {"Authorization": f"Bearer {token}"}
    key, iv = secrets.token_bytes(32), secrets.token_bytes(16)

    # 1) create the media container (give Snapchat our AES key/iv to decrypt with)
    r = requests.post(
        f"{API}/public_profiles/{profile_id}/media", headers=H,
        json={"media": [{
            "type": "VIDEO",
            "name": os.path.basename(str(clip_path)),
            "key": base64.b64encode(key).decode(),
            "iv": base64.b64encode(iv).decode(),
        }]}, timeout=60,
    )
    r.raise_for_status()
    body = r.json()
    media = (body.get("media") or [{}])[0]
    media = media.get("media", media)
    media_id = media.get("id") or body.get("id")
    add_path = media.get("add_path") or f"/v1/media/{media_id}/upload"
    upload_url = f"https://businessapi.snapchat.com{add_path}"

    # 2) upload the encrypted clip in chunks, then finalize
    enc = _encrypt(clip_path, key, iv)
    part = 1
    for off in range(0, len(enc), CHUNK):
        requests.post(upload_url, headers=H,
                      data={"action": "ADD", "part_number": part},
                      files={"file": (f"part{part}", enc[off:off + CHUNK])},
                      timeout=180).raise_for_status()
        part += 1
    requests.post(upload_url, headers=H, data={"action": "FINALIZE"}, timeout=60).raise_for_status()

    # 3) create the spotlight
    r = requests.post(
        f"{API}/public_profiles/{profile_id}/spotlights", headers=H,
        json={"spotlights": [{
            "media_id": media_id,
            "locale": "en_US",
            "description": caption[:160],
            "skip_save_to_profile": False,
        }]}, timeout=60,
    )
    r.raise_for_status()
    sp = r.json()
    spot = (sp.get("spotlights") or [{}])[0]
    spot = spot.get("spotlight", spot)
    sid = spot.get("id") or sp.get("id")

    # 4) poll review status (best-effort; spotlights enter SUBMITTED then LIVE)
    for _ in range(12):
        s = requests.get(f"{API}/public_profiles/{profile_id}/spotlights/{sid}",
                         headers=H, timeout=30).json()
        st = (((s.get("spotlights") or [{}])[0]).get("spotlight", {}) or {}).get("status")
        if st in ("LIVE", "SUCCESS", "PUBLISHED"):
            break
        if st in ("REJECTED", "FAILED", "ERROR"):
            raise RuntimeError(f"Snapchat spotlight rejected: {s}")
        time.sleep(5)

    print(f"[snapchat] submitted spotlight {sid} (Snapchat review -> LIVE)")
    return sid
