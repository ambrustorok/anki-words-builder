# app/gradio/interface.py
import gradio as gr
from fastapi import Request


async def gradio_ui(request: gr.Request):
    #  Hello, <coroutine object get_current_user at 0x7fc8beffee30>! Welcome to the Gradio interface.
    return f"Hello, {request.username}! Welcome to the Gradio interface."


with gr.Blocks() as demo:
    gr.Markdown("## Welcome to the Gradio Interface")
    output = gr.Markdown()
    demo.load(fn=gradio_ui, inputs=[], outputs=output)
