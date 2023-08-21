import time

from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def configure_settings():
    options = webdriver.ChromeOptions()
    options.add_argument("--enable-javascript")

    return options

def configure_driver(options=configure_settings()):
    service = Service(ChromeDriverManager().install())
    # breakpoint()
    driver = webdriver.Chrome(
        service=service #, options=options
    )

    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver, {get: () => undefined}')"
    )

    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        # {
        #     "userAgent": "Mozilla/5.0 (Windows NT 10.0; W)"
        # }
    )

    return driver

def run(driver= configure_driver()):

    driver.get("https://portal.ustraveldocs.com/applicanthome")

    time.sleep(10)


if __name__ == "__main__":
    run()