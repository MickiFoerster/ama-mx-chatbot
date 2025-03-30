import logging
import openai
import os
import pandas as pd
import copy

from datetime import date
from jinja2 import Environment, FileSystemLoader
from pprint import pprint
from typing import List, Dict, Optional

from . import drivers, from_dataframe_to_race_results
from . import tracks

MODEL_FOR_CSV_HEADER = "gpt-4o-mini"
MODEL_FOR_USER_RESPONSE = "gpt-4o-mini"

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

RACE_RESULTS_CSV_FILENAME = os.path.join(MODULE_DIR, "race_results.csv")

# Global object for CSV file data
RACE_RESULTS = None

J2_FILE_PROMPT_HEADLINES = "prompt_for_involved_csv_headlines.j2"
J2_FILE_PROMPT_FINAL_OUTPUT = "prompt_for_final_output.j2"

SYSTEM_PROMPT_FOR_FINDING_HEADLINES = """
You are an helpful assistant in transforming user queries into names of CSV 
headlines. If you cannot transform the user query into CSV headlines then 
answer with REDIRECT_TO_NEXT_LLM.
"""

SYSTEM_PROMPT_FOR_FINAL_OUTPUT = """
You are an helpful assistant that provides motocross results of the American
Motorcyclist Association (AMA) from the year 2004 on forward. You can list race
results in a tabular form. You are an expert in motocross. The user may ask you
anything about the AMA races or results. If you don't know the answer then start
your answer with "Mmmh, " and respond that you are not sure to what the user is
referring to and suggest to have a conversation about certain motocross drivers
or tracks. Only answer with motocross results from the AMA championship in USA.
Don't make something up. 
"""


def chat(message, history):
    logging.basicConfig(level=logging.INFO)

    global RACE_RESULTS

    if RACE_RESULTS is None:
        RACE_RESULTS = _load_results_csv()

    headlines = _find_csv_headlines(RACE_RESULTS, message, history)
    if len(headlines) == 0:
        yield from _create_final_response(message, pd.DataFrame(), {}, history)

        return

    search_criterias = _get_search_criterias(RACE_RESULTS, headlines)
    pprint(search_criterias)

    results = _get_filtered_results(RACE_RESULTS, search_criterias)
    pprint(results)

    # If too many results then don't overload LLM
    max_results = 15000
    if len(results) > max_results:
        logging.warning("Too many results were found. This indicates a bad filter.")
        results = results[:max_results]
        if isinstance(results, pd.Series):
            results = results.to_frame()

    # Call LLM to get user response
    yield from _create_final_response(message, results, search_criterias, history)


def _get_filtered_results(
    race_results: pd.DataFrame, search_criterias: Dict
) -> pd.DataFrame:
    # Create a boolean mask that contains True for all values
    mask = pd.Series(True, index=race_results.index)

    for header_name, patterns in search_criterias.items():
        # Convert to lower case when column contains strings
        if race_results[header_name].dtype == "object":
            lower_col_values = race_results[header_name].astype(str).str.lower()
            lower_patterns = {p.lower() for p in patterns}

            # Apply the filter
            mask &= lower_col_values.isin(lower_patterns)
        else:
            # Combine different column criterias per logical AND
            mask &= race_results[header_name].isin(patterns)

    # Apply the resulting mask to the data frame
    filtered_df = race_results[mask]
    logging.info(f"Filtered search found {len(filtered_df)} results")

    if isinstance(filtered_df, pd.Series):
        filtered_df = filtered_df.to_frame()

    # Sort dataframe by year, round, and position
    sorted_df = filtered_df.sort_values(
        by=["year", "race_date", "class_name", "position"]
    )

    results = sorted_df

    if isinstance(results, pd.Series):
        results = results.to_frame()

    return results


def _get_search_criterias(race_results: pd.DataFrame, headlines: List[str]) -> Dict:
    search = {}

    for column in headlines:
        logging.info(f"search criteria: {column}")
        if "driver_name:" in column:
            driver = column.split(":")[1].strip()
            logging.info(f"Found driver name: {driver}")

            patterns = drivers.get_drivers(race_results, driver)

            search.setdefault("driver_name", []).extend(patterns)
            logging.info("We look for driver_name: {}".format(search["driver_name"]))
        elif "track_name:" in column:
            track_name = column.split(":")[1].strip()
            logging.info(f"Found track name: {track_name}")

            patterns = tracks.get_tracks(race_results, track_name)

            search.setdefault("track_name", []).extend(patterns)
            logging.info("We look for track_name: {}".format(search["track_name"]))
        else:
            if column.find(":") >= 0:
                lst = column.split(":")
                key = lst[0].strip()
                value = lst[1].strip()
            else:
                logging.error("unexpected answer from LLM: {column}")
                key = column
                value = ""

            if race_results[key].dtype == "object":
                search.setdefault(key, []).append(value)
            else:
                search.setdefault(key, []).append(pd.to_numeric(value))

    return search


def _create_final_response(
    user_query: str, results: pd.DataFrame, search_criterias: Dict, history: List
):
    """
    This function uses RAG to give the LLM the necessary details for a proper
    response.

    Take results and insert them into prompt. Then call LLM and return its
    response to the caller.
    """

    drivers = search_criterias.get("driver_name")
    if drivers is None:
        drivers = []

    num_of_results = int(len(results))

    if num_of_results > 0:
        lst = []
        race_results = from_dataframe_to_race_results(results)

        if num_of_results > 1000:
            lst.append(
                f"Since we found {num_of_results} results in the archive, we only give you top 3 positions."
            )

            lst.extend([result.as_prompt(only_top3=True) for result in race_results])
        elif num_of_results > 100:
            lst.append(
                f"Since we found {num_of_results} results in the archive, we only give you top 10 positions."
            )

            lst.extend([result.as_prompt(only_top10=True) for result in race_results])
        else:
            lst.extend([result.as_prompt() for result in race_results])

        results_txt = "\n".join(lst)
    else:
        results_txt = ""

    env = Environment(loader=FileSystemLoader(MODULE_DIR))
    template = env.get_template(J2_FILE_PROMPT_FINAL_OUTPUT)
    rendered = template.render(
        {
            "user_query": user_query,
            "drivers": drivers,
            "results_txt": results_txt,
            "num_of_results": num_of_results,
            "today": date.today(),
        }
    )

    messages = copy.deepcopy(history)
    messages.append({"role": "user", "content": rendered})

    messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT_FOR_FINAL_OUTPUT})

    _dump_llm_conversation(messages)

    yield from _LLM_chat_completion_stream(
        model=MODEL_FOR_USER_RESPONSE, messages=messages
    )


def _find_csv_headlines(
    race_results: pd.DataFrame, user_query: str, history: List
) -> List[str]:
    """
    This function returns a list of column names of the race result CSV that
    need to be searched for values contained in the user query.

    For example, the user query
    "I need all results from 2004 from Jeffrey Herlings."
    should be answered by the LLM with
    ```
    driver_name: Jeffrey Herlings
    year: 2004
    ```
    """
    sample = (
        race_results.sample(n=10, random_state=42)
        .drop(columns=["source"])
        .to_string(index=False)
    )

    track_list = race_results["track_name"].unique().tolist()

    env = Environment(loader=FileSystemLoader(MODULE_DIR))
    template = env.get_template(J2_FILE_PROMPT_HEADLINES)

    rendered = template.render(
        {
            "random_sample_from_csv": sample,
            "history": history,
            "tracks": "\n".join(track_list),
            "today": date.today(),
        }
    )

    messages = _create_user_assistant_chat([rendered], ["OK"])

    user_content = []
    for msg in history:
        if msg["role"] == "user":
            user_content.append(f"{msg["content"]}")
    previous_user_content = "\n".join(user_content)

    instruct_llm = f"""
The user gave the following queries in the past:
{previous_user_content}

The current user query is:
{user_query}

I want you to focus on the current user query but consider also the previous 
queries to understand the context. With this respond with the columns the user
refers to.
"""

    messages.append({"role": "user", "content": instruct_llm})

    messages.insert(
        0, {"role": "system", "content": SYSTEM_PROMPT_FOR_FINDING_HEADLINES}
    )

    _dump_llm_conversation(messages)

    response = _LLM_chat_completion(model=MODEL_FOR_CSV_HEADER, messages=messages)
    logging.info(response)

    if response is None:
        return []
    if response is not None and "REDIRECT_TO_NEXT_LLM" in response:
        return []

    cols = []
    for line in response.split("\n"):
        if "```" in line:
            continue
        else:
            cols.append(line)

    return cols


def _load_results_csv() -> pd.DataFrame:
    return pd.read_csv(RACE_RESULTS_CSV_FILENAME)


def _create_user_assistant_chat(user: List[str], assistant: List[str]) -> List:
    if len(user) != len(assistant):
        logging.error(
            "Cannot create user, assistant chat with arrays not having the same size."
        )
        return []

    messages = []
    for q, a in zip(user, assistant):
        messages.append({"role": "user", "content": q})
        messages.append({"role": "assistant", "content": a})

    return messages


def _LLM_chat_completion(model: str, messages: List) -> Optional[str]:
    if model.startswith("gpt-"):
        return _OpenAI_chat_completion(model, messages)
    else:
        raise ValueError("Other LLMs than gpt-* are not implemented yet")


def _LLM_chat_completion_stream(model: str, messages: List):
    if model.startswith("gpt-"):
        yield from _OpenAI_chat_completion_stream(model, messages)
    else:
        raise ValueError("Other LLMs than gpt-* are not implemented yet")


def _OpenAI_chat_completion(model: str, messages: List) -> Optional[str]:
    """
    Call OpenAI API and return complete response.
    """
    if len(messages) == 0:
        return None

    try:
        response = openai.OpenAI().chat.completions.create(
            model=model, messages=messages
        )
        logging.info(f"OpenAI response: {response}")

        # Validate response structure before accessing elements
        if not response or not hasattr(response, "choices") or not response.choices:
            logging.warning("OpenAI response has no choices.")

            return None

        content = response.choices[0].message.content
        return content if content else None

    except openai.OpenAIError as e:
        logging.error(f"OpenAI API error: {e}")
        return f"Error: OpenAI API failed - {str(e)}"

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return f"Error: Unexpected issue - {str(e)}"


def _OpenAI_chat_completion_stream(model: str, messages: List):
    """
    This function is a generator.
    Call to OpenAI and generate stream of tokens as response.
    """

    if len(messages) == 0:
        yield None

    # Check whether there is already a system prompt, otherwise set it.
    if messages[0]["role"] != "system":
        logging.error("You need to give a system prompt.")
        sys.exit(1)

    try:
        response = openai.OpenAI().chat.completions.create(
            model=model, messages=messages, stream=True
        )

        accumulated_response = ""

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                accumulated_response += token
                yield accumulated_response

    except openai.OpenAIError as e:
        logging.error(f"OpenAI API error: {e}")
        yield f"Error: OpenAI API failed - {str(e)}"

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        yield f"Error: Unexpected issue - {str(e)}"


def _dump_llm_conversation(messages: List[Dict]):
    for msg in messages:
        print(
            f"""
## {msg["role"]}

{msg["content"]}
###############################################################################
"""
        )
