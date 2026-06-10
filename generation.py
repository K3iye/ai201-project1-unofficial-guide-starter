"""generation.py — Stage 5 (Generation) + interface.

Final stage of the pipeline in planning.md (lines 117-124):

    [Ingestion -> Chunking -> Embedding -> Retrieval] -> Generation
                                                         pass retrieved chunks
                                                         to an LLM (Groq)

How it works:
  1. retrieve() (from Embedding.py) returns the top-k review chunks for a
     question, optionally scoped to one professor,
  2. those chunks are formatted into a numbered CONTEXT block,
  3. a Groq LLM answers using ONLY that context, citing the chunk number(s)
     next to each claim, e.g. "He is a tough grader [2].",
  4. a Sources list maps each [n] back to its professor + source file.

The model is instructed never to use outside knowledge — if the reviews don't
cover the question, it says so instead of guessing.

This file is the *generator only* — the web interface lives in app.py and
imports generate() and format_sources_md() from here.

Run it:
    python generation.py --query "Is David a tough grader?"   # one-shot CLI
    python app.py                                             # web interface
"""

from __future__ import annotations

import argparse
import os
import re

from dotenv import load_dotenv

from Embedding import retrieve

# --- Configuration -------------------------------------------------------------
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
TEMPERATURE = 0.2  # low = stay close to the reviews, don't get creative
DEFAULT_TOP_K = 5

SYSTEM_PROMPT = """You are "The Unofficial Guide", a question-answering assistant \
that answers questions about university professors using ONLY the student reviews \
provided to you in the CONTEXT.

Follow these rules exactly:
1. Use ONLY information found in the numbered CONTEXT. Never use outside knowledge or assumptions.
2. After every claim, cite the chunk number(s) it came from in square brackets, e.g. "He is a tough grader [2]." If several chunks support a claim, cite them all: [1][3].
3. If the CONTEXT does not contain enough information to answer, reply exactly: "The reviews don't contain enough information to answer that." Do not guess.
4. When reviews disagree, present both sides instead of picking one.
5. Be concise and answer the question directly."""


# --- The Groq client -----------------------------------------------------------
_client = None


def _get_client():
    """Create the Groq client once, reading GROQ_API_KEY from the .env file."""
    global _client
    if _client is None:
        load_dotenv()
        api_key = (os.getenv("GROQ_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        from groq import Groq

        _client = Groq(api_key=api_key)
    return _client


# --- Building the prompt from retrieved chunks ---------------------------------
def format_context(hits: list[dict]) -> tuple[str, list[dict]]:
    """Turn retrieved chunks into a numbered CONTEXT block + a sources list.

    The number on each context entry ([1], [2], ...) is exactly what the model
    cites, so the Sources list can map every citation back to its origin.
    """
    lines = []
    sources = []
    for i, hit in enumerate(hits, start=1):
        m = hit["metadata"]
        lines.append(f"[{i}] ({m['professor']} — {m['source']})\n{hit['text']}")
        sources.append(
            {
                "n": i,
                "professor": m["professor"],
                "source": m["source"],
                "url": m.get("url", ""),
                "score": hit["score"],
                "text": hit["text"],
            }
        )
    return "\n\n".join(lines), sources


def build_messages(question: str, context: str) -> list[dict]:
    user_prompt = f"QUESTION: {question}\n\nCONTEXT:\n{context}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


# --- Stage 5: Generation -------------------------------------------------------
def generate(question: str, professor: str | None = None, top_k: int = DEFAULT_TOP_K) -> dict:
    """Answer `question` from the reviews. Returns {answer, sources, hits}.

    `professor` scopes retrieval to one professor (None = search everyone, with
    auto-detection from the question still active).
    """
    hits = retrieve(question, top_k=top_k, professor=professor)
    if not hits:
        return {"answer": "No reviews were found for that question.", "sources": [], "hits": []}

    context, sources = format_context(hits)
    messages = build_messages(question, context)

    response = _get_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=TEMPERATURE,
    )
    answer = response.choices[0].message.content.strip()

    # Only show sources the answer actually cited. If the model refused (no [n]
    # citations), this leaves the list empty so no chunks are shown.
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    used_sources = [s for s in sources if s["n"] in cited]
    return {"answer": answer, "sources": used_sources, "hits": hits}


def format_sources_md(sources: list[dict]) -> str:
    """Render the sources as markdown: each cited chunk plus what the review said.

    A reader can match an inline citation like [2] to its entry here and see the
    exact review text the answer drew on, not just a number.
    """
    if not sources:
        return ""
    lines = ["### Sources"]
    for s in sources:
        link = f"[{s['source']}]({s['url']})" if s["url"] else s["source"]
        quote = " ".join(s["text"].split())  # flatten newlines for a clean quote
        lines.append(f"**`[{s['n']}]` {s['professor']}** — {link}  _(relevance {s['score']})_")
        lines.append(f"> {quote}")
        lines.append("")  # blank line between sources
    return "\n".join(lines).strip()


# --- CLI -----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Generate grounded, cited answers from professor reviews.")
    parser.add_argument("--query", type=str, required=True, help="Ask one question from the terminal.")
    parser.add_argument("--professor", type=str, help="Scope the answer to one professor (exact name).")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Chunks to retrieve as context.")
    args = parser.parse_args()

    result = generate(args.query, professor=args.professor, top_k=args.top_k)
    print(f"\nQ: {args.query}\n")
    print(result["answer"])
    print()
    print(format_sources_md(result["sources"]))


if __name__ == "__main__":
    main()
