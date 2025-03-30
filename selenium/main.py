import os
import sys
import time
import re
import logging
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# logging.setLoggerClass(logging.basicConfig)
def log(msg):
    print(f"{msg}", file=sys.stderr)


INDENT = 0


def get_indent() -> str:
    global INDENT
    return " " * INDENT


class Link:
    def __init__(self, href, text):
        self.href = href
        self.text = text

    def __str__(self):
        return f"{self.href}: {self.text}"

    def get_kind_of_link(self, driver):
        pattern = r"^[0-2][0-9] - "
        if re.match(pattern, self.text):
            delimiter = " - "
            lst = self.text.split(delimiter)
            round = lst[0]
            location = delimiter.join(lst[1:])
            pattern = r"http[s]*://americanmotocrossresults.com/"
            href = re.sub(pattern, "", self.href)
            # If there is no change we don't have a correct href
            assert href != self.href
            pattern = "live/archives/mx/"
            year = "1900"  # init value
            if href.startswith(pattern):
                s = href.removeprefix(pattern)
                pattern = r"^20[0-9][0-9]/"
                if re.match(pattern, s):
                    year = s.split("/")[0]
                else:
                    raise ValueError
            else:
                pattern = r"^20[0-9][0-9]/"
                if re.match(pattern, href):
                    year = href.split("/")[0]
                else:
                    raise ValueError
            return RaceResult(round, location, year, self.href)
        elif "Final Standings" in self.text:
            class_name = self.text.replace("Final Standings", "").strip()
            pattern = r"http[s]*://americanmotocrossresults.com/"
            href = re.sub(pattern, "", self.href)
            # If there is no change we don't have a correct href
            assert href != self.href
            pattern = "live/archives/mx/"
            year = ""  # init value
            if href.startswith(pattern):
                s = href.removeprefix(pattern)
                pattern = r"^20[0-9][0-9]/"
                if re.match(pattern, s):
                    year = s.split("/")[0]
                else:
                    raise ValueError
            else:
                pattern = "xml/MX/events/M"
                if href.startswith(pattern):
                    s = href.removeprefix(pattern)[0:2]
                    pattern = r"^[0-9][0-9]"
                    if re.match(pattern, s):
                        year = str(int(s) + 2000)
                    else:
                        raise ValueError
                else:
                    raise ValueError
            return FinalStandings(class_name, year, self.href)
        else:
            return None


class FinalStandings:
    def __init__(self, class_name, year, href):
        self.class_name = class_name
        self.year = year
        self.href = href

    def __repr__(self):
        return f"FinalStandings(class_name={self.class_name!r}, year={self.year}, href={self.href!r})"

    def __str__(self) -> str:
        global INDENT
        s = get_indent()
        s += f"- championship: {self.class_name}"
        s += "\n"
        INDENT += 2
        s += get_indent()
        s += f'href: "{self.href}"'
        s += "\n"
        INDENT -= 2
        return s


class RaceResult:
    def __init__(self, round, location, year, href):
        self.round = round
        self.location = location
        self.year = year
        self.href = href
        self.official_results = []
        overall_links = self.get_official_results(href)
        if overall_links is None or len(overall_links) == 0:
            print(type(round))
            print(type(year))
            print((round))
            print((year))
            checked_exceptions = [
                ("11", "2007"),
                ("01", "2006"),
                ("02", "2008"),
                ("04", "2007"),
                ("01", "2015"),
                ("02", "2015"),
                ("03", "2015"),
                ("04", "2015"),
                ("05", "2015"),
                ("06", "2015"),
                ("07", "2015"),
                ("08", "2015"),
                ("09", "2015"),
                ("10", "2015"),
                ("11", "2015"),
                ("12", "2015"),
            ]

            found = False
            for check in checked_exceptions:
                r, y = check

                if r == round and y == year:
                    log("Found exception! I continue rather than stop the execution.")
                    found = True
                    break

            if not found:
                raise ValueError(
                    f"No official results found for {round} in {location} in year {year}"
                )

        if overall_links is not None:
            for anchor in overall_links:
                href = anchor.get_attribute("href")
                self.official_results.append(href)
                print(href)

    def get_official_results(self, href):
        home_dir = os.environ.get("HOME")
        chrome_headless_shell_path = f"{home_dir}/chrome-headless-shell-linux64"
        # Configure Chrome options to use headless mode with chrome-headless-shell
        options = webdriver.ChromeOptions()
        options.binary_location = chrome_headless_shell_path
        options.add_argument("--headless")  # Enable headless mode
        options.add_argument("--disable-gpu")  # Disables GPU hardware acceleration
        options.add_argument("--no-sandbox")  # Bypass OS security model for automation
        driver = webdriver.Chrome(options=options)

        log(f"Opening URL {href}")
        driver.get(href)
        try:
            overall_links = WebDriverWait(driver, 3).until(
                EC.presence_of_all_elements_located(
                    (
                        By.XPATH,
                        "//a[span[text()='Official Results']]",
                    )
                )
            )
            log("found official results with xpath kind 1")
            return overall_links
        except:
            try:
                overall_links = WebDriverWait(driver, 3).until(
                    EC.presence_of_all_elements_located(
                        (
                            By.XPATH,
                            "//tr[td[contains(text(), 'Moto #2')]]/following-sibling::tr[td/a[text()='Overall']]/td/a",
                        )
                    )
                )
                log("found official results with xpath kind 2")

                return overall_links
            except:
                try:
                    overall_links = WebDriverWait(driver, 3).until(
                        EC.presence_of_all_elements_located(
                            (
                                By.XPATH,
                                '//a[@href="450_overall.pdf" or @href="250_overall.pdf"]',
                            )
                        )
                    )
                    log("found official results with xpath kind 3")

                    return overall_links
                except:
                    return None

    def __repr__(self):
        return f"RaceResult(round={self.round}, location={self.location!r}, year={self.year}, href={self.href!r})"

    def __str__(self) -> str:
        global INDENT
        s = get_indent()
        s += f'- round: "{self.round}"'
        s += "\n"
        INDENT += 2
        s += get_indent()
        s += f'location: "{self.location}"'
        s += "\n"
        s += get_indent()
        s += f'href: "{self.href}"'
        s += "\n"
        s += get_indent()
        s += f"official_results:\n"
        INDENT += 2
        for href in self.official_results:
            s += get_indent()
            s += f'- "{href}"'
            s += "\n"
        INDENT -= 2
        INDENT -= 2
        return s


class AmaMxResults:
    def __init__(self):
        self._results = []
        home_dir = os.environ.get("HOME")
        chrome_headless_shell_path = (
            f"{home_dir}/programs/chrome-headless-shell-linux64"
        )
        # Configure Chrome options to use headless mode with chrome-headless-shell
        options = webdriver.ChromeOptions()
        options.binary_location = chrome_headless_shell_path
        options.add_argument("--headless")  # Enable headless mode
        options.add_argument("--disable-gpu")  # Disables GPU hardware acceleration
        options.add_argument("--no-sandbox")  # Bypass OS security model for automation
        # options.add_argument("--disable-dev-shm-usage")
        # options.add_argument("--window-size=1920,1080")
        driver = webdriver.Chrome(options=options)
        # driver = webdriver.Chrome()
        log("Load AMA result page ...")
        driver.get("https://americanmotocrossresults.com/events.html")
        time.sleep(2)
        log("Load all links from page ...")
        anchor_elements = driver.find_elements(By.TAG_NAME, "a")
        for anchor in anchor_elements:
            href = anchor.get_attribute("href")
            text = anchor.text.strip()
            link = Link(href, text)
            result = link.get_kind_of_link(driver)
            if result:
                self._results.append(result)
        log("Finished to read main page.")
        driver.quit()

    def __iter__(self):
        return iter(self._results)

    def __getitem__(self, index):
        return self._results[index]

    def __str__(self):
        global INDENT
        results = sorted(
            self._results,
            key=lambda x: (x.year, getattr(x, "round", getattr(x, "class_name", 0))),
        )
        INDENT = 4
        last_year = 0
        s = "americanmotocrossresults:\n"
        for result in results:
            current_year = result.year
            if current_year != last_year:
                INDENT -= 2
                s += get_indent()
                s += f"- {current_year}:"
                s += "\n"
                last_year = current_year
                INDENT += 2
            s += str(result)
        return s


results = AmaMxResults()
with open("official_results.yaml", "w") as file:
    file.write(str(results))
    file.write("\n")
