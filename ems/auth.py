import atexit
import json
import logging
import os
from http.cookies import CookieError
from time import sleep, time

import aiohttp
from selenium.common import NoSuchElementException
from selenium.webdriver import Keys
from seleniumwire.undetected_chromedriver.v2 import Chrome, ChromeOptions

logger = logging.getLogger(__name__)

if "auth.json" not in os.listdir("cache"):
    with open("cache/auth.json", "w") as f:
        json.dump(
            {
                "auth_headers": {},
                "auth_cookies": {},
                "refresh_at": 0,
            },
            f,
        )

with open("cache/auth.json", "r") as f:
    cached_auth = json.load(f)
    if cached_auth["refresh_at"] < time():
        cached_auth = {"auth_headers": {}, "auth_cookies": {}}


def dump_auth(auth_headers, auth_cookies):
    logger.debug("Dumping auth to cache")
    with open("cache/auth.json", "w") as f:
        json.dump(
            {
                "auth_headers": auth_headers,
                "auth_cookies": auth_cookies,
                "refresh_at": time() + 6 * 60 * 60,  # 6 hours
            },
            f,
            indent=2,
        )
        exit()


class AuthedClientSession(aiohttp.ClientSession):
    def __init__(self, username, password, *args, **kwargs):
        self.username = username
        self.password = password

        self.auth_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "application/json; charset=UTF-8",
            "Origin": "https://case.emscloudservice.com",
            "Pragma": "no-cache",
            "Referer": "https://case.emscloudservice.com/web/BrowseForSpace.aspx",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        self.auth_cookies = None

        self._logged_in = False
        self._login()

        kwargs["headers"] = self.auth_headers | kwargs.get("headers", {})
        kwargs["cookies"] = self.auth_cookies

        super().__init__(*args, **kwargs)

    def _login(self):
        if cached_auth["auth_headers"] and cached_auth["auth_cookies"]:
            self.auth_headers = cached_auth["auth_headers"]
            self.auth_cookies = cached_auth["auth_cookies"]
            self._logged_in = True
            return

        chrome_options = ChromeOptions()
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36"
        )

        driver = Chrome(options=chrome_options)

        driver.get("https://case.emscloudservice.com/web/SamlAuth.aspx")

        for i in range(10):
            try:
                username_field = driver.find_element("id", "username")
                username_field.send_keys(self.username)
                break
            except NoSuchElementException or AttributeError:
                driver.implicitly_wait(1)

        password_field = driver.find_element("id", "password")
        password_field.send_keys(self.password)

        password_field.send_keys(Keys.RETURN)

        driver.get("https://case.emscloudservice.com/web/BrowseForSpace.aspx")

        self.auth_cookies = {
            "ASP.NET_SessionId": driver.get_cookie("ASP.NET_SessionId"),
            "__AntiXsrfToken": driver.get_cookie("__AntiXsrfToken"),
            "emsAuthToken": driver.get_cookie("emsAuthToken"),
            "OptanonAlertBoxClosed": driver.get_cookie("OptanonAlertBoxClosed"),
            "OptanonConsent": driver.get_cookie("OptanonConsent"),
        }
        self.auth_cookies = {k: v["value"] for k, v in self.auth_cookies.items() if v}

        # Find the last network-related log entry
        for request in driver.requests:
            if "getbrowselocationsrooms" in str(request).lower():
                for header, value in request.headers.items():
                    if header == "dea-CSRFToken":
                        self.auth_headers[header] = value
                break

        try:
            driver.quit()
        except OSError:
            pass
        finally:
            dump_auth(self.auth_headers, self.auth_cookies)
            self._logged_in = True
