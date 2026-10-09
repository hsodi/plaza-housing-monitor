import json
from pathlib import Path

import httpx


API_URL = (
    "https://mosaic-plaza-aanbodapi.zig365.nl/"
    "api/v1/locaties"
)

DETAIL_URL = (
    "https://plaza.newnewnew.space/"
    "portal/object/frontend/getobject/format/json"
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUEST_FILE = (
    PROJECT_ROOT / ".private" / "plaza_request.json"
)


# Load the Plaza request payload once when the program starts.
with open(REQUEST_FILE, "r", encoding="utf-8") as file:
    REQUEST_PAYLOAD = json.load(file)


# Reuse one HTTP client instead of creating a new connection
# every monitoring cycle.
http_client = httpx.Client(
    timeout=20.0,
    limits=httpx.Limits(
        max_connections=5,
        max_keepalive_connections=2,
        keepalive_expiry=30.0,
    ),
)


def get_plaza_listings() -> list[dict]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://plaza.newnewnew.space",
        "Referer": "https://plaza.newnewnew.space/",
        "X-Requested-With": "XMLHttpRequest",
    }

    response = http_client.post(
        API_URL,
        params={"locale": "en_GB"},
        headers=headers,
        json=REQUEST_PAYLOAD,
    )

    response.raise_for_status()

    return response.json()["data"]


def get_listing_details(listing_id: int) -> dict:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
    }

    response = http_client.post(
        DETAIL_URL,
        headers=headers,
        data={
            "id": str(listing_id),
        },
    )

    response.raise_for_status()

    return response.json()["result"]


def close_http_client() -> None:
    http_client.close()