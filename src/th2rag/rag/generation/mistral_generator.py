import json

import requests

from th2rag.config import settings
from th2rag.rag.generation.base import BaseGenerator
from th2rag.utils.logger import setup_logger

logger = setup_logger(__name__)


class MistralGenerator(BaseGenerator):

    DEFAULT_SYSTEM_PROMPT = """
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

    """
    A wrapper class for interacting with the Mistral AI API for text generation.
    """
    #old:
    # def __init__(self, api_key: str = None, endpoint: str = None, model: str = "mistral-nemo-instruct-2407", max_tokens: int = 512):
    #     """
    #     Initialize the MistralGenerator.

    #     Args:
    #         api_key (str): Your Mistral API key. If not provided, will be read from the MISTRAL_API_KEY environment variable.
    #         endpoint (str): The Mistral API endpoint. Defaults to the value from MISTRAL_API_ENDPOINT environment variable or a default value.
    #         model (str): The model name to use (default "mistral-7b").
    #         max_tokens (int): Maximum length for generated text.
    #     """
    #     self.api_key = api_key or settings.mistral_api_key
    #     self.endpoint = endpoint or settings.mistral_api_url
    #     self.model = model
    #     self.max_tokens = max_tokens

    #     if not self.api_key:
    #         raise ValueError(
    #             "Mistral API key must be provided either as an argument or via the MISTRAL_API_KEY environment variable."
    #         )

    def __init__(self, api_key: str = None, endpoint: str = None, model: str = None, max_tokens: int = None, temperature: float = None, top_p: float = None, presence_penalty: float = None, stream: bool = None):
        """
        Initialize the MistralGenerator.

        All parameters are optional and will default to environment variable values.

        Args:
            api_key: Mistral API key (defaults to MISTRAL_API_KEY)
            endpoint: API endpoint URL (defaults to MISTRAL_API_URL)
            model: Model name to use (defaults to MISTRAL_MODEL_NAME)
            max_tokens: Maximum tokens to generate (defaults to MISTRAL_MAX_TOKENS)
            temperature: Temperature for generation (defaults to MISTRAL_TEMPERATURE)
            top_p: Top-p sampling parameter (defaults to MISTRAL_TOP_P)
            presence_penalty: Presence penalty (defaults to MISTRAL_PRESENCE_PENALTY)
            stream: Whether to stream responses (defaults to MISTRAL_STREAM)
        """
        # Load from environment variables with fallback to provided arguments
        self.api_key = api_key or settings.mistral_api_key
        self.endpoint = endpoint or settings.mistral_api_url
        self.model = model or settings.mistral_model_name
        self.max_tokens = max_tokens if max_tokens is not None else settings.mistral_max_tokens
        self.temperature = temperature if temperature is not None else settings.mistral_temperature
        self.top_p = top_p if top_p is not None else settings.mistral_top_p
        self.presence_penalty = presence_penalty if presence_penalty is not None else settings.mistral_presence_penalty
        self.stream = stream if stream is not None else settings.mistral_stream

        if not self.api_key:
            raise ValueError(
                "Mistral API key must be provided either as an argument or via the MISTRAL_API_KEY environment variable."
            )

        logger.info(f"Initialized MistralGenerator with model: {self.model}")
        logger.info(f"Configuration: max_tokens={self.max_tokens}, temperature={self.temperature}, "
                   f"top_p={self.top_p}, presence_penalty={self.presence_penalty}, stream={self.stream}")

    #old:
    # def generate(self, question: str, retrieved_context: str = None, prompt: str = None, history=[] ) -> str:
    #     """
    #     Generate a response from the Mistral AI API based on the provided prompt.

    #     Args:
    #         prompt (str): The input prompt for text generation.

    #     Returns:
    #         str: The generated text response.
    #     """

    #     if prompt != None:
    #         self.SYSTEM_PROMPT = prompt

    #     messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
    #     messages.extend(history)

    #     if retrieved_context != None:
    #         messages.append(
    #             {
    #                 "role": "user",
    #                 "content": f"# Retrieved information:\n{retrieved_context}\n\n# User Query:\n{question}",
    #             }
    #         )
    #     else:
    #         messages.append({"role": "user", "content": question})

    #     print("the retrieved messages are :", messages)
    #     headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
    #     payload = {
    #         "model": self.model,
    #         "messages": messages,
    #         "max_tokens": self.max_tokens,
    #         "top_p": 1,
    #         "temperature": 0,
    #         "presence_penalty": 0,
    #         "stream": True,
    #     }

    #     response = requests.post(
    #         self.endpoint, headers=headers, data=json.dumps(payload), stream=True
    #     )
    #     if response.status_code != 200:
    #         raise Exception(f"Mistral API error {response.status_code}: {response.text}")

    #     output = ""

    #     for line in response.iter_lines():
    #         if line:
    #             decoded_line = line.decode("utf-8").strip()
    #             if decoded_line == "data: [DONE]":
    #                 break
    #             if decoded_line.startswith("data: "):
    #                 try:
    #                     data = json.loads(decoded_line[len("data: ") :])
    #                     if data.get("choices") and data["choices"][0]["delta"].get("content"):
    #                         output += data["choices"][0]["delta"]["content"]
    #                 except json.JSONDecodeError:
    #                     continue
    #     return output

    def generate(self, question: str, retrieved_context: str = None, prompt: str = None, history: list = None ) -> str:
        """
        Generate a response from the Mistral AI API based on the provided inputs.

        Args:
            question: The user's question
            retrieved_context: Retrieved context from RAG (optional)
            prompt: Custom system prompt (optional, defaults to DEFAULT_SYSTEM_PROMPT)
            history: Conversation history (optional)

        Returns:
            str: The generated text response

        Raises:
            Exception: If the API request fails
        """
        if history is None:
            history = []

        # Use custom prompt or default
        system_prompt = prompt if prompt is not None else self.DEFAULT_SYSTEM_PROMPT

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)

        # Add context and question
        if retrieved_context is not None:
            user_message = f"# Retrieved information:\n{retrieved_context}\n\n# User Query:\n{question}"
        else:
            user_message = question

        messages.append({"role": "user", "content": user_message})

        logger.debug(f"Sending {len(messages)} messages to Mistral API")

        # Prepare request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "presence_penalty": self.presence_penalty,
            "stream": self.stream,
        }

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                data=json.dumps(payload),
                stream=self.stream,
                timeout=60
            )

            if response.status_code != 200:
                error_msg = f"Mistral API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

            # Handle streaming response
            if self.stream:
                return self._handle_stream_response(response)
            else:
                # Handle non-streaming response
                data = response.json()
                output = data["choices"][0]["message"]["content"]
                logger.info(f"Generated response of length {len(output)}")
                return output

        except requests.exceptions.RequestException as e:
            logger.error(f"Request to Mistral API failed: {e}")
            raise Exception(f"Failed to connect to Mistral API: {str(e)}")



    def _handle_stream_response(self, response) -> str:
        """
        Handle streaming response from Mistral API.

        Args:
            response: The streaming response object

        Returns:
            str: The complete generated text
        """
        output = ""

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode("utf-8").strip()

                if decoded_line == "data: [DONE]":
                    break

                if decoded_line.startswith("data: "):
                    try:
                        data = json.loads(decoded_line[len("data: "):])
                        if data.get("choices") and data["choices"][0]["delta"].get("content"):
                            output += data["choices"][0]["delta"]["content"]
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode JSON: {decoded_line}")
                        continue

        logger.info(f"Completed streaming response of length {len(output)}")
        return output


    def get_embedding_dimension(self) -> int:
        """
        Not applicable for a generation model.
        """
        raise NotImplementedError("MistralGenerator does not support embeddings.")
