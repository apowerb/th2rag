from abc import ABC, abstractmethod


class BaseGenerator(ABC):
    """
    Abstract base class for generation models.
    """

    @abstractmethod
    def generate(
        self, question: str, retrieved_context: str = None, prompt: str = None, history=[]
    ) -> str:
        """
        Generate a response based on the input prompt.

        Args:
            prompt (str): The input prompt.

        Returns:
            str: The generated text.
        """
        pass
