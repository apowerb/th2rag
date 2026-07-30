from docling.chunking import HybridChunker


class HybridTextChunker:
    """
    Wraps the HybridChunker from docling to split documents into chunks.
    """

    def __init__(self, tokenizer: str = "bert-base-uncased", merge_peers: bool = True):
        self.chunker = HybridChunker(tokenizer=tokenizer, merge_peers=merge_peers, max_tokens=512)

    def chunk_document(self, dl_doc) -> list:
        """
        Chunks the given document into smaller pieces.

        Args:
            dl_doc: Document object from DocumentConverter.

        Returns:
            list: A list of chunk objects.
        """
        chunk_iter = self.chunker.chunk(dl_doc=dl_doc)
        return list(chunk_iter)
