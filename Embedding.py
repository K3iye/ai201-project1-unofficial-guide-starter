"""Embedding.py — Stage 3 (Embedding + Vector Store) + Stage 4 (Retrieval).

Continues the pipeline from planning.md (lines 117-124):

    [Ingestion -> Chunking] -> Embedding + Vector Store -> Retrieval -> [Generation]
                               all-MiniLM-L6-v2,            query ChromaDB
                               stored in ChromaDB           for top-k=5

What this file does:
  1. loads the chunks produced by Ingestion.py,
  2. turns each chunk's text into a 384-dim vector with all-MiniLM-L6-v2,
  3. stores those vectors + text + source metadata in a persistent ChromaDB
     collection,
  4. exposes retrieve() — embed a question the same way and ask ChromaDB for the
     most similar chunks (optionally filtered to one professor).

Typical use:
    python Embedding.py --rebuild                      # build the index once
    python Embedding.py --query "Is David a tough grader?"
    python Embedding.py --query "lots of homework?" --professor "Olga Glebova"
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import chromadb

from Ingestion import EMBEDDING_MODEL, ingest

# --- Configuration -------------------------------------------------------------
CHROMA_DIR = str(Path(__file__).parent / "chroma_db")  # on-disk store (gitignored)
COLLECTION_NAME = "professor_reviews"
DEFAULT_TOP_K = 5  # planning.md retrieval approach


# --- The embedding model -------------------------------------------------------
# all-MiniLM-L6-v2 maps a piece of text to a 384-dimensional vector. Texts that
# mean similar things land close together in that 384-d space; that closeness is
# what retrieval measures. The model is loaded once and cached.
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """Encode a list of strings into a list of 384-dim vectors.

    normalize_embeddings=True scales every vector to length 1, which makes
    cosine similarity (the metric we configure on the collection) behave well.
    """
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


# --- Stage 3: Embedding + Vector Store -----------------------------------------
def _client() -> chromadb.ClientAPI:
    """A ChromaDB client that persists to disk, so the index survives restarts."""
    return chromadb.PersistentClient(path=CHROMA_DIR)


def build_index(rebuild: bool = False) -> chromadb.Collection:
    """Load chunks, embed them, and store everything in ChromaDB.

    rebuild=True wipes any existing collection first (use it whenever the
    documents or chunking settings change). Returns the populated collection.
    """
    client = _client()

    if rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass  # nothing to delete on the first run

    # "hnsw:space": "cosine" tells Chroma to rank by cosine similarity, the right
    # metric for normalized sentence-transformer vectors.
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Stage 1+2: get the cleaned, recursively-chunked reviews from Ingestion.py.
    chunks = ingest()

    # Chroma stores four parallel lists, indexed by a shared id:
    #   ids        — unique key per chunk (e.g. "2872422-3")
    #   embeddings — the vector we search over
    #   documents  — the raw chunk text (returned at query time for the LLM)
    #   metadatas  — source info used for citation and filtering
    ids = [c.id for c in chunks]
    documents = [c.text for c in chunks]
    metadatas = [c.metadata for c in chunks]
    embeddings = embed(documents)

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    print(f"Indexed {collection.count()} chunks into '{COLLECTION_NAME}' at {CHROMA_DIR}")
    return collection


def get_collection() -> chromadb.Collection:
    """Open the existing collection (does not rebuild). Errors if it's empty."""
    collection = _client().get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    if collection.count() == 0:
        raise RuntimeError(
            "The vector store is empty. Build it first with: python Embedding.py --rebuild"
        )
    return collection


# --- Stage 4: Retrieval --------------------------------------------------------
def _known_professors(collection: chromadb.Collection) -> list[str]:
    """Distinct professor names currently stored in the collection."""
    metadatas = collection.get(include=["metadatas"])["metadatas"]
    return sorted({m["professor"] for m in metadatas})


def list_professors() -> list[str]:
    """Public helper: all professor names in the store (for UI dropdowns)."""
    return _known_professors(get_collection())


def detect_professor(query: str, known: list[str]) -> str | None:
    """Guess which professor a question is about from its text.

    Matches if any significant part of a professor's name (first OR last name,
    length > 2) appears as a whole word in the query — so "Is David a tough
    grader?" maps to "David Strimple". Returns None if zero or more than one
    professor matches, so an ambiguous question falls back to a global search.
    """
    q = query.lower()
    matched = []
    for name in known:
        name_tokens = [t for t in re.findall(r"[a-z]+", name.lower()) if len(t) > 2]
        if any(re.search(rf"\b{re.escape(t)}\b", q) for t in name_tokens):
            matched.append(name)
    return matched[0] if len(matched) == 1 else None


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    professor: str | None = None,
    auto_detect: bool = True,
) -> list[dict]:
    """Return the top_k chunks most relevant to `query`.

    Steps: embed the query with the SAME model used for the chunks, then ask
    ChromaDB for the nearest vectors. Chroma filters to one professor's chunks
    *before* ranking (metadata filtering), which keeps results on-topic since
    every question targets a specific professor.

    Professor scope is resolved in this order:
      1. an explicit `professor=` argument, else
      2. auto-detected from the query text (when auto_detect=True), else
      3. no filter — a global search across all professors.

    Each result is a dict with the chunk text, its metadata (professor, url,
    source...), and a similarity score in [0, 1] where higher = more relevant.
    """
    collection = get_collection()

    if professor is None and auto_detect:
        professor = detect_professor(query, _known_professors(collection))

    query_embedding = embed([query])
    where = {"professor": professor} if professor else None

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        where=where,
    )

    # Chroma returns parallel lists wrapped in an outer list (one per query).
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    hits = []
    for text, meta, distance in zip(documents, metadatas, distances):
        hits.append(
            {
                "text": text,
                "metadata": meta,
                # cosine distance -> similarity: 0 distance == identical == score 1.
                "score": round(1 - distance, 4),
            }
        )
    return hits


# --- CLI -----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Embed chunks into ChromaDB and run retrieval.")
    parser.add_argument("--rebuild", action="store_true", help="(Re)build the vector store from documents.")
    parser.add_argument("--query", type=str, help="A question to retrieve chunks for.")
    parser.add_argument("--professor", type=str, help="Restrict retrieval to one professor (exact name).")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="How many chunks to return.")
    parser.add_argument("--no-auto", action="store_true", help="Disable auto-detecting the professor from the query.")
    args = parser.parse_args()

    if args.rebuild:
        build_index(rebuild=True)

    if args.query:
        auto_detect = not args.no_auto
        # Resolve scope up front so we can report it to the user.
        professor = args.professor
        if professor is None and auto_detect:
            professor = detect_professor(args.query, _known_professors(get_collection()))

        hits = retrieve(args.query, top_k=args.top_k, professor=professor, auto_detect=False)
        scope = f" (professor={professor})" if professor else " (all professors)"
        print(f"\nTop {len(hits)} results for: {args.query!r}{scope}\n")
        for rank, hit in enumerate(hits, start=1):
            m = hit["metadata"]
            print(f"[{rank}] score={hit['score']}  {m['professor']}  ({m['source']})")
            print(f"    {hit['text'][:200].strip()}...\n")

    if not args.rebuild and not args.query:
        parser.print_help()


if __name__ == "__main__":
    main()
