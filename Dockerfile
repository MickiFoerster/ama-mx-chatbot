FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y g++ curl xz-utils tar && \
    apt-get clean

COPY requirements.txt . 
COPY americanmotocrossresults . 
COPY app.py . 
COPY . . 

RUN sed -i 's#chat_interface.launch()#sys.stdout = sys.stderr; chat_interface.launch(server_name="0.0.0.0", server_port=80)#' app.py

RUN pip install -U pip
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 80

RUN curl -L https://huggingface.co/datasets/mickey45/americanmotocrossresults/resolve/main/vector-dbs.tar.xz | tar -xvJ
RUN curl -LO https://huggingface.co/datasets/mickey45/americanmotocrossresults/resolve/main/race_results.csv && \
    mv -v race_results.csv americanmotocrossresults 

CMD ["python", "/app/app.py"]
