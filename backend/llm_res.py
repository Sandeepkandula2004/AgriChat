# llm_response.py
import os
from groq import Groq
from src.query_pipeline import full_pipeline
from dotenv import load_dotenv
load_dotenv()
# -----------------------
# Initialize Groq client
# -----------------------
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_advisory(query, top_k=5):
    """
    Generates a farmer-friendly advisory using quantum-enhanced retrieval + Groq reasoning model.
    """
    # Step 1: Run your quantum retrieval pipeline
    results = full_pipeline(query, top_k=top_k)
    
    # Step 2: Build context
    context = "\n".join([f"- {r[0]}" for r in results])
    # Step 3: Domain-specific prompt
    prompt = f"""
You are an agricultural advisory assistant helping farmers.
Use only the information in the context below to answer the question.
In the context i have given every possible solution to the given query so from that generate
a good response


Context:
{context}

Question:
{query}

Provide a clear, concise, and practical advisory useful for farmers.
Avoid technical jargon.
    """

    # Step 4: Use Groq's reasoning-capable model (gpt-oss-120b)
    stream = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_completion_tokens=800,
        top_p=1,
        reasoning_effort="medium",
        stream=True
    )

    # Step 5: Stream and assemble the response
    response_text = ""
    for chunk in stream:
        if chunk.choices[0].delta and chunk.choices[0].delta.content:
            piece = chunk.choices[0].delta.content
            response_text += piece
            print(piece, end="", flush=True)  # live output

    return response_text.strip()


# -----------------------
# Test the pipeline
# -----------------------
if __name__ == "__main__":
    # user_query = "How can farmers save water in paddy fields?"
    user_query = "Tell me about wheat problems?"
    print("\n🔹 Generating advisory...\n")
    response = generate_advisory(user_query)
    print("\n\n🔹 Final Advisory:\n", response)
