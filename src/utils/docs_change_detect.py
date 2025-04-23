import hashlib
from pathlib import Path
from typing import List
from langchain_core.documents import Document


def get_docs_fingerprint(docs: List[Document]) -> str:
    sorted_content = sorted(doc.page_content for doc in docs)
    combined = "\n".join(sorted_content)
    return hashlib.md5(combined.encode("utf-8")).hexdigest()


def has_docs_changed(docs: List[Document], cache_path: str = "src/runtime/storage/.docs_fingerprint") -> bool:
    cache_file = Path(cache_path)
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    current_fingerprint = get_docs_fingerprint(docs)

    if not cache_file.exists():
        cache_file.write_text(current_fingerprint)
        return True

    previous_fingerprint = cache_file.read_text().strip()

    if current_fingerprint != previous_fingerprint:
        cache_file.write_text(current_fingerprint)
        return True

    return False
