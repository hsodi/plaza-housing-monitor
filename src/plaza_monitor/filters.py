AMSTERDAM_AREA = {
    "Amsterdam",
    "Amstelveen",
    "Diemen",
    "Duivendrecht",
}


def is_in_amsterdam_area(listing: dict) -> bool:
    city = listing.get("city", {}).get("name")

    return city in AMSTERDAM_AREA