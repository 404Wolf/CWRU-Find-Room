import dataclasses
import json
import logging
from os import getenv

from flask import Flask, jsonify, request, Response
import asyncio

from ems.auth import AuthedClientSession
from ems.rooms import Rooms

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)

with open("filters.json", "r") as f:
    filters = json.load(f)


@app.route('/find-rooms', methods=['GET'])
async def findRooms():
    hours_from_now = request.args.get('hours_from_now')
    duration_hours = request.args.get('duration_hours')

    if not hours_from_now or not duration_hours:
        return jsonify({"error": "hours_from_now and duration_hours are required parameters"})

    async with AuthedClientSession(getenv("CASEID"), getenv("PASSWORD")) as session:
        rooms = Rooms(session)
        schedule = await rooms.list_rooms(int(hours_from_now), int(duration_hours))

        for room in tuple(schedule):
            for term in filters["blacklist"]:
                if term in str(room).lower():
                    schedule.remove(room)
                    break

        schedule = [dataclasses.asdict(schedule) for schedule in schedule]
        schedule.sort(key=lambda x: x["name"])

        if request.args.get("prettified", "").lower() == "true":
            return Response(
                "\n".join([f"[{room['room_id']}] {room['name']} ({room['building_code']})" for room in schedule])
                , mimetype="text/plain"
            )

        return jsonify({"rooms": schedule})

if __name__ == '__main__':
    app.run(debug=True)
