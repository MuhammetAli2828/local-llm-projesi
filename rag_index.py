"""
rag_index.py
============
TF-IDF tabanlı basit RAG indeksi. Yönerge PDF'ini indeksler ve arama yapar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class SearchHit:
    score: float
    chunk_text: str


class TfidfRagIndex:
    def __init__(self, chunk_size: int = 600, overlap: int = 100):
        self.chunk_size  = chunk_size
        self.overlap     = overlap
        self.vectorizer  = TfidfVectorizer(stop_words=None, ngram_range=(1, 2))
        self.chunks: List[str] = []
        self.matrix      = None
        self.source_name: str | None = None
        self.is_ready    = False

    def build_from_text(self, source_name: str, text: str) -> None:
        clean = " ".join((text or "").split())
        self.chunks = []
        start = 0
        while start < len(clean):
            end = min(len(clean), start + self.chunk_size)
            self.chunks.append(clean[start:end])
            if end == len(clean):
                break
            start = max(end - self.overlap, start + 1)
        if not self.chunks:
            self.chunks = ["Boş içerik"]
        self.matrix      = self.vectorizer.fit_transform(self.chunks)
        self.source_name = source_name
        self.is_ready    = True
        print(f"[RAG] {source_name} indekslendi — {len(self.chunks)} chunk.")

    def search(self, query: str, top_k: int = 3) -> List[SearchHit]:
        if not self.is_ready or not query.strip():
            return []
        qv   = self.vectorizer.transform([query])
        sims = cosine_similarity(qv, self.matrix)[0]
        ranked = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            SearchHit(score=float(s), chunk_text=self.chunks[i])
            for i, s in ranked if s > 0.01
        ]
