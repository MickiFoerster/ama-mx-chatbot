import pdfplumber
import os
import logging
import glob
from typing import List
from tqdm import tqdm


def convert2text(pdf_path) -> List[str]:
    text = []

    if not os.path.exists(pdf_path):
        logging.error(f"error: File {pdf_path} does exist.\n")
        return []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            logging.debug(f"pages: {pdf.pages}")
            for page_num, page in enumerate(pdf.pages, start=1):
                logging.debug(f"Try to extract text from page {page_num}")
                text.append(page.extract_text())
    except Exception as e:
        logging.warning(f"File {pdf_path} could not be processed by pdfplumber: {e}")

    return text


logging.basicConfig(level=logging.INFO)

pdf_files = glob.glob("**/*.pdf", recursive=True)

for path in tqdm(pdf_files, desc="Processing PDFs", unit="file"):
    logging.debug(f"Extract text from file {path}.")
    text = convert2text(path)

    if len(text) == 0:
        logging.warning(f"No text found in file {path}.")

    txt_path = os.path.splitext(path)[0] + ".txt"
    with open(txt_path, "w") as file:
        for t in text:
            file.write(t)

    logging.debug(f"Text from PDF has been written to file {txt_path}.")
