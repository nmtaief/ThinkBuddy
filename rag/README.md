# ThinkBuddy – RAG Module

The RAG module implements:
- Hybrid vector + trigram/BM25 retrieval over NCTB textbook chunks.
- Multilingual embeddings (`bge-m3` / `multilingual-e5`).
- Cross-encoder reranking.
- Citation tracking (book, chapter, printed page number, chunk id).
- Threshold-based fallback ("not found in textbook") to prevent hallucinations.
