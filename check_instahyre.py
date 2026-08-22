from playwright.sync_api import sync_playwright
import time
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://www.instahyre.com/login/')
    page.wait_for_load_state('networkidle')
    time.sleep(2)
    inputs = page.locator('input').all()
    for el in inputs:
        print(f"INPUT: id={el.get_attribute('id')}, name={el.get_attribute('name')}, type={el.get_attribute('type')}")
    browser.close()
