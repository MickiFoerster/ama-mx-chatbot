import os
import re
import logging
import pandas as pd
from typing import Optional, Tuple, List

US_STATE_IDS = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "US",
]

_current_pos = 0
_result_handler = []
_mx_dirtbike_brands = [
    "HONDA",
    "YAMAHA",
    "KTM",
    "HUSQVARNA",
    "KAWASAKI",
    "SUZUKI",
    "GASGAS",
    "TRIUMPH",
    "DUCATI",
    "STARK",
]

_mx_numbers_found_results = []
_mx_riders_found_results = []
_mx_hometowns_found_results = []
_mx_brands_found_results = []
_mx_tracks_found_results = []
_mx_track_locations_found_results = []
_mx_races = []
_mx_race_results = []


def export_found_data():
    """
    Export all data found during parsing files with parse_result_file()
    """

    csv_filename = "race_results.csv"
    df = pd.DataFrame(_mx_race_results)
    df = df.drop(columns=["round", "kind_of_result", "hometown"])
    df.to_csv(csv_filename, index=False)


def ordinal_suffix(n: int) -> str:
    """Return the ordinal representation of a number."""
    if 10 <= n % 100 <= 20:  # Special case for 11-19
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


class Result:
    def __init__(
        self,
        pos: int,
        num: int,
        driver_name: str,
        hometown: Optional[str],
        bike: Optional[str],
    ):
        self.pos = pos
        self.num = num
        self.driver_name = driver_name
        self.hometown = hometown
        self.bike = bike

        logging.debug(f"New race result created: {repr(self)}")

        global _mx_numbers_found_results
        global _mx_riders_found_results
        global _mx_hometowns_found_results
        global _mx_brands_found_results

        _mx_riders_found_results.append(f"{driver_name}")
        _mx_numbers_found_results.append(num)
        if hometown is not None:
            _mx_hometowns_found_results.append(hometown)

        pattern = r"[a-zA-Z]"
        if bike is not None and len(bike) > 0:
            if bike[0] != "," and re.match(pattern, bike):
                _mx_brands_found_results.append(bike)

    def __str__(self) -> str:
        # Basic format: "#<position>. <driver> (#<number>)"
        result = f"{self.pos}. {self.driver_name} (#{self.num})"

        # Add optional information if available
        if self.hometown:
            result += f" from {self.hometown}"
        if self.bike:
            result += f" on {self.bike}"

        return result

    def __repr__(self) -> str:
        return (
            f"\n\tResult(pos={self.pos}, num={self.num}, "
            f"name='{self.driver_name}', hometown={repr(self.hometown)}, "
            f"bike={repr(self.bike)})"
        )

    def as_prompt(self) -> str:
        result = f"  {self.num}      {self.pos}     {self.driver_name}    "

        if self.bike:
            result += f"{self.bike}"

        return result


class RaceResult:
    def __init__(
        self,
        track_name: Optional[str],
        track_location: Optional[str],
        round: Optional[int],
        race_date: Optional[str],
        class_name: Optional[str],
        kind_of_result: Optional[str],
        results: List[Result],
        source: str,
        store_to_static_vars: bool = True,
    ):
        self.track_name = track_name
        self.track_location = track_location
        self.round = round
        self.race_date = race_date
        self.class_name = class_name
        self.kind_of_result = kind_of_result
        self.results = results
        self.source = source

        if store_to_static_vars:
            global _mx_tracks_found_results
            global _mx_track_locations_found_results
            global _mx_race_results
            global _mx_races

            _mx_tracks_found_results.append(track_name)
            _mx_track_locations_found_results.append(track_location)
            _mx_races.append(
                f"{self.race_date}: race on track '{self.track_name}' in {self.track_location}"
            )

            csv_data = self.to_csv()
            for d in csv_data:
                _mx_race_results.append(d)

    def __str__(self) -> str:
        # Build header with available information
        header_parts = []
        if self.track_name:
            header_parts.append(self.track_name)
        if self.track_location:
            header_parts.append(self.track_location)
        if self.round:
            header_parts.append(f"Round {self.round}")
        if self.race_date:
            header_parts.append(self.race_date)
        if self.class_name:
            header_parts.append(self.class_name)
        if self.kind_of_result:
            header_parts.append(self.kind_of_result)

        header = f"Results from file {self.source}\n" + " - ".join(header_parts)

        # Format results
        result_strings = [str(result) for result in self.results]
        results_section = "\n".join(result_strings)

        return f"{header}\n\n{results_section}"

    def __repr__(self) -> str:
        return (
            f"Race results from file {self.source}\n\ttrack_name={repr(self.track_name)},\n"
            f"\ttrack_location={repr(self.track_location)},\n"
            f"\tround={repr(self.round)}, race_date={repr(self.race_date)},\n"
            f"\tclass_name={repr(self.class_name)},\n"
            f"\tkind_of_result={repr(self.kind_of_result)},\n"
            f"\tresults={repr(self.results)})\n"
        )

    def as_prompt(self, only_top10: bool = False, only_top3: bool = False) -> str:
        if (
            self.track_name
            and self.race_date
            and self.track_location
            and self.class_name
        ):
            header = f"### Race Results from track {self.track_name} on {self.race_date} of class {self.class_name}\n\n"
        else:
            header = "### Race Results\n\n"

        header += "number  position  name              bike"

        # Format results
        if only_top3:
            max = 3
        elif only_top10:
            max = 10
        else:
            max = 50

        result_strings = [
            result.as_prompt() for result in self.results if result.pos <= max
        ]

        results_section = "\n".join(result_strings)

        return f"{header}\n{results_section}\n"

    def to_csv(self):
        data = []
        id_counter = 1

        # FIXME: replace source with online reference. This MUST not be
        # in pushed version.
        source = self.source.replace("/home/micki/1tb/", "https://")
        source = source.replace(".txt", ".pdf")

        if self.race_date is not None:
            pattern = r"20[0-9]{2}"
            match = re.search(pattern, self.race_date)
            if match:
                year = match.group(0)
            else:
                year = None
        else:
            year = None

        for result in self.results:
            data.append(
                {
                    "track_name": self.track_name,
                    "track_location": self.track_location,
                    "round": str(self.round),
                    "year": year,
                    "race_date": self.race_date,
                    "class_name": self.class_name,
                    "kind_of_result": self.kind_of_result,
                    "position": result.pos,
                    "number": result.num,
                    "driver_name": result.driver_name,
                    "hometown": result.hometown,
                    "mx_bike": result.bike,
                    "source": source,
                }
            )

            id_counter += 1

        return data


def parse_result_file(
    path: str, race_track: Optional[str] = None
) -> Optional[RaceResult]:
    """
    Opens a .txt file with AMA motocross results. This .txt file is assumed to
    be created by library pdfplumber from the original PDF file from the
    website of americanmotocross.com.
    """
    global _current_pos
    global _result_handler

    _current_pos = 0
    _result_handler = []

    if not os.path.exists(path):
        logging.warning(f"File {path} does not exist.")

        return None

    track_name = race_track
    track_location = None
    round = None
    race_date = None
    class_name = None
    next_line_is_class_name = False
    kind_of_result = None
    next_line_is_kind_of_result = False
    results = []

    with open(path, "r") as file:
        content = file.read()

    # pdfplumber converts some lines to only the race position in one line and
    # remaining data in the next line.
    content = re.sub(r"^([0-9]+)\n([0-9]+)", r"\1 \2", content, flags=re.MULTILINE)

    for line in content.splitlines():
        line = line.strip()
        logging.debug(f"parse line: {line}")

        if track_location is None:
            logging.debug("track_location is None")
            track_location = _get_track_location(line)
            if track_location is not None:
                logging.debug("track_location is not None")
                if track_name is None:
                    track_name = line.split(" - ")[0]
                    logging.debug(
                        f"FOUND track: {track_name} is located in {track_location}"
                    )
                continue  # with next line

        if round is None:
            logging.debug("round is None")
            round = _get_round(line)
            if round is not None:
                logging.debug("round is not None")
                race_date = _get_race_date(line)
                next_line_is_class_name = True
                logging.debug(f"FOUND round and date: {round} and {race_date}")
                continue

        if next_line_is_class_name:
            logging.debug("next_line_is_class_name is True")
            next_line_is_class_name = False
            class_name = line
            next_line_is_kind_of_result = True
            logging.debug(f"FOUND class name: {class_name}")
            continue

        if next_line_is_kind_of_result:
            logging.debug("next_line_is_kind_of_result is True")
            next_line_is_kind_of_result = False
            kind_of_result = line
            logging.debug(f"FOUND kind of result: {kind_of_result}")
            continue

        result = None
        result = _get_result(line)
        logging.debug(f"result is {result}")
        if result is not None:
            results.append(result)

    if len(results) == 0:
        return None

    return RaceResult(
        track_name,
        track_location,
        round,
        race_date,
        class_name,
        kind_of_result,
        results,
        path,
    )


def _get_track_location(line: str) -> Optional[str]:
    for state_id in US_STATE_IDS:
        pattern1 = f", {state_id}"
        idx = line.find(pattern1)
        if idx >= 0:
            pattern2 = r"[A-Za-z]+" + pattern1
            match = re.search(pattern2, line)
            if match:
                return match[0]

    idx = line.find(" - ")
    if idx > 0:
        track_location = line[idx + 3 :]
        return track_location

    return None


def _get_round(line: str) -> Optional[int]:
    pattern = "ROUND "
    idx = line.find(pattern)
    if idx >= 0:
        line = line[len(pattern) :]
        try:
            round = int(line.split(" ")[0])

            return round
        except ValueError:
            return None

    return None


def _get_race_date(line: str) -> Optional[str]:
    pattern = "ROUND "
    idx = line.find(pattern)
    if idx >= 0:
        line = line[len(pattern) :]
        idx = line.find(" - ")
        if idx >= 0:
            return line.split(" - ")[1]

    return None


def _result_handler_pos(line: str) -> Optional[Tuple[str, str]]:
    global _current_pos

    lst = line.split(" ")
    try:
        pos = int(lst[0])

        if _current_pos == pos:
            _current_pos += 1

            remaining_line = " ".join(lst[1:]).strip()

            return (str(pos), remaining_line)
    except:
        pass

    return None


def _result_handler_num(line: str) -> Optional[Tuple[str, str]]:
    lst = line.split(" ")
    try:
        num = int(lst[0])

        if 0 < num and num < 1000:
            remaining_line = " ".join(lst[1:]).strip()

            return (str(num), remaining_line)
    except:
        pass

    return None


def _result_handler_driver(line: str) -> Optional[Tuple[str, str]]:
    """
    Check for two kind of names:
        - Firstname M. Lastname
        - Firstname Lastname
    """

    line = line.strip()

    pattern1 = r"^([A-Z][a-z]+)\s+[A-Z]\.?\s+([A-Z][A-Za-z]+) "  # e.g., "JOHN A. SMITH"
    pattern2 = r"^([A-Z][a-z]+)\s+([A-Z][A-Za-z]+) "  # e.g., "JOHN SMITH"

    for pattern in [pattern1, pattern2]:
        match = re.search(pattern, line)
        if match:
            # print("found match: ", match)

            firstname = match.group(1)
            lastname = match.group(2)
            remaining_line = line[match.end() :]

            idx = remaining_line.upper().find("JR.")
            if idx >= 0:
                remaining_line = remaining_line[idx + 3 :]

            # Return the corresponding portion of the original text
            return (f"{firstname} {lastname}", remaining_line)

    return None


def _result_handler_hometown(line: str) -> Optional[Tuple[str, str]]:
    # If no hometown is given the bike brand is next.
    line = line.strip()
    first_word = line.split(" ")[0]

    # Cases where some number instead of hometown such as 2.123
    try:
        float(first_word)
        return None
    except:
        pass

    global _mx_dirtbike_brands
    if first_word.upper() in _mx_dirtbike_brands:
        return None

    countries = [
        "AUSTRALIA",
        "AUSTRAILIA",
        "BELGIUM",
        "BOLIVIA",
        "BRAZIL",
        "CANADA",
        "CHILE",
        "CHINA",
        "COSTA RICA",
        "CZECH REPUBLIC",
        "DENMARK",
        "DOMINICAN REPUBLIC",
        "ECUADOR",
        "ENGLAND",
        "ESTONIA",
        "FINLAND",
        "FRANCE",
        "GERMANY",
        "GREAT BRITAIN",
        "GREAT BRITIAN",
        "GUAM",
        "HONDURAS",
        "IRAN",
        "IRELAND",
        "ITALY",
        "JAPAN",
        "KOREA",
        "LITHUANIA",
        "MEXICO",
        "NETHERLAND",
        "NEW JERSEY",
        "NEW ZEALAND",
        "NORWAY",
        "PERU",
        "RUSSIA",
        "SCOTLAND",
        "SOUTH AFRICA",
        "SPAIN",
        "SPRINGFIELD",
        "SWEDEN",
        "SWITZERLAND",
        "UNITED KINGDOM",
        "UGANDA",
        "URUGUAY",
        "VENEZUELA",
        "VIETNAM",
        "ZAMBIA",
        "WHITEHALL",
        "PHILLIPPINES",
        "IRWIN",
        "GROVELAND",
        "MENIFEE",
        "MURRIETA, CA",
        "WHITE BEAR LAKE",
        "GRANITE BAY",
        "MONTGOMERY",
        "BAKERSFIELD",
        "SAO PAULO",
        "ALAJUELA",
        "WILDOMAR",
    ]

    for country in countries:
        idx = line.upper().find(country)
        if idx >= 0:
            remaining_line = line[idx + len(country) :]

            # Look for US state_id
            for state_id in US_STATE_IDS:
                pattern = f", {state_id}"
                idx = remaining_line.find(pattern)
                if idx >= 0:
                    remaining_line = remaining_line[idx + len(pattern) :]

            return (country, remaining_line)

    idx = line.find(",")
    if idx >= 0:
        lst = line.upper().split(",")
        city, state_id = lst[0].strip(), lst[1].strip().split(" ")[0]

        hometown = f"{city}, {state_id}"

        pattern = f", {state_id}"
        idx = line.find(pattern)
        if idx >= 0:
            remaining_line = line[idx + len(pattern) :].strip()

            return (hometown, remaining_line)

    # Look for US state_id
    for state_id in US_STATE_IDS:
        pattern = f"{state_id}"
        idx = line.find(pattern)
        if idx >= 0:
            hometown = line[: idx + len(pattern)].strip()

            remaining_line = line[idx + len(pattern) :]

            return (hometown, remaining_line)

    logging.warning(f"cannot find hometown in {line}")

    return None


def _result_handler_bike(line: str) -> Optional[Tuple[str, str]]:
    for brand in _mx_dirtbike_brands:
        idx = line.upper().find(brand)
        if idx >= 0:
            line = line[idx:]
            break

    lst = line.split(" ")

    bike = []
    for i, l in enumerate(lst):
        if i < 2:
            bike.append(l)
        else:
            if i > 3:
                break

            try:
                n = int(l)
                if n == 125 or n == 250 or n == 450 or n == 500:
                    bike.append(l)
            except:
                if l.find(":") < 0 & l.find("+") < 0:
                    bike.append(l)

    if len(bike) > 0:
        bike = " ".join(bike).strip()

        remaining_line = line[len(bike) :]

        return (bike, remaining_line)

    return None


_result_handler_functions = {
    _result_handler_pos: "_result_handler_pos",
    _result_handler_num: "_result_handler_num",
    _result_handler_driver: "_result_handler_driver",
    _result_handler_hometown: "_result_handler_hometown",
    _result_handler_bike: "_result_handler_bike",
}


def _get_result(line: str) -> Optional[Result]:
    global _current_pos
    global _result_handler
    global _result_handler_functions

    if line.upper().startswith("POS"):
        if _current_pos == 0:
            _current_pos = 1
            _result_handler.append(_result_handler_pos)

            pattern = " # "
            idx = line.find(pattern)
            if idx >= 0:
                _result_handler.append(_result_handler_num)
                line = line[idx + len(pattern) :]

            pattern = "NAME "
            idx = line.upper().find(pattern)
            if idx >= 0:
                _result_handler.append(_result_handler_driver)
                line = line[idx + len(pattern) :]
            else:
                pattern = "RIDER "
                idx = line.upper().find(pattern)
                if idx >= 0:
                    _result_handler.append(_result_handler_driver)
                    line = line[idx + len(pattern) :]

            pattern = "HOMETOWN "
            idx = line.upper().find(pattern)
            if idx >= 0:
                _result_handler.append(_result_handler_hometown)
                line = line[idx + len(pattern) :]

            pattern = "BIKE "
            idx = line.upper().find(pattern)
            if idx >= 0:
                _result_handler.append(_result_handler_bike)
                line = line[idx + len(pattern) :]

        return None

    if _current_pos > 0:
        pos = None
        num = None
        driver = None
        hometown = None
        bike = None

        for handler in _result_handler:
            result = handler(line)
            logging.debug(
                f"pos={pos}, num={num}, driver={driver}, hometown={hometown}, bike={bike}"
            )
            if result is not None:
                (token, line) = result

                match _result_handler_functions.get(handler, "Unknown handler"):
                    case "_result_handler_pos":
                        pos = int(token)
                    case "_result_handler_num":
                        num = int(token)
                    case "_result_handler_driver":
                        driver = token
                    case "_result_handler_hometown":
                        hometown = token
                    case "_result_handler_bike":
                        bike = token
                    case _:
                        raise ValueError("Unknown result handler function")
            else:
                # In case POS could not parsed successfully, we skip the
                # remaining handlers.
                if (
                    _result_handler_functions.get(handler, "Unknown handler")
                    == "_result_handler_pos"
                ):
                    break

        if pos is not None and num is not None and driver is not None:
            return Result(pos, num, driver, hometown, bike)

    return None


def from_dataframe_to_race_results(df: pd.DataFrame) -> List[RaceResult]:
    sorted_df = df.sort_values(by=["source", "position"])
    if isinstance(sorted_df, pd.Series):
        sorted_df = sorted_df.to_frame()

    sources = sorted_df["source"].unique().tolist()

    race_results = []
    for source in sources:
        filtered_df = sorted_df[sorted_df["source"] == source]

        results = []
        track_name = filtered_df.iloc[0]["track_name"]
        track_location = filtered_df.iloc[0]["track_location"]
        race_date = filtered_df.iloc[0]["race_date"]
        class_name = filtered_df.iloc[0]["class_name"]
        source = filtered_df.iloc[0]["source"]

        for row in filtered_df.itertuples(index=False):
            result = Result(
                pos=int(row.position),
                num=int(row.number),
                driver_name=str(row.driver_name),
                hometown=None,
                bike=str(row.mx_bike),
            )

            results.append(result)

        race_result = RaceResult(
            track_name=track_name,
            track_location=track_location,
            round=None,
            race_date=race_date,
            class_name=class_name,
            kind_of_result=None,
            results=results,
            source=source,
            store_to_static_vars=False,
        )

        race_results.append(race_result)

    return race_results
