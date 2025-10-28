from src.query_pipeline import full_pipeline

query = "How can farmers save water in paddy fields?"
results = full_pipeline(query, top_k=5)

print("\n🔍 Query:", query)
print("\nTop Results (Quantum Reranked):\n")
for i, (text, score) in enumerate(results, 1):
    print(f"{i}. ({score:.4f}) {text}")