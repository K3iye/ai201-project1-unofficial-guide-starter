"""Ingestion.py — Stage 1 (Document Ingestion) + Stage 2 (Chunking).

Implements the first two boxes of the pipeline in planning.md (lines 117-124):

    Document Ingestion ->  Chunking  -> [ Embedding + Vector Store -> ... ]
    one professor =          recursive,
    one document          128 tokens, 20 overlap (~one review per chunk)

For each professor file in documents/ this script:
  1. loads the raw text and parses the header (name, RMP id, url) into metadata,
  2. cleans the body (drops section markers, un-wraps mid-sentence line breaks),
  3. splits the cleaned text into overlapping chunks with a recursive chunker
     whose chunk size is measured in *real* tokens using the same tokenizer as
     the embedding model (all-MiniLM-L6-v2).

Run it directly to see a per-professor summary, or with --out to write the
chunks to JSON for the embedding stage:

    python Ingestion.py
    python Ingestion.py --out chunks.json --preview
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

# --- Configuration (mirrors the Chunking Strategy section of planning.md) ------
DOCUMENTS_DIR = Path(__file__).parent / "documents"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# Reviews average ~60-80 tokens, so 128 keeps roughly one review per chunk:
# sharp, single-topic embeddings instead of 250-token blobs that mix 3 reviews.
CHUNK_SIZE_TOKENS = 128
CHUNK_OVERLAP_TOKENS = 20
# Recursive separators, tried coarsest -> finest. After cleaning, reviews are
# separated by blank lines, sentences by ". ", then words, then characters.
SEPARATORS = ["\n\n", ". ", "\n", " ", ""]


# --- Token counting ------------------------------------------------------------
# We count length in tokens (not characters) so "250 tokens" matches what the
# embedding model actually sees. The tokenizer is loaded lazily and cached.
_tokenizer = None


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        from transformers import AutoTokenizer

        _tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)
    return _tokenizer


def count_tokens(text: str) -> int:
    """Number of model tokens in `text` (excluding [CLS]/[SEP] special tokens)."""
    if not text:
        return 0
    return len(_get_tokenizer().encode(text, add_special_tokens=False))


# --- Data structures -----------------------------------------------------------
@dataclass
class Document:
    professor: str
    rmp_id: str
    url: str
    source: str  # original filename
    text: str    # cleaned body (overall stats + reviews)


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict = field(default_factory=dict)


# --- Stage 1: Document Ingestion -----------------------------------------------
def _extract(pattern: str, text: str, default: str = "") -> str:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else default


def clean_text(text: str) -> str:
    """Normalize raw review text.

    - removes `=== SECTION ===` markers,
    - collapses the hard line-wrapping inside a review into single spaces,
    - keeps blank lines between reviews so the recursive chunker can split on
      review boundaries first.
    """
    # Drop section header lines like "=== OVERALL ===".
    text = re.sub(r"^\s*===.*===\s*$", "", text, flags=re.MULTILINE)

    # Split into paragraphs on blank lines, then squeeze whitespace within each.
    paragraphs = re.split(r"\n\s*\n", text)
    cleaned = []
    for para in paragraphs:
        para = re.sub(r"\s+", " ", para).strip()
        if para:
            cleaned.append(para)
    return "\n\n".join(cleaned)


def parse_document(path: Path) -> Document:
    """Read one professor file and return a cleaned Document with metadata."""
    raw = path.read_text(encoding="utf-8")

    professor = _extract(r"PROFESSOR:\s*(.+)", raw, default=path.stem)
    rmp_id = _extract(r"RMP_ID:\s*(\S+)", raw)
    url = _extract(r"URL:\s*(\S+)", raw)

    # Body = everything from the first "===" section onward (overall + reviews);
    # this drops the PROFESSOR/RMP_ID/URL header, which we keep in metadata.
    marker = raw.find("===")
    body = raw[marker:] if marker != -1 else raw

    return Document(
        professor=professor,
        rmp_id=rmp_id,
        url=url,
        source=path.name,
        text=clean_text(body),
    )


def load_documents(documents_dir: Path = DOCUMENTS_DIR) -> list[Document]:
    """Load every *.txt professor file in the documents folder."""
    files = sorted(documents_dir.glob("*.txt"))
    if not files:
        raise FileNotFoundError(f"No .txt documents found in {documents_dir}")
    return [parse_document(path) for path in files]


# --- Stage 2: Recursive Chunking -----------------------------------------------
class RecursiveTokenChunker:
    """Recursive character chunker that measures size in tokens.

    Same idea as LangChain's RecursiveCharacterTextSplitter: try to split on the
    coarsest separator that exists in the text; any piece still over the size
    limit is split again with the next-finer separator. Pieces are then merged
    back together up to `chunk_size`, carrying `chunk_overlap` tokens between
    consecutive chunks.
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE_TOKENS,
        chunk_overlap: int = CHUNK_OVERLAP_TOKENS,
        separators: list[str] = SEPARATORS,
        length_function=count_tokens,
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators
        self.length = length_function

    def split(self, text: str) -> list[str]:
        return self._split(text, self.separators)

    def _split(self, text: str, separators: list[str]) -> list[str]:
        final: list[str] = []

        # Pick the first separator that occurs in the text (last one, "", is the
        # character-level fallback that always "matches").
        separator = separators[-1]
        remaining: list[str] = []
        for i, sep in enumerate(separators):
            if sep == "":
                separator = sep
                break
            if sep in text:
                separator = sep
                remaining = separators[i + 1:]
                break

        splits = list(text) if separator == "" else text.split(separator)

        good_splits: list[str] = []
        for piece in splits:
            if piece == "":
                continue
            if self.length(piece) <= self.chunk_size:
                good_splits.append(piece)
            else:
                # Flush what we have, then recurse into the oversized piece.
                if good_splits:
                    final.extend(self._merge(good_splits, separator))
                    good_splits = []
                if not remaining:
                    final.append(piece)  # cannot split any further
                else:
                    final.extend(self._split(piece, remaining))

        if good_splits:
            final.extend(self._merge(good_splits, separator))
        return final

    def _merge(self, splits: list[str], separator: str) -> list[str]:
        """Pack small splits into chunks <= chunk_size with token overlap."""
        sep_len = self.length(separator)
        chunks: list[str] = []
        current: list[str] = []
        total = 0

        for piece in splits:
            piece_len = self.length(piece)
            extra = sep_len if current else 0
            if total + piece_len + extra > self.chunk_size and current:
                chunk = separator.join(current).strip()
                if chunk:
                    chunks.append(chunk)
                # Drop from the front until the carried-over overlap fits.
                while total > self.chunk_overlap or (
                    total + piece_len + (sep_len if current else 0) > self.chunk_size
                    and total > 0
                ):
                    total -= self.length(current[0]) + (sep_len if len(current) > 1 else 0)
                    current = current[1:]
            current.append(piece)
            total += piece_len + (sep_len if len(current) > 1 else 0)

        if current:
            chunk = separator.join(current).strip()
            if chunk:
                chunks.append(chunk)
        return chunks


def chunk_document(doc: Document, chunker: RecursiveTokenChunker) -> list[Chunk]:
    """Turn one professor Document into a list of metadata-tagged Chunks."""
    pieces = chunker.split(doc.text)
    chunks = []
    for i, piece in enumerate(pieces):
        chunks.append(
            Chunk(
                id=f"{doc.rmp_id or doc.source}-{i}",
                text=piece,
                metadata={
                    "professor": doc.professor,
                    "rmp_id": doc.rmp_id,
                    "url": doc.url,
                    "source": doc.source,
                    "chunk_index": i,
                    "tokens": count_tokens(piece),
                },
            )
        )
    return chunks


def ingest(
    documents_dir: Path = DOCUMENTS_DIR,
    chunk_size: int = CHUNK_SIZE_TOKENS,
    chunk_overlap: int = CHUNK_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Full Stage 1 + Stage 2: load -> clean -> recursive chunk."""
    chunker = RecursiveTokenChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    all_chunks: list[Chunk] = []
    for doc in load_documents(documents_dir):
        all_chunks.extend(chunk_document(doc, chunker))
    return all_chunks


# --- CLI -----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Load and recursively chunk professor reviews.")
    parser.add_argument("--documents", type=Path, default=DOCUMENTS_DIR, help="Folder of .txt files.")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE_TOKENS, help="Chunk size in tokens.")
    parser.add_argument("--overlap", type=int, default=CHUNK_OVERLAP_TOKENS, help="Overlap in tokens.")
    parser.add_argument("--out", type=Path, help="Optional path to write chunks as JSON.")
    parser.add_argument("--preview", action="store_true", help="Print the first chunk of each professor.")
    args = parser.parse_args()

    chunker = RecursiveTokenChunker(chunk_size=args.chunk_size, chunk_overlap=args.overlap)

    total = 0
    sources = set()
    out_records = []
    print(f"Chunking with size={args.chunk_size} tokens, overlap={args.overlap} tokens\n")
    for doc in load_documents(args.documents):
        chunks = chunk_document(doc, chunker)
        total += len(chunks)
        sources.add(doc.source)
        token_counts = [c.metadata["tokens"] for c in chunks]
        span = f"{min(token_counts)}-{max(token_counts)}" if token_counts else "0"
        print(f"  {doc.professor:<32} {len(chunks):>2} chunks  ({span} tokens each)")
        if args.preview and chunks:
            preview = chunks[0].text[:160].replace("\n", " ")
            print(f"      first chunk: {preview}...")
        out_records.extend(asdict(c) for c in chunks)

    print(f"\nTotal: {total} chunks across {len(sources)} documents")

    if args.out:
        args.out.write_text(json.dumps(out_records, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {len(out_records)} chunks to {args.out}")


if __name__ == "__main__":
    main()
