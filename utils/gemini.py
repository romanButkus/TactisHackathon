import os

from dotenv import load_dotenv
from google import genai
from google.genai.types import HttpOptions

# Automatically load environment variables when this module is imported somewhere
load_dotenv()


def get_gemini_client() -> genai.Client:
    """
    Initializes and returns a configured GenAI Client using the shared API key.
    Export this function to reuse the authenticated client across your project.
    """
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "Error: GEMINI_API_KEY is missing from your environment setup / .env file!"
        )

    # Standard website initialization using the shared developer/express key
    client = genai.Client(api_key=api_key, http_options=HttpOptions(api_version="v1"))
    return client


def ask_gemini(prompt: str, model: str = "gemini-2.5-flash") -> str:
    """
    A quick helper function to send a text prompt to Gemini and get a string response back.
    Useful for rapid tactical analysis or debugging telemetry data.
    """
    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"💥 Connection failed inside ask_gemini. Details: {str(e)}"


# This local testing block will ONLY run if you execute this file directly.
# It will be completely ignored when you import these functions into other files!
if __name__ == "__main__":
    test_prompt = "Test, what is a tes"
    result = ask_gemini(test_prompt)
    print(result)
