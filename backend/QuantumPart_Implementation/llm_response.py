# llm_response.py
import os
from openai import OpenAI
from src.query_pipeline import full_pipeline
from dotenv import load_dotenv

load_dotenv()
# -----------------------
# Initialize the OpenAI client
# -----------------------
# Make sure to set your API key as an environment variable:
# For example: setx OPENAI_API_KEY "your_api_key_here"  (on Windows)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_advisory(query, top_k=5):
    """
    Generates a farmer-friendly advisory using quantum-enhanced retrieval + GPT-4.
    """
    # Step 1: Run the full quantum pipeline
    results = full_pipeline(query, top_k=top_k)

    # Step 2: Format the reranked results as context
    context = "\n".join([f"- {r[0]}" for r in results])

    # Step 3: Construct a domain-specific prompt for GPT-4
    prompt = f"""
You are an agricultural advisory assistant helping farmers.
Use only the information in the context below to answer the question.
If the answer is not clearly available, say you don't have enough data.

Context:
{context}

Question:
{query}

Provide a clear, concise, and practical advisory useful for farmers.
Avoid technical jargon.
    """

    # Step 4: Call GPT-4 model
    completion = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.3
    )

    answer = completion.choices[0].message.content.strip()
    return answer


# -----------------------
# Test the pipeline
# -----------------------
if __name__ == "__main__":
    user_query = "How can farmers save water in paddy fields?"
    response = generate_advisory(user_query)
    print("\n🔹 Final Advisory:\n", response)
