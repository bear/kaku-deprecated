import os

import pytest
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
# from selenium.webdriver.common.alert import Alert

if 'DRIVER_IP' in os.environ:
    host = os.environ['DRIVER_IP']
else:
    host = ''

@pytest.mark.web
@pytest.mark.usefixtures('app')
def test_page():
    driver = webdriver.Remote(
        desired_capabilities=DesiredCapabilities.CHROME,
        command_executor="http://%s:4444" % host
    )
    driver.get('http://nginx:8000')
    driver.get_screenshot_as_file('screenshot.png')
    driver.quit()
