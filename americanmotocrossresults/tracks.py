import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import sys
import os
import pandas as pd
from typing import List
import logging

# Global vector database for track names
TRACKS_VEC_DB = None

# Storage path for persistence
TRACKS_DB_PATH = "./chroma_db_tracks"


def get_tracks(race_results: pd.DataFrame, track: str) -> List[str]:
    global TRACKS_VEC_DB

    _init_db(race_results)

    if TRACKS_VEC_DB is None:
        return []

    nearest_tracks = TRACKS_VEC_DB.query(query_texts=[track], n_results=5)

    # Check that response is as expected
    if (
        nearest_tracks is None
        or not isinstance(nearest_tracks, dict)
        or nearest_tracks.get("documents") is None
        or nearest_tracks.get("distances") is None
    ):
        logging.error(
            f"Query to track vector database for track '{track}' had an unexpected result: {nearest_tracks}"
        )
        return []

    assert nearest_tracks is not None
    assert nearest_tracks["documents"] is not None
    assert nearest_tracks["distances"] is not None

    logging.info(f"{nearest_tracks["documents"][0]}")
    logging.info(f"{nearest_tracks["distances"][0]}")

    tracks = []
    for index, dist in enumerate(nearest_tracks["distances"][0]):
        d = nearest_tracks["documents"][0][index]
        if dist <= 1.5:
            tracks.append(d)

    return tracks


def _init_db(race_results: pd.DataFrame):
    """Initializes the vector database and persists it to disk."""

    global TRACKS_VEC_DB
    global TRACKS_DB_PATH

    if TRACKS_VEC_DB is not None:
        logging.info("Vector database with tracks was already initialized.")
        return

    logging.info("Initialization of tracks vector database ...")

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key is None or not api_key.startswith("sk-proj-"):
        logging.error(
            "OpenAI API key is not set correctly. Check env variable OPENAI_API_KEY."
        )
        raise ValueError("OPENAI_API_KEY is not set")

    embedding_function = OpenAIEmbeddingFunction(
        api_key=api_key, model_name="text-embedding-3-small"
    )

    chroma_client = chromadb.PersistentClient(path=TRACKS_DB_PATH)

    collection_name = "tracks"

    # Check if the collection already exists
    if collection_name in chroma_client.list_collections():
        logging.info("Loading existing vector database from disk ...")
        TRACKS_VEC_DB = chroma_client.get_collection(
            name=collection_name, embedding_function=embedding_function
        )
    else:
        logging.info("Creating new vector database from scratch ...")
        collection = chroma_client.create_collection(
            name=collection_name, embedding_function=embedding_function
        )

        tracks = race_results["track_name"].unique().tolist()

        collection.add(
            documents=tracks,
            ids=[str(i) for i in range(0, len(tracks))],
        )
        logging.info("done")

        TRACKS_VEC_DB = collection
