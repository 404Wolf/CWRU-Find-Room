import json
import os

if "cache" not in os.listdir():
    os.mkdir("cache")

import asyncio

import dotenv
import logging
from os import getenv

from ems.auth import AuthedClientSession
from ems.rooms import Rooms

dotenv.load_dotenv()
logging.basicConfig(level=logging.DEBUG)


with open("filters.json", "r") as f:
    filters = json.load(f)

async def main():
    async with AuthedClientSession(getenv("CASEID"), getenv("PASSWORD")) as session:
        rooms = Rooms(session)
        schedule = await rooms.list_rooms(int(getenv("HOURS_FROM_NOW")), int(getenv("DURATION_HOURS")))

        for room in tuple(schedule):
            for term in filters["blacklist"]:
                if term in str(room).lower():
                    schedule.remove(room)
                    break

        prettified = "\n".join(
            [
                f"{room.name} ({room.room_code}, {room.building_code})"
                for room in schedule
            ]
        )
        print(prettified)
        with open("output.txt", "w") as f:
            f.write(prettified)


if __name__ == "__main__":
    asyncio.run(main())
