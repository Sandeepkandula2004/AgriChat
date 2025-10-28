import numpy as np
import joblib
from sentence_transformers import SentenceTransformer
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from src.utils import reduced_to_angles

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Initialize quantum simulator
backend = AerSimulator(method="statevector")

def build_circuit(angles):
    """Build a 6-qubit circuit with RY rotations and chained CNOT entanglement."""
    qc = QuantumCircuit(6)
    for i, a in enumerate(angles):
        qc.ry(float(a), i)
    for i in range(5):  # 0->1, 1->2, ... 4->5
        qc.cx(i, i + 1)
    qc.save_statevector()
    return qc

def get_statevector(angles):
    """Simulate and return the 6-qubit statevector."""
    qc = build_circuit(angles)
    job = backend.run(qc)
    result = job.result()
    return result.get_statevector(qc)

def fidelity(vec1, vec2):
    """Quantum state fidelity (similarity between two statevectors)."""
    return np.abs(np.vdot(vec1, vec2)) ** 2

def quantum_similarity(query_embedding, pca_model, mins_val, maxs_val, doc_svs):
    """Compute quantum similarity scores for a query embedding."""
    reduced = pca_model.transform(query_embedding)
    angles = reduced_to_angles(reduced[0], mins_val, maxs_val)
    query_sv = get_statevector(angles)
    scores = [fidelity(query_sv, doc_sv) for doc_sv in doc_svs]
    return np.array(scores)

def quantum_rerank(query, texts, candidate_doc_statevectors, top_k=5, pca_model=None, mins_val=None, maxs_val=None):
    """Rerank candidate texts using quantum fidelity similarity."""
    emb = model.encode([query])
    scores = quantum_similarity(emb, pca_model, mins_val, maxs_val, candidate_doc_statevectors)
    top_idx = np.argsort(scores)[::-1][:top_k]
    return [(texts[i], float(scores[i])) for i in top_idx]
