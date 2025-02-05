import os
from openai import OpenAI
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Create client with explicit API key
client = OpenAI(
    api_key=os.getenv("ALI_OPENAI_API_KEY"),
    organization=os.getenv("ALI_OPENAI_ORG_ID"),
    project=os.getenv("ALI_OPENAI_PROJECT_ID")
)

try:
    logger.info("Making API call to OpenAI...")
    logger.info(f"Using API key: {os.getenv('ALI_OPENAI_API_KEY')[:5]}...")
    logger.info(f"Using project ID: {os.getenv('ALI_OPENAI_PROJECT_ID')}")
    
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": "Write a haiku about recursion in programming."
            }
        ],
        timeout=10
    )

    print(completion.choices[0].message)
    
except Exception as e:
    logger.error(f"Error making OpenAI API call: {str(e)}", exc_info=True)