"""
rag_index.py
============
TF-IDF tabanlı RAG indeksi. Birden fazla PDF'i indeksler ve arama yapar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class SearchHit:
    score: float
    chunk_text: str
    source: str = ""


class TfidfRagIndex:
    def __init__(self, chunk_size: int = 600, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap    = overlap
        self.vectorizer = TfidfVectorizer(stop_words=None, ngram_range=(1, 2))
        self.chunks:  List[str] = []
        self.sources: List[str] = []
        self.matrix   = None
        self.is_ready = False
        # source_name → chunk sayısı
        self._doc_registry: Dict[str, int] = {}

    def _text_to_chunks(self, text: str) -> List[str]:
        clean = " ".join((text or "").split())
        chunks, start = [], 0
        while start < len(clean):
            end = min(len(clean), start + self.chunk_size)
            chunks.append(clean[start:end])
            if end == len(clean):
                break
            start = max(end - self.overlap, start + 1)
        return chunks or ["Boş içerik"]

    def _rebuild_matrix(self) -> None:
        if self.chunks:
            self.matrix   = self.vectorizer.fit_transform(self.chunks)
            self.is_ready = True

    def build_from_text(self, source_name: str, text: str) -> None:
        """Geriye dönük uyumluluk için tek doküman index'i."""
        self.chunks.clear()
        self.sources.clear()
        self._doc_registry.clear()
        self.add_document(source_name, text)

    def add_document(self, source_name: str, text: str) -> None:
        """Yeni bir dokümanı mevcut index'e ekle."""
        new_chunks = self._text_to_chunks(text)
        self.chunks.extend(new_chunks)
        self.sources.extend([source_name] * len(new_chunks))
        self._doc_registry[source_name] = len(new_chunks)
        self._rebuild_matrix()
        print(f"[RAG] '{source_name}' eklendi — {len(new_chunks)} chunk "
              f"(toplam: {len(self.chunks)})")

    def remove_document(self, source_name: str) -> bool:
        """Bir dokümanı index'ten çıkar."""
        if source_name not in self._doc_registry:
            return False
        pairs = [(c, s) for c, s in zip(self.chunks, self.sources) if s != source_name]
        if pairs:
            self.chunks, self.sources = map(list, zip(*pairs))
        else:
            self.chunks, self.sources = [], []
        del self._doc_registry[source_name]
        if self.chunks:
            self._rebuild_matrix()
        else:
            self.matrix   = None
            self.is_ready = False
        print(f"[RAG] '{source_name}' kaldırıldı.")
        return True

    def list_documents(self) -> List[Tuple[str, int]]:
        """(dosya_adı, chunk_sayısı) listesi döner."""
        return list(self._doc_registry.items())

    def search(self, query: str, top_k: int = 3) -> List[SearchHit]:
        if not self.is_ready or not query.strip():
            return []
        qv   = self.vectorizer.transform([query])
        sims = cosine_similarity(qv, self.matrix)[0]
        ranked = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            SearchHit(score=float(s), chunk_text=self.chunks[i], source=self.sources[i])
            for i, s in ranked if s > 0.01
        ]
