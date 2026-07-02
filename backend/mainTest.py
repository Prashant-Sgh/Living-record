import asyncio
import os
from dotenv import load_dotenv
import cognee

# 1. Force load the environment variables from your .env file
load_dotenv()

async def init_cognee():
    # Double-check that python actually sees your environment variables
    service_url = os.getenv("COGNEE_SERVICE_URL")
    api_key = os.getenv("COGNEE_API_KEY")
    
    if not service_url or not api_key:
        print("❌ Error: COGNEE_SERVICE_URL or COGNEE_API_KEY is missing from your environment!")
        return

    try:
        print("Connecting to Cognee Cloud...")
        # Pass them explicitly to bypass any internal fallback logic
        await cognee.serve(url=service_url, api_key=api_key)
        print("✅ Success: Successfully connected to Cognee Cloud!")
        # Remember something
        await cognee.remember("This project is called Living Record, and it is a hackathon project.")
        # Recall something
        recall_result = await cognee.recall("Tell me about this project.")
        for item in recall_result:
            print(f"✅ Cognee Recall: {item}")

    except Exception as e:
        print(f"❌ Error: Failed to connect to Cognee Cloud.")
        print(f"Details: {e}")

async def main():
    print("Application started.")
    await init_cognee()
    print("Application is running.")

if __name__ == "__main__":
    asyncio.run(main())