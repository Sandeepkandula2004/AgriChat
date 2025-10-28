import numpy as np
import faiss
import json
from sentence_transformers import SentenceTransformer
from src.quantum_rerank import quantum_rerank
import joblib

# Load FAISS index and dataset texts
index = faiss.read_index("data/faiss_index_384.index")
model = SentenceTransformer("all-MiniLM-L6-v2")
# Load PCA + metadata + doc statevectors
pca = joblib.load("data/pca_6.pkl")
mins = np.load("data/pca_mins.npy")
maxs = np.load("data/pca_maxs.npy")
doc_statevectors = np.load("data/doc_statevectors.npy", mmap_mode='r')

# Load your advisory texts (each line = one record)
texts = []
with open("data/qa_dataset_final.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        texts.append(data["text"])

def get_faiss_top(query, top_n=20):
    """Retrieve top_n most similar embeddings from FAISS."""
    emb = model.encode([query])
    emb = emb / np.linalg.norm(emb)
    emb = np.array(emb, dtype=np.float32)
    scores, idx = index.search(emb, top_n)
    candidate_doc_statevectors = doc_statevectors[idx[0]]
    return idx[0], scores[0], candidate_doc_statevectors

def full_pipeline(query, top_k=5):
    """Complete pipeline: FAISS retrieval + Quantum rerank."""
    idx, _, candidate_doc_statevectors = get_faiss_top(query)
    candidate_texts = [texts[i] for i in idx]
    final_results = quantum_rerank(query, candidate_texts, candidate_doc_statevectors, top_k=top_k, pca_model=pca, mins_val=mins, maxs_val=maxs)
    return final_results