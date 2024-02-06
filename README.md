# CWRU Room Finder

This is a program that can automatically use Case Western's room reservation system internal API to locate vacant rooms.

To use it, simply set `CASEID` and `PASSWORD` as environmental variables, install packages in `requirements.txt`, and run `findroom.py`.

All rooms will be filtered out based on the `HOURS_FROM_NOW` and `DURATION_HOURS` set as environmental variables. These should be integers. All rooms will be filtered out based on "blacklist" in `filters.json`, to remove rooms such as "auditoriums" (which are counted as rooms) as well as the health campus.

## Disclaimer
I AM NOT LIABLE FOR ANYTHING THAT HAPPENS AS A RESULT OF USING THIS PROGRAM. This program uses a headless browser to automatically login to your case account, which is probably not allowed.
