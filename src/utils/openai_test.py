import os
from openai import AzureOpenAI
from dotenv import load_dotenv

def test_azure_openai_connection():
    """Test connection to Azure OpenAI service."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Print configuration for debugging
        print("Testing Azure OpenAI connection with the following configuration:")
        print(f"API Base: {os.getenv('OPENAI_API_BASE')}")
        print(f"API Version: {os.getenv('OPENAI_API_VERSION')}")
        print(f"Deployment Name: {os.getenv('OPENAI_DEPLOYMENT_NAME')}")
        
        # Initialize the client
        client = AzureOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("OPENAI_API_BASE")
        )
        
        print("\nAttempting to create chat completion...")
        
        # Test completion with a simple prompt
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_DEPLOYMENT_NAME"),
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hello, connection successful!' if you can read this."}
            ],
            max_tokens=50,
            temperature=0.7,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            stop=None,
            stream=False
        )
        
        print("\nConnection test successful!")
        print("Response:", response.choices[0].message.content)
        return True
        
    except Exception as e:
        print("\nError connecting to Azure OpenAI:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        
        # Additional debugging information
        if "api_key" in str(e).lower():
            print("\nPossible API key issue. Please verify your OPENAI_API_KEY in .env")
        elif "endpoint" in str(e).lower():
            print("\nPossible endpoint issue. Please verify your OPENAI_API_BASE in .env")
        elif "deployment" in str(e).lower():
            print("\nPossible deployment name issue. Please verify your OPENAI_DEPLOYMENT_NAME in .env")
        
        return False

if __name__ == "__main__":
    test_azure_openai_connection() 