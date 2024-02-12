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

with open("filters.json", "r") as f:
    filters = json.load(f)

username, password = os.getenv("CASEID"), os.getenv("PASSWORD")


@app.route("/find-rooms", methods=["GET"])
async def findRooms():
    hours_from_now = request.args.get("hours_from_now")
    duration_hours = request.args.get("duration_hours")

    if not hours_from_now or not duration_hours:
        return jsonify(
            {"error": "hours_from_now and duration_hours are required parameters"}, 400
        )

    cached_headers = cache.hgetall("auth:cookies")
    cached_cookies = cache.hgetall("auth:headers")
    if not cached_cookies or not cached_headers:
        return jsonify(
            {
                "error": "No cached auth found. This means that the server is currently obtaining an auth token. "
                         "Please try again soon."
            },
            500,
        )
    cache.persist("auth")

    async with aiohttp.ClientSession(
        headers=cached_headers,
        cookies=cached_cookies,
    ) as session:
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
