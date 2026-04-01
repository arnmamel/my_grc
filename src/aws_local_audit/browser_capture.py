from __future__ import annotations

from pathlib import Path


def capture_screenshot(
    url: str,
    output_path: str,
    browser_binary: str | None = None,
    driver_path: str | None = None,
    headless: bool = True,
) -> str:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ImportError as exc:
        raise RuntimeError(
            "Selenium support is not installed. Install with `pip install -e .[browser-evidence]`."
        ) from exc

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    if browser_binary:
        options.binary_location = browser_binary

    service = Service(executable_path=driver_path) if driver_path else Service()
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(url)
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(str(target))
        return str(target)
    finally:
        driver.quit()
