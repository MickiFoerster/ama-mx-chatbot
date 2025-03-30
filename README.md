# Motocross Result Chatbot

## Overview

This repository contains code for a chatbot that can held conversations about 
motocross results of the American Motorsports Association (AMA) which can be 
found [here](https://americanmotocrossresults.com/).

![Chatbot Demo](assets/chatbot.gif)

## Setup

1. Set your OpenAI API Key as environment variable:

```bash
OPENAI_API_KEY="sk-..."
```

2. Create a local virtual environment, for example using the `venv` module. Then, activate it.

```bash
python -m venv venv
source venv/bin/activate
```

3. Install the dependencies.

```bash
pip install -r requirements.txt
```

4. Launch the Gradio app.

```bash
python app.py
```

## Implementation Details

The [website](https://americanmotocrossresults.com/) contains PDF files with
results from the last two decades. These PDF files were processed with help of
PDFplumber library and converted into text. The python module
americanmotocrossresults contains a function parse_result_file() which takes a
path to a text file and starts to parse the content. It reads all race results
and corresponding metadata about the race. The file race_results.csv is the result of parsing all the available PDF results.

This files looks as follows:
```csv
track_name,track_location,year,race_date,class_name,position,number,driver_name,mx_bike,source
HIGH POINT,"MORRIS, PA",2004,"MAY 30, 2004",125 Motocross,1,259,James Stewart,Kawasaki KX125,https://americanmotocrossresults.com/live/archives/mx/2004/02-mt_morris/125overall.pdf
HIGH POINT,"MORRIS, PA",2004,"MAY 30, 2004",125 Motocross,2,60,Broc Hepler,Suzuki RM-Z250,https://americanmotocrossresults.com/live/archives/mx/2004/02-mt_morris/125overall.pdf
HIGH POINT,"MORRIS, PA",2004,"MAY 30, 2004",125 Motocross,3,3,Michael Brown,Yamaha YZ250F,https://americanmotocrossresults.com/live/archives/mx/2004/02-mt_morris/125overall.pdf
HIGH POINT,"MORRIS, PA",2004,"MAY 30, 2004",125 Motocross,4,122,Matt Walker,Kawasaki KX250F,https://americanmotocrossresults.com/live/archives/mx/2004/02-mt_morris/125overall.pdf
```
and is available on hugging face [here](mickey45/americanmotocrossresults). The
data from this file is used to provide the LLM per RAG with a knowledge base it
does not have from its pretrained knowledge. The file size of the CSV data is
3mb and therefore to big to provide in each call to the LLM. Therefore, we need
to reduce the data to the one that is important for the users query. This is
done by calling the LLM twice. The first call to the LLM show the header of the
CSV file and the users query. The LLM is being instructed to answer with the
column header names which should be searched and the corresponding values. The
LLM answers then e.g. with 
```
driver_name: James Stewart
```

In order to allow also typos or variants of driver or track names we use
chrombadb library to build a vector database as lookup table for drivers and
tracks that are close to the value the user is referring to. For example the 
user query "Results of James steward in 2011?" results then in vector database
search for drivers:
```
drivers:   ['James Stewart', 'Malcolm Stewart', 'Ronnie Stewart', 'Bryce Stewart', 'Clark Stiles']
distances: [1.8729542716755532e-06, 0.6615568399429321, 0.6827191710472107, 0.7818885445594788, 1.035943627357483]

```

Once the information what columns of the CSV data should be searched is ready,
this is used to retrieve the information the user wants to know. This is then
used to create the second request to the LLM. This is then the actual answer the
user gets to see.
