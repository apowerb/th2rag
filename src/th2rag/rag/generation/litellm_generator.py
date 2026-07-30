from litellm import completion 
from th2rag.rag.generation.base import BaseGenerator 
from th2rag.config import settings 
from th2rag.utils.logger import setup_logger
from th2rag.models import UserLLMConfig  # <--- NEW IMPORT
from th2rag.utils.security import decrypt_key # <--- NEW IMPORT

logger = setup_logger(__name__)

class LiteLLMGenerator(BaseGenerator):
    """
    A smart wrapper that switches between User Config and System Default.
    """
    
    DEFAULT_SYSTEM_PROMPT = """
            # Role and Purpose
            You are an AI assistant with access to a dynamic knowledge base. Users have uploaded various documents
            to create a personalized repository. Your task is to answer the user's question based solely on the provided context, if not context is provided then answer based on your knowledge.

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
    
    # We added 'user_config' to the init arguments
    def __init__(self, user_config: UserLLMConfig = None, provider: str = None, model: str = None, max_tokens: int = None, temperature: float = None, top_p: float = None, stream: bool = None):     
        
        # THE HYBRID 
        # 1. Check if User provided a custom config
        if user_config and user_config.api_key:
            self.provider = user_config.provider
            self.model_name = user_config.model_name
            # Decrypt their key on the fly
            self.api_key = decrypt_key(user_config.api_key)
            logger.info(f"Using CUSTOM CONFIG for User {user_config.user_id}: {self.provider}/{self.model_name}")
        
        # 2. If direct provider/model passed 
        elif provider and model:
            self.provider = provider
            self.model_name = model
            
            if self.provider.lower() == "anthropic":
                self.api_key = settings.anthropic_api_key
            else:
                self.api_key = settings.litellm_api_key or settings.mistral_api_key
            
            logger.info(f"Using DIRECT PARAMS: {self.provider}/{self.model_name}")
        
        # 3. If not, use System Default (.env)
        else:
            self.provider = settings.litellm_provider
            self.model_name = settings.litellm_model
            
            if self.provider.lower() == "anthropic":
                self.api_key = settings.anthropic_api_key
            else:
                self.api_key = settings.litellm_api_key or settings.mistral_api_key
            
            logger.info(f"Using SYSTEM DEFAULT: {self.provider}/{self.model_name}")

        # Safety Check
        if not self.api_key:
            logger.error(f"No API key found! Provider: {self.provider}")
            raise ValueError(f"API key missing for provider {self.provider}")

        # Build Model ID
        if "/" in self.model_name:
            self.model = self.model_name
        else:
            self.model = f"{self.provider}/{self.model_name}"
        
        # Set Parameters
        self.max_tokens = max_tokens if max_tokens is not None else settings.mistral_max_tokens
        self.temperature = temperature if temperature is not None else settings.mistral_temperature
        self.top_p = top_p if top_p is not None else settings.mistral_top_p
        self.stream = stream if stream is not None else settings.mistral_stream
        

    def generate(self, question: str, retrieved_context: str = None, prompt: str = None, history: list = None) -> str:
        # Standard generation logic...
        if history is None:
            history = []
        
        system_prompt = prompt if prompt is not None else self.DEFAULT_SYSTEM_PROMPT

        messages = [{"role": "system", "content": system_prompt}]
        
        if retrieved_context:
            messages.append({"role": "system", "content": f"Context:\n{retrieved_context}"})
        
        if history:
            messages.extend(history)
        
        messages.append({"role": "user", "content": question})
        
        try:
            logger.info(f"Calling LiteLLM with model: {self.model}")
            logger.info(f"Prompt: {prompt}")  
            logger.info(f"Messages: {messages}")  
            
            completion_kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "stream": self.stream,
                "api_key": self.api_key,
                "drop_params": True 
            }
            
            # Mistral/OVH Hack (Only needed if using System Default Mistral)
            is_anthropic = (
                self.provider.lower() == "anthropic" or 
                self.model.startswith("anthropic/")
            )
            
            if not is_anthropic:#because here mistr accept top_p 
                completion_kwargs["top_p"] = self.top_p

            if self.provider == "mistral" or self.model.startswith("mistral/"):
                 if settings.mistral_api_url and "api.mistral.ai" not in settings.mistral_api_url:
                      completion_kwargs["api_base"] = settings.mistral_api_url

            response = completion(**completion_kwargs)
            
            generated_text = (
                "".join(chunk.choices[0].delta.content for chunk in response if chunk.choices[0].delta.content)
                if self.stream
                else response.choices[0].message.content
            )
            
            logger.info(f"Successfully generated response ({len(generated_text)} chars)")
            return generated_text
            
        except Exception as e:
            logger.error(f"LiteLLM generation failed: {str(e)}")
            raise RuntimeError(f"Failed to generate response: {str(e)}")