# from client import get_plaza_listings, get_listing_details
# from filters import is_in_amsterdam_area
# from notifier import send_telegram_message
# from storage import (
#     initialize_database,
#     listing_exists,
#     save_listing,
# )
# import logging
# import time
# import os

# POLL_INTERVAL_SECONDS = 60

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s | %(levelname)s | %(message)s",
# )

# logger = logging.getLogger(__name__)

# def build_listing_message(details: dict) -> str:
#     city = details["city"]["name"]
#     street = details["street"]
#     house_number = details["houseNumber"]
#     total_rent = details["totalRent"]
#     area = details["areaDwelling"]
#     available = details["availableFromDate"]
#     url_key = details["urlKey"]

#     listing_url = (
#         "https://plaza.newnewnew.space/en/"
#         "availables-places/living-place/details/"
#         f"{url_key}"
#     )

#     return (
#         "🏠 NEW PLAZA LISTING\n\n"
#         f"📍 {street} {house_number}, {city}\n"
#         f"💶 €{total_rent} / month\n"
#         f"📐 {area} m²\n"
#         f"📅 Available: {available}\n\n"
#         f"{listing_url}"
#     )

# def check_once() -> None:
#     initialize_database()

#     listings = get_plaza_listings()

#     logger.info("Received %s listings", len(listings))

#     new_count = 0

#     for listing in listings:
#         listing_id = listing["id"]

#         if listing_exists(listing_id):
#             continue

#         new_count += 1

#         details = get_listing_details(listing_id)

#         if is_in_amsterdam_area(details):
#             message = build_listing_message(details)

#             send_telegram_message(message)

#             logger.info(
#                 "Telegram notification sent for listing %s",
#                 listing_id,
#             )

#         save_listing(listing)

#     logger.info("New listings: %s", new_count)


# def run_monitor() -> None:
#     logger.info("Plaza Monitor started")

#     while True:
#         try:
#             check_once()

#         except Exception:
#             logger.exception("Plaza monitoring cycle failed")

#         time.sleep(POLL_INTERVAL_SECONDS)


# if __name__ == "__main__":
#     run_monitor()


import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from client import (
    close_http_client,
    get_listing_details,
    get_plaza_listings,
)
from filters import is_in_amsterdam_area
from notifier import send_telegram_message
from storage import (
    initialize_database,
    listing_exists,
    save_listing,
)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

POLL_INTERVAL_SECONDS = 60

FILTER_AMSTERDAM = os.getenv(
    "FILTER_AMSTERDAM",
    "true",
).lower() == "true"


# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Telegram message
# --------------------------------------------------

def build_listing_message(details: dict) -> str:
    city = details["city"]["name"]
    street = details["street"]
    house_number = details["houseNumber"]
    total_rent = details["totalRent"]
    area = details["areaDwelling"]
    available = details["availableFromDate"]
    url_key = details["urlKey"]

    listing_url = (
        "https://plaza.newnewnew.space/en/"
        "availables-places/living-place/details/"
        f"{url_key}"
    )

    return (
        "🏠 NEW PLAZA LISTING\n\n"
        f"📍 {street} {house_number}, {city}\n"
        f"💶 €{total_rent} / month\n"
        f"📐 {area} m²\n"
        f"📅 Available: {available}\n\n"
        f"{listing_url}"
    )


# --------------------------------------------------
# Single monitoring cycle
# --------------------------------------------------

def check_once() -> None:

    listings = get_plaza_listings()

    logger.info("Received %s listings", len(listings))

    new_count = 0

    for listing in listings:
        listing_id = listing["id"]

        # We have already processed this listing
        if listing_exists(listing_id):
            continue

        new_count += 1

        logger.info("New listing detected: %s", listing_id)

        # Get full information about the listing
        details = get_listing_details(listing_id)

        # Decide whether notification should be sent
        should_notify = (
            not FILTER_AMSTERDAM
            or is_in_amsterdam_area(details)
        )

        if should_notify:
            message = build_listing_message(details)

            send_telegram_message(message)

            logger.info(
                "Telegram notification sent for listing %s",
                listing_id,
            )
        else:
            logger.info(
                "Listing %s ignored by Amsterdam filter",
                listing_id,
            )

        # Save only after processing succeeds
        save_listing(listing)

    logger.info("New listings: %s", new_count)


# --------------------------------------------------
# Continuous monitoring
# --------------------------------------------------

def run_monitor() -> None:
    logger.info("Plaza Monitor started")
    logger.info(
        "Amsterdam filter: %s",
        "ENABLED" if FILTER_AMSTERDAM else "DISABLED",
    )
    logger.info(
        "Polling interval: %s seconds",
        POLL_INTERVAL_SECONDS,
    )

    initialize_database()

    try:
        while True:
            try:
                check_once()

            except Exception:
                logger.exception(
                    "Plaza monitoring cycle failed"
                )

            time.sleep(POLL_INTERVAL_SECONDS)

    finally:
        close_http_client()

# --------------------------------------------------
# Entry point
# --------------------------------------------------

if __name__ == "__main__":
    run_monitor()