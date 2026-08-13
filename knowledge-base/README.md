# Knowledge-base source area

This directory contains reviewed, fictional source documents for local RAG
development. They are not customer exports, generated embeddings, Qdrant
storage, or production policy.

`noavia/` is a realistic but fictional support KB for the first consumer. The
offline path in `services/classification/app/local_rag.py` reads only Markdown
and text from this directory, attaches source/title/chunk metadata, and keeps
all vectors in process. It is safe to run without credentials or services.
