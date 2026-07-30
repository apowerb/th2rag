from th2rag.rag.generation.litellm_generator import LiteLLMGenerator
from th2rag.utils.logger import setup_logger

logger = setup_logger(__name__)

def run_test():
    # 1. Initialize with your new config defaults (Mistral)
    print("--- Testing Mistral ---")
    gen = LiteLLMGenerator()
    
    try:
        # 2. Run a simple generation
        answer = gen.generate(question="What is the capital of France? and who is its president?")
        print(f"Response: {answer}\n")
        
        # 3. Test the "Switch" to Anthropic
        # Ensure you have ANTHROPIC_API_KEY in your .env for this to work!
        print("--- Testing Anthropic ---")
        anthropic_gen = LiteLLMGenerator(
            provider="anthropic", 
            model='claude-3-haiku-20240307'
        )
        answer_anthropic = anthropic_gen.generate(question="What is the capital of US? and who is its president??")
        print(f"Response: {answer_anthropic}")
        

    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    run_test()


