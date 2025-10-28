import numpy as np

def reduced_to_angles(z, mins, maxs):
    """Convert reduced PCA features into rotation angles in [0, π]."""
    z = np.asarray(z)
    denom = (maxs - mins)
    denom[denom == 0] = 1e-12
    scaled = (z - mins) / denom
    return scaled * np.pi

def l2_normalize_matrix(X):
    """Normalize a matrix row-wise to unit length (L2 norm)."""
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1e-12
    return X / norms