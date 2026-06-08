"""app.py — the interface / web app for The Unofficial Guide.

This is the front end for the pipeline. It wraps the generator in generation.py
(Stage 5) in a simple Gradio UI:

    pick a professor  ->  type a question  ->  press Generate  ->  cited answer

All the RAG work (retrieval + grounded generation) happens in generation.py;
this file only handles the widgets and wiring.

Run it:
    python app.py
"""

from __future__ import annotations

import gradio as gr

from Embedding import list_professors
from generation import format_sources_md, generate

ALL_PROFESSORS = "All professors"  # dropdown option for an unscoped search

# The 5 evaluation questions from planning.md, paired with their professor so
# each example sets the dropdown too. Handy for testing while writing the report.
EXAMPLE_QUESTIONS = [
    ["Swamy Narayan Jignaas Pattipati", "Is Swamy a good lecturer and does he make class engaging?"],
    ["Lina Kloub", "Does Lina Kloub prepare students for exams and are they difficult?"],
    ["Olga Glebova", "Does Olga Glbova give a lot of homework throughout the week?"],
    ["Justin Furuness", "Does Justin Furuness have lots of office hours for help when needed?"],
    ["David Strimple", "Is David Strimple a tough grader?"],
]


def answer_question(professor_choice: str, question: str):
    """Bridge the Gradio widgets to generate(); returns (answer_md, sources_md)."""
    question = (question or "").strip()
    if not question:
        return "_Please type a question first._", ""

    professor = None if professor_choice == ALL_PROFESSORS else professor_choice
    result = generate(question, professor=professor)
    return result["answer"], format_sources_md(result["sources"])


def build_ui():
    professors = [ALL_PROFESSORS] + list_professors()

    with gr.Blocks(theme=gr.themes.Soft(), title="The Unofficial Guide") as demo:
        gr.Markdown(
            "# 🎓 The Unofficial Guide\n"
            "Ask about a UConn CS professor and get an answer grounded **only** in real "
            "student reviews. Every claim is cited `[n]`, and each source below shows the "
            "exact review it came from."
        )

        with gr.Row():
            professor = gr.Dropdown(
                choices=professors,
                value=ALL_PROFESSORS,
                label="Professor",
                scale=1,
            )
            question = gr.Textbox(
                label="Your question",
                placeholder="e.g. Is David Strimple a tough grader?",
                scale=3,
            )

        generate_btn = gr.Button("Generate", variant="primary")

        answer = gr.Markdown(label="Answer")
        sources = gr.Markdown(label="Sources")

        gr.Examples(
            examples=EXAMPLE_QUESTIONS,
            inputs=[professor, question],
            label="Evaluation questions (from planning.md)",
        )

        generate_btn.click(answer_question, inputs=[professor, question], outputs=[answer, sources])
        question.submit(answer_question, inputs=[professor, question], outputs=[answer, sources])

    return demo


if __name__ == "__main__":
    build_ui().launch()
