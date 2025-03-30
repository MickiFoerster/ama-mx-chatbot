import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import sys
import os
import pandas as pd
from typing import List
import logging

# Global vector database for driver names
DRIVERS_VEC_DB = None

# Storage path for persistence
DRIVERS_DB_PATH = "./chroma_db_drivers"


def get_drivers(race_results: pd.DataFrame, driver: str) -> List[str]:
    global DRIVERS_VEC_DB

    _init_db(race_results)

    if DRIVERS_VEC_DB is None:
        return []

    nearest_drivers = DRIVERS_VEC_DB.query(query_texts=[driver], n_results=5)

    # Check that response is as expected
    if (
        nearest_drivers is None
        or not isinstance(nearest_drivers, dict)
        or nearest_drivers.get("documents") is None
        or nearest_drivers.get("distances") is None
    ):
        logging.error(
            f"Query to driver vector database for driver '{driver}' had an unexpected result: {nearest_drivers}"
        )
        return []

    assert nearest_drivers is not None
    assert nearest_drivers["documents"] is not None
    assert nearest_drivers["distances"] is not None

    logging.info(f"{nearest_drivers["documents"][0]}")
    logging.info(f"{nearest_drivers["distances"][0]}")

    drivers = []
    for index, dist in enumerate(nearest_drivers["distances"][0]):
        d = nearest_drivers["documents"][0][index]
        # If we have exact match then take this driver and return
        if dist <= 0.1:
            # Just take current driver and end search.
            drivers = [d]
            break
        elif dist <= 1.5:
            drivers.append(d)

    return drivers


def _init_db(race_results: pd.DataFrame):
    """Initializes the vector database and persists it to disk."""

    global DRIVERS_VEC_DB
    global DRIVERS_DB_PATH

    if DRIVERS_VEC_DB is not None:
        logging.info("Vector database with drivers was already initialized.")
        return

    logging.info("Initialization of drivers vector database ...")

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key is None or not api_key.startswith("sk-proj-"):
        logging.error(
            "OpenAI API key is not set correctly. Check env variable OPENAI_API_KEY."
        )
        raise ValueError("OPENAI_API_KEY is not set")

    embedding_function = OpenAIEmbeddingFunction(
        api_key=api_key, model_name="text-embedding-3-small"
    )

    chroma_client = chromadb.PersistentClient(path=DRIVERS_DB_PATH)

    collection_name = "drivers"

    # Check if the collection already exists
    if collection_name in chroma_client.list_collections():
        logging.info("Loading existing vector database from disk ...")
        DRIVERS_VEC_DB = chroma_client.get_collection(
            name=collection_name, embedding_function=embedding_function
        )
    else:
        logging.info("Creating new vector database from scratch ...")
        collection = chroma_client.create_collection(
            name=collection_name, embedding_function=embedding_function
        )

        drivers = race_results["driver_name"].unique().tolist()

        collection.add(
            documents=drivers,
            ids=[str(i) for i in range(0, len(drivers))],
        )
        logging.info("done")

        DRIVERS_VEC_DB = collection
