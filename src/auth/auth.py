import json
import logging
import os
import re
from time import sleep, time

import urllib3

# from seleniumwire.undetected_chromedriver import ChromeOptions
from selenium.webdriver import FirefoxOptions
import redis
import schedule
from selenium.common import NoSuchElementException
from selenium.webdriver import Remote

cache = redis.Redis(host="redis", port=6379)
username, password = os.getenv("CASEID"), os.getenv("PASSWORD")

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

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
def reauth(username, password):
    firefox_options = FirefoxOptions()
    firefox_options.add_argument("--headless")
    firefox_options.add_argument("--no-sandbox")
    firefox_options.add_argument("--disable-dev-shm-usage")
    firefox_options.add_argument("--ignore-certificate-errors")
    firefox_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36"
    )
    firefox_options.set_capability(
        "cloud:options",
        {
            "browserName": "firefox",
            "platform": "Windows 10",
            "version": "latest",
            "screenResolution": "1920x1080",
            "seleniumVersion": "3.141.59",
        },
    )

    driver = Remote(
        command_executor=f"http://172.21.0.3:4444/wd/hub",
        options=firefox_options,
    )

    # Get the auth cookies
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

    sleep(2)
    driver.get("https://case.emscloudservice.com/web/BrowseForSpace.aspx")
    sleep(2)

    # Get the auth cookies
    auth_cookies = {
        "ASP.NET_SessionId": driver.get_cookie("ASP.NET_SessionId"),
        "__AntiXsrfToken": driver.get_cookie("__AntiXsrfToken"),
        "emsAuthToken": driver.get_cookie("emsAuthToken"),
        "OptanonAlertBoxClosed": driver.get_cookie("OptanonAlertBoxClosed"),
        "OptanonConsent": driver.get_cookie("OptanonConsent"),
    }
    auth_cookies = {k: v["value"] for k, v in auth_cookies.items() if v}
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
