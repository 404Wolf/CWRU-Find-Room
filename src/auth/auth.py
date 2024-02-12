import json
import logging
import os
from datetime import datetime
from time import sleep, time

import urllib3

from selenium.webdriver import FirefoxOptions
import redis
import schedule
from selenium.common import NoSuchElementException
from selenium.webdriver import Remote

cache = redis.Redis(host="redis", port=6379)
username, password = os.getenv("CASEID"), os.getenv("PASSWORD")

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

auth_cookies_required = (
    "ASP.NET_SessionId",
    "__AntiXsrfToken",
    "emsAuthToken",
    "OptanonAlertBoxClosed",
    "OptanonConsent",
)

auth_headers_template = {
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


@schedule.repeat(schedule.every(2).hours, username, password)
def reauth(username: str, password: str):
    firefox_options = FirefoxOptions()
    firefox_options.add_argument("--headless")
    firefox_options.add_argument("start-maximized")
    firefox_options.add_argument("--no-sandbox")
    firefox_options.add_argument("--disable-gpu")
    firefox_options.add_argument("--ignore-certificate-errors")
    firefox_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36"
    )
    firefox_options.set_capability(
        "cloud:options",
        {
            "browserName": "firefox",
            "platform": "Windows 10",
            "screenResolution": "1920x1080",
        },
    )

    driver = Remote(
        command_executor=f"http://firefox:4444/wd/hub",
        options=firefox_options,
    )

    # Before authenticating, make sure that we accept cookies
    driver.get("https://case.emscloudservice.com/web/Default.aspx")
    driver.implicitly_wait(1000)
    driver.find_element("id", "onetrust-accept-btn-handler").click()

    # Authenticate
    driver.get("https://case.emscloudservice.com/web/SamlAuth.aspx")

    # Submit the username
    for i in range(10):
        try:
            logger.info("Submitting username")
            username_field = driver.find_element("id", "username")
            username_field.send_keys(username)
            break
        except NoSuchElementException or AttributeError:
            sleep(1)

    # Submit the password
    for i in range(10):
        try:
            logger.info("Submitting password")
            password_field = driver.find_element("id", "password")
            password_field.send_keys(password)
            break
        except NoSuchElementException or AttributeError:
            sleep(1)

    driver.find_element("id", "login-submit").click()

    driver.get("https://case.emscloudservice.com/web/BrowseForSpace.aspx")
    driver.implicitly_wait(1000)

    successfully_fetched_auth_cookies = set()
    for i in range(4):
        if i == 3:
            raise ValueError("Failed to get auth cookies")

        auth_cookies = {}
        for required_auth_cookie in auth_cookies_required:
            auth_cookie = driver.get_cookie(required_auth_cookie)
            if auth_cookie:
                auth_cookies[required_auth_cookie] = auth_cookie["value"]
                successfully_fetched_auth_cookies.add(required_auth_cookie)

        logger.info("Was able to fetch: %s", successfully_fetched_auth_cookies)
        if len(successfully_fetched_auth_cookies) == len(auth_cookies_required):
            break
    logger.debug(f"Auth cookies: {auth_cookies}")

    # Create auth headers
    auth_headers = auth_headers_template.copy()
    auth_headers["dea-CSRFToken"] = driver.find_element(
        "id", "deaCSRFToken"
    ).get_attribute("value")
    logger.debug(f"Auth headers: {auth_headers}")

    cache.set(
        "auth",
        json.dumps(
            {
                "auth_cookies": auth_cookies,
                "auth_headers": auth_headers,
                "expires_at": int(time()) + 7200,
            }
        ),
    )

    logger.info("Auth refreshed")
    logger.debug(f"Auth: {json.loads(cache.get('auth'))}")


sleep(10)
while True:
    try:
        reauth(username, password)
        while True:
            schedule.run_pending()
            sleep(1)
    except urllib3.exceptions.MaxRetryError:
        logger.error("Max retries exceeded")
        sleep(1)
