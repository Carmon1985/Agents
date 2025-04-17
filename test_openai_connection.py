import os
import openai
from dotenv import load_dotenv

print("--- Loading .env file ---")
load_dotenv()

print("--- Checking loaded API Key and Azure Endpoint ---")
api_key = os.environ.get("OPENAI_API_KEY")
# Get Azure endpoint from env, provide a default if not set in .env
azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://aihub3803534642.openai.azure.com/") 

if not api_key:
    print("ERROR: OPENAI_API_KEY not found in environment variables.")
    exit()
if not azure_endpoint:
    print("ERROR: AZURE_OPENAI_ENDPOINT not found in environment variables and no default provided.")
    exit() # Exit if endpoint is missing
else:
    print(f"Loaded Key (masked): {api_key[:5]}...{api_key[-4:]}")
    print(f"Using Azure endpoint: {azure_endpoint}")

print("--- Initializing Azure OpenAI Client ---")
try:
    client = openai.AzureOpenAI(
        api_key=api_key,
        api_version="2023-05-15",  # Use an appropriate API version for your Azure setup
        azure_endpoint=azure_endpoint
    )
    print("Azure OpenAI client initialized successfully.")

    print("--- Attempting API call (list models/deployments) ---")
    # For Azure OpenAI with openai>=1.0, use client.models.list()
    # The listed models correspond to your available deployments.
    models = client.models.list()
    
    # Check if we got models/deployments
    model_list = list(models)
    if model_list:
        print(f"SUCCESS: Successfully retrieved {len(model_list)} models/deployments from Azure OpenAI API.")
        # Print model IDs (which correspond to your deployment names)
        print("Available model/deployment IDs:", [m.id for m in model_list])
    else:
        print("WARNING: API call succeeded but returned no models/deployments. Check your Azure OpenAI resource and deployments.")

except openai.AuthenticationError as e:
    print(f"ERROR: Authentication failed. Incorrect API key for the specified Azure endpoint or invalid setup.")
    print(f"Details: {e}")
except openai.PermissionDeniedError as e:
    print(f"ERROR: Permission denied. Check Azure RBAC roles for your API key.")
    print(f"Details: {e}")
except openai.APIConnectionError as e:
    print(f"ERROR: Connection error. Could not connect to the Azure endpoint: {azure_endpoint}")
    print(f"Details: {e}")
except openai.RateLimitError as e:
    print(f"ERROR: Rate limit exceeded.")
    print(f"Details: {e}")
except openai.OpenAIError as e:
    print(f"ERROR: An Azure OpenAI API error occurred.")
    print(f"Details: {e}")
except Exception as e:
    print(f"ERROR: An unexpected error occurred.")
    print(f"Details: {e}") 