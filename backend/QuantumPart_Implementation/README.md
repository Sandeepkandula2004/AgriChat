Quantum-Enhanced AI Assistant for Agriculture
Abstract

This project presents a Quantum-Enhanced Retrieval-Augmented Generation (RAG) system for delivering intelligent and contextually relevant agricultural advisories.
It integrates quantum computing principles with classical AI-based retrieval to improve the semantic depth of query understanding.
Using a 6-qubit quantum encoding approach, the system captures high-order semantic correlations that classical cosine similarity often overlooks, providing a significant enhancement in information relevance and contextual fidelity.

Overview

The system aims to bridge the gap between modern AI-driven agriculture and emerging quantum technologies.
By leveraging sentence embeddings, Principal Component Analysis (PCA), and quantum feature mapping, it introduces a hybrid retrieval pipeline that can assist farmers with precise, data-driven recommendations.
This work forms part of a long-term vision to make intelligent agricultural knowledge systems more efficient, explainable, and future-ready.

System Architecture

User Query Input: The user enters a natural language question.

Text Embedding Generation: The query is embedded into a 384-dimensional vector using all-MiniLM-L6-v2.

Classical Retrieval (FAISS): FAISS retrieves the top candidate advisories based on cosine similarity.

Dimensionality Reduction: PCA reduces 384 features to 6 to align with a 6-qubit encoding scheme.

Quantum Encoding: Each reduced feature is encoded using RY rotations, followed by chained CNOT entanglement for correlation modeling.

Quantum Fidelity Evaluation: Fidelity between query and document statevectors determines semantic closeness.

Quantum Reranking: FAISS candidates are reranked based on quantum similarity scores.

Final Output: The top advisories are provided as context to an LLM for generating farmer-friendly responses.

Project Structure
Quantum_Agri_Assistant/
│
├── data/
│   ├── pca_6.pkl                # Trained PCA model (384 → 6)
│   ├── pca_mins.npy             # PCA feature minima
│   ├── pca_maxs.npy             # PCA feature maxima
│   ├── doc_statevectors.npy     # Precomputed document quantum statevectors
│   ├── faiss_index_384.index    # FAISS index for classical search
│   └── qa_texts.txt             # Agricultural advisory dataset
│
├── src/
│   ├── __init__.py              # Package initializer
│   ├── utils.py                 # Helper utilities
│   ├── quantum_rerank.py        # Quantum encoding and fidelity calculation
│   └── query_pipeline.py        # Complete FAISS + Quantum reranking pipeline
│
├── test_query.py                # Script for testing the end-to-end pipeline
├── requirements.txt             # Dependencies with exact versions
└── README.md                    # Project documentation

Key Components
Component	Description
Sentence Embedding	Converts input text into 384-D vectors using all-MiniLM-L6-v2.
PCA Reduction	Maps embeddings to 6D for quantum encoding.
Quantum Circuit	6 qubits, RY rotations, and CNOT entanglement for state preparation.
Fidelity Similarity	Quantum metric measuring closeness between query and document states.
Hybrid Retrieval	Combines FAISS (speed) with quantum reranking (semantic accuracy).
Installation

Ensure Python 3.9 or higher is installed.

Navigate to the project directory and install dependencies:

pip install -r requirements.txt


Confirm that all data files exist inside the data/ folder.

Execution

To run the full query pipeline:

python test_query.py


Expected Output:
Displays the query and top-5 most contextually relevant advisories based on quantum similarity.

For backend integration, use:

from src.query_pipeline import full_pipeline
results = full_pipeline("How can farmers save water in paddy fields?", top_k=5)

Design Rationale

6-Qubit Quantum Encoding: Balances computational feasibility and semantic richness on classical simulators.

RY Rotations + CNOT Entanglement: Captures inter-feature dependencies in reduced embeddings.

Quantum Fidelity Metric: Provides a nonlinear, geometry-aware similarity measure.

Hybrid Integration: Classical FAISS ensures scalability; quantum reranking enhances contextual accuracy.