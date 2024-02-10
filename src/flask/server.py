import dataclasses
import json
import logging
import os
from pprint import pprint

import redis
from dotenv import load_dotenv

import aiohttp
from flask import Flask, jsonify, request

from ems.rooms import Rooms

app = Flask(__name__)
cache = redis.Redis(host="redis", port=6379, db=0)
load_dotenv()
logging.basicConfig(level=logging.DEBUG)

if "cache" not in os.listdir():
    os.mkdir("cache")
    with open("cache/auth.json", "w") as f:
        json.dump({}, f)

    with open("cache/rooms.json", "w") as f:
        json.dump({}, f)

with open("filters.json", "r") as f:
    filters = json.load(f)

with open("cache/auth.json", "r") as f:
    auth = json.load(f)

username, password = os.getenv("CASEID"), os.getenv("PASSWORD")


@app.route("/find-rooms", methods=["GET"])
async def findRooms():
    hours_from_now = request.args.get("hours_from_now")
    duration_hours = request.args.get("duration_hours")

    if not hours_from_now or not duration_hours:
        return jsonify(
            {"error": "hours_from_now and duration_hours are required parameters"}, 400
        )

    print(cache.get("auth"))
    cached_auth = json.loads(cache.get("auth"))

    async with aiohttp.ClientSession(
        cookies=(cookies := cached_auth["auth_cookies"]),
        headers=(headers := cached_auth["auth_headers"]),
    ) as session:
        pprint(cookies)
        pprint(headers)
        rooms = Rooms(session)
        schedule = await rooms.list_rooms(int(hours_from_now), int(duration_hours))

        for room in tuple(schedule):
            for term in filters["blacklist"]:
                if term in str(room).lower():
                    schedule.remove(room)
                    break

        schedule = [dataclasses.asdict(schedule) for schedule in schedule]
        schedule.sort(key=lambda x: x["name"])

        return jsonify({"rooms": schedule})


if __name__ == "__main__":
    app.run("0.0.0.0", debug=True)
