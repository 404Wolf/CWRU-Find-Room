import dataclasses
import json
import logging
import os
from pprint import pprint
from threading import Thread
from time import sleep

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


cached_auth = cache.get("auth")


def keep_auth():
    global cached_auth

    while True:
        new_cached_auth = cache.get("auth") or str(cached_auth)
        if new_cached_auth:
            cached_auth = json.loads(new_cached_auth)
        else:
            sleep(2)


Thread(target=keep_auth, daemon=True).start()


@app.route("/find-rooms", methods=["GET"])
async def findRooms():
    global cached_auth

    hours_from_now = request.args.get("hours_from_now")
    duration_hours = request.args.get("duration_hours")

    if not hours_from_now or not duration_hours:
        return jsonify(
            {"error": "hours_from_now and duration_hours are required parameters"}, 400
        )

    if not cached_auth:
        return (
            jsonify(
                {
                    "error": "No cached auth found. This means that the server is currently obtaining an auth token. "
                             "Please try again soon."
                }
            ),
            500,
        )

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
