import asyncio
import atexit
import json
import os

import aiohttp
from datetime import datetime, timedelta
from dataclasses import dataclass


import logging

from ems.auth import AuthedClientSession

logger = logging.getLogger(__name__)

if "rooms.json" not in os.listdir("cache"):
    with open("cache/rooms.json", "w") as f:
        json.dump({}, f)

with open("cache/rooms.json", "r") as f:
    cached_rooms = json.load(f)


def dump_cached_rooms():
    with open("cache/rooms.json", "w") as f:
        json.dump(cached_rooms, f, indent=2)


atexit.register(dump_cached_rooms)


def is_range_within_another(range1_start, range1_end, range2_start, range2_end):
    return range1_start >= range2_start and range1_end <= range2_end


@dataclass(frozen=True)
class Room:
    room_id: int
    room_code: str
    building_id: int
    building_code: str
    name: str


class Rooms:
    def __init__(self, session: AuthedClientSession):
        self.session = session

    async def list_rooms(
        self, hours_from_now: int, duration_hours: int, count: int = None
    ) -> list[Room]:
        """
        Asynchronously fetches a list of room openings based on the specified time range and event duration.

        Parameters:
            - hours_from_now (int): Number of hours from the current time.
            - duration_hours (int): Duration for which rooms will be listed.
            - event_duration (int): Minimum duration for which a room should be free.

        Returns:
            list[Opening]: List of Opening instances representing room openings.

        Example:
            hours_from_now = 2
            duration_hours = 4
            event_duration = 2
            openings = await list_rooms(hours_from_now, duration_hours, event_duration)
            for opening in openings:
                print(f"Room ID: {opening.room_id}, Start Time: {opening.start_time}, End Time: {opening.end_time}")
        """
        # Calculate start and end times based on the provided parameters
        current_time = datetime.now()
        desired_start = current_time + timedelta(hours=hours_from_now)
        desired_end = desired_start + timedelta(hours=duration_hours + 1)

        url = "https://case.emscloudservice.com/web/AnonymousServersApi.aspx/GetBrowseLocationsBookings"

        json_data = {
            "filterData": {
                "filters": [
                    {
                        "filterName": "StartDate",
                        "value": desired_start.strftime("%Y-%m-%d %H:%M:%S"),
                        "displayValue": " ",
                        "filterType": 3,
                    },
                    {
                        "filterName": "EndDate",
                        "value": desired_end.strftime("%Y-%m-%d %H:%M:%S"),
                        "filterType": 3,
                        "displayValue": "",
                    },
                    {
                        "filterName": "Locations",
                        "value": "-1",
                        "displayValue": "(all)",
                        "filterType": 8,
                    },
                    {
                        "filterName": "TimeZone",
                        "value": "61",
                        "displayValue": "Eastern Time",
                        "filterType": 2,
                    },
                ],
            },
        }

        logger.info(f"Fetching room data for {desired_start} to {desired_end}.")
        async with self.session.post(url, json=json_data) as response:
            logger.debug(f"Response: {await response.text()}")

            data = await response.json()
            if len(data) < 100:
                self.session.auth()
                data = await response.json()

            data = json.loads(data["d"])["Bookings"]

            bookings = {}
            tasks = []

            # First cache all the room info
            already_fetched_ids = set()
            for i, item in enumerate(data):
                if item["RoomId"] in already_fetched_ids:
                    continue

                bookings[item["RoomId"]] = bookings.get(item["RoomId"], []) + [item]

                async def room_info_fetcher(
                    item=item,
                ):
                    await self.fetch_room_info(item["BuildingId"], item["RoomId"])

                tasks.append(room_info_fetcher())

            await asyncio.gather(*tasks)

            # Then filter out the openings
            openings = set()
            for room, bookings in bookings.items():
                booked = False

                for booking in bookings:
                    # If any booking overlaps with the event duration, skip the room
                    start_time = datetime.strptime(
                        booking["BookingGMTStart"], "%Y-%m-%dT%H:%M:%S"
                    )
                    end_time = datetime.strptime(
                        booking["BookingGMTEnd"], "%Y-%m-%dT%H:%M:%S"
                    )

                    if is_range_within_another(
                        start_time, end_time, desired_start, desired_end
                    ):
                        booked = True
                        break

                if not booked:
                    openings.add(
                        await self.fetch_room_info(
                            booking["BuildingId"], booking["RoomId"]
                        )
                    )
            return openings

    async def fetch_room_info(self, building_id: int, room_id: int):
        """
        Asynchronously fetches room info for the specified room ID.

        Parameters:
            - building_id (int): Building ID for the room.
            - room_id (int): Room ID for which the info is to be fetched.

        Returns:
            Room: Room instance representing the room.
        """
        if (str_room_id := str(room_id)) in cached_rooms:
            return Room(**cached_rooms[str_room_id])

        url = "https://case.emscloudservice.com/web/AnonymousServersApi.aspx/GetLocationDetails"

        json_data = {
            "buildingId": building_id,
            "roomId": room_id,
        }

        async with self.session.post(url, json=json_data) as response:
            print(await response.json())
            logger.info(f"Fetching room info for room {room_id}.")

            data = json.loads(await response.text())
            room_data = json.loads(json.loads(data["d"])["JsonData"])

            room = Room(
                room_id=room_data["RoomId"],
                room_code=room_data["RoomCode"],
                building_id=building_id,
                building_code=room_data["BuildingCode"],
                name=room_data["RoomDescription"],
            )
            cached_rooms[room_id] = room.__dict__

            return room
