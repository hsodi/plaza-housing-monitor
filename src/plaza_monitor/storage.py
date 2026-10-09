import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "data" / "plaza.db"


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY,
                net_rent REAL,
                total_rent REAL,
                latitude REAL,
                longitude REAL,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def listing_exists(listing_id: int) -> bool:
    with get_connection() as connection:
        result = connection.execute(
            """
            SELECT 1
            FROM listings
            WHERE id = ?
            """,
            (listing_id,),
        ).fetchone()

    return result is not None


def save_listing(listing: dict) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO listings (
                id,
                net_rent,
                total_rent,
                latitude,
                longitude
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                listing["id"],
                listing["netRent"],
                listing["totalRent"],
                listing["latitude"],
                listing["longitude"],
            ),
        )