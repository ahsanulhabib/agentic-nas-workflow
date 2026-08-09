from __future__ import annotations

import re


def recursive_text_chunker(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """
    SRE Chunker: Sentence-aware recursive text splitter with overlap.
    Prevents slicing sentences in half.
    """
    if not text or not text.strip():
        return []

    # Split by paragraphs or sentences first
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)
        if current_len + sentence_len > chunk_size and current_chunk:
            chunk_str = " ".join(current_chunk)
            chunks.append(chunk_str)
            
            # Keep overlap sentences
            overlap_chunk = []
            overlap_len = 0
            for s in reversed(current_chunk):
                if overlap_len + len(s) <= overlap:
                    overlap_chunk.insert(0, s)
                    overlap_len += len(s)
                else:
                    break
            current_chunk = overlap_chunk
            current_len = overlap_len

        current_chunk.append(sentence)
        current_len += sentence_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks