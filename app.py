import os
import sys
import gradio as gr

from americanmotocrossresults.chat import chat


def chatbot_handler(message, history):
    yield from chat(message, history)


def show_ui():
    chatbot = gr.Chatbot(type="messages")
    chat_interface = gr.ChatInterface(
        fn=chatbot_handler, chatbot=chatbot, type="messages", multimodal=False
    )

    print("Start MX chatbot now ...", file=sys.stderr)
    chat_interface.launch()


def _requirements():
    if not os.getenv("OPENAI_API_KEY"):
        print("error: OPENAI_API_KEY is not set or is empty.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists("americanmotocrossresults/race_results.csv"):
        print("error: CSV file race_results.csv is not present.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _requirements()

    show_ui()
