
from th2rag.rag.generation.base import BaseGenerator
from th2rag.rag.retrieval.base import BaseRetriever


class RAGService:
    """
    RAGService orchestrates the retrieval-augmented generation pipeline.
    It retrieves relevant context for a user question, builds a prompt, and generates an answer.
    """

    def __init__(self, retriever: BaseRetriever, generator: BaseGenerator):
        self.retriever = retriever
        self.generator = generator

    def generate_code_snippet(self, question: str, prompt: str, history=[]) -> str:
        return self.generator.generate(
            question=question, retrieved_context=None, prompt=prompt, history=history
        )

    def answer_question(
        self,
        question: str,
        doc_id: int | None = None,
        limit: int = 3,
        prompt: str = None,
        history=[],
    ) -> str:
        """
        Given a user question and an optional document ID (doc_id), this method:
        1. Retrieves relevant chunks using the retriever.
        2. Builds a prompt combining the retrieved context and the question.
        3. Calls the generator to produce a final answer.

        Args:
            question (str): The user's question.
            doc_id (Optional[int]): The document identifier to restrict the retrieval.
            limit (int): The maximum number of chunks to retrieve.

        Returns:
            str: The generated answer.
        """
        try:
            if doc_id != None:
                chunks: list[dict] = self.retriever.retrieve(
                    query=question, doc_id=doc_id, limit=limit
                )
                knowledge_text = "\n\n".join(chunk.get("text", "") for chunk in chunks)
                return self.generator.generate(
                    question, retrieved_context=knowledge_text, prompt=prompt, history=history
                )
            else:
                return self.generator.generate(
                    question, retrieved_context=None, prompt=prompt, history=history
                )
        except Exception:
            raise

    def build_prompt(self, chunks: list[dict], user_question: str) -> str:
        """
        Construct a prompt for the generator by combining the retrieved chunks with the user's question.

        Args:
            chunks (List[Dict]): List of retrieved chunks, each expected to have a 'text' key.
            user_question (str): The user's input question.

        Returns:
            str: The complete prompt.
        """
        # Combine all chunk texts with separation.
        knowledge_text = "\n\n".join(chunk.get("text", "") for chunk in chunks)

        # prompt = (
        #     "You are an AI assistant with access to a dynamic knowledge base. Users have uploaded various documents "
        #     "to create a personalized repository. Your task is to answer the user's question based solely on the provided context.\n\n"
        #     "Relevant Context:\n"
        #     f"{knowledge_text}\n\n"
        #     "User Question:\n"
        #     f"{user_question}\n\n"
        #     "Please provide a comprehensive answer.\n\n"
        #     "And please respond in french."
        # )

        prompt = """
            # Role and Purpose
            You are an AI assistant with access to a dynamic knowledge base. Users have uploaded various documents
            to create a personalized repository. Your task is to answer the user's question based solely on the provided context.

            # Guidelines:
            1. Provide a clear and concise answer to the question.
            2. Use only the information from the relevant context to support your answer.
            3. The context is retrieved based on similarity search, so some information might be missing or irrelevant.
            4. Be transparent when there is insufficient information to fully answer the question.
            5. Do not make up or infer information not present in the provided context.
            6. If you cannot answer the question based on the given context, clearly state that.
            7. Maintain a helpful and professional tone.
            8. Respond in the same language of the question.
        """
        return prompt
