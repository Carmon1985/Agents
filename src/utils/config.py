import autogen
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def load_llm_config():
    """Loads LLM configuration, prioritizing OAI_CONFIG_LIST file,
    then environment variables.
    Returns a dictionary suitable for AutoGen agents or None if config fails.
    """
    load_dotenv() # Load .env file if present
    
    # Try loading from environment variables first
    try:
        # Load Azure OpenAI config from environment variables
        azure_api_key = os.getenv("OPENAI_API_KEY")
        azure_endpoint = os.getenv("OPENAI_API_BASE")
        azure_deployment = os.getenv("OPENAI_DEPLOYMENT_NAME")
        azure_api_version = os.getenv("OPENAI_API_VERSION")
        azure_api_type = os.getenv("OPENAI_API_TYPE", "azure")  # Ensure api_type is set to azure
        
        if all([azure_api_key, azure_endpoint, azure_deployment, azure_api_version]):
            config_list = [
                {
                    "model": azure_deployment,
                    "api_key": azure_api_key,
                    "base_url": azure_endpoint,
                    "api_type": "azure",  # Explicitly set to azure
                    "api_version": azure_api_version,
                }
            ]
            logger.info("LLM config loaded from Azure OpenAI environment variables.")
            return {
                "config_list": config_list,
                "temperature": 0.7,
                "timeout": 600,
                "cache_seed": None
            }
        else:
            missing = []
            if not azure_api_key: missing.append("OPENAI_API_KEY")
            if not azure_endpoint: missing.append("OPENAI_API_BASE")
            if not azure_deployment: missing.append("OPENAI_DEPLOYMENT_NAME")
            if not azure_api_version: missing.append("OPENAI_API_VERSION")
            logger.error(f"Missing required Azure OpenAI environment variables: {', '.join(missing)}")
            return None

    except Exception as e:
        logger.error(f"Error loading LLM config from environment variables: {e}", exc_info=True)
        return None

    config_list = None
    config_file_path = "OAI_CONFIG_LIST" # Default name

    # Try loading from the specified file
    try:
        if os.path.exists(config_file_path):
            config_list = autogen.config_list_from_json(config_file_path)
            logger.info(f"LLM config loaded from {config_file_path}")
        else:
            logger.info(f"{config_file_path} not found, checking environment variables.")
    except Exception as e:
        logger.warning(f"Could not load config from {config_file_path}: {e}. Checking environment variables.")

    # If file loading failed or file doesn't exist, try environment variables
    if not config_list:
        try:
            # Example: Load Azure OpenAI config from environment variables
            # Adjust variable names based on your actual setup
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o") # Default deployment
            azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01") # Example version
            
            if all([azure_api_key, azure_endpoint]):
                config_list = [
                    {
                        "model": azure_deployment,
                        "api_key": azure_api_key,
                        "base_url": azure_endpoint,
                        "api_type": "azure",
                        "api_version": azure_api_version,
                    }
                ]
                logger.info("LLM config loaded from Azure environment variables.")
            else:
                logger.warning("Azure OpenAI environment variables (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT) not fully set. Trying standard OpenAI.")
                # Try standard OpenAI key
                openai_api_key = os.getenv("OPENAI_API_KEY")
                if openai_api_key:
                    config_list = [
                        {
                            "model": "gpt-4o", # Or another model like gpt-3.5-turbo
                            "api_key": openai_api_key,
                        }
                    ]
                    logger.info("LLM config loaded from OPENAI_API_KEY environment variable.")
                else:
                    logger.error("No suitable LLM configuration found in file or environment variables.")
                    return None
        except Exception as e:
            logger.error(f"Error loading LLM config from environment variables: {e}", exc_info=True)
            return None

    if not config_list:
        logger.error("Failed to load any LLM configuration.")
        return None

    # Return dict format expected by AutoGen agents
    return {"config_list": config_list, "timeout": 120, "cache_seed": 42} # Add timeout and caching seed 