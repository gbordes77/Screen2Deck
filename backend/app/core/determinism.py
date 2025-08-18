"""
Determinism configuration for reproducible results.
Ensures consistent behavior across runs for benchmarking.
"""

import os
import random
import numpy as np
import logging

logger = logging.getLogger(__name__)

def init_determinism():
    """
    Initialize deterministic behavior for reproducible results.
    Sets seeds for all random number generators.
    Enforces project constraints.
    """
    # HARD CONSTRAINT: Tesseract must NOT be installed
    import shutil
    if shutil.which("tesseract"):
        raise RuntimeError("❌ Tesseract must NOT be installed (project hard constraint). Use EasyOCR only.")
    
    # Get seed from environment or use default
    SEED = int(os.getenv("S2D_SEED", "42"))
    
    # Python random
    random.seed(SEED)
    
    # NumPy random
    np.random.seed(SEED)
    
    # Hash seed for deterministic dict ordering
    os.environ["PYTHONHASHSEED"] = str(SEED)
    
    # Limit threading for deterministic performance
    thread_count = os.getenv("S2D_THREADS", "1")
    os.environ["OMP_NUM_THREADS"] = thread_count
    os.environ["MKL_NUM_THREADS"] = thread_count
    os.environ["OPENBLAS_NUM_THREADS"] = thread_count
    os.environ["NUMEXPR_NUM_THREADS"] = thread_count
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
    # PyTorch determinism (if available)
    try:
        import torch
        torch.manual_seed(SEED)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(SEED)
            torch.cuda.manual_seed_all(SEED)
        # Enable deterministic algorithms
        torch.use_deterministic_algorithms(True, warn_only=True)
        # CUBLAS determinism
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        logger.info(f"PyTorch determinism enabled with seed {SEED}")
    except ImportError:
        pass  # PyTorch not installed
    except Exception as e:
        logger.warning(f"Could not enable PyTorch determinism: {e}")
    
    # TensorFlow determinism (if available)
    try:
        import tensorflow as tf
        tf.random.set_seed(SEED)
        logger.info(f"TensorFlow determinism enabled with seed {SEED}")
    except ImportError:
        pass  # TensorFlow not installed
    except Exception as e:
        logger.warning(f"Could not enable TensorFlow determinism: {e}")
    
    logger.info(f"Determinism initialized: SEED={SEED}, THREADS={thread_count}")
    
    return SEED

def get_deterministic_hash(data: bytes, context: dict = None) -> str:
    """
    Generate deterministic hash including version and configuration.
    
    Args:
        data: Raw data to hash
        context: Additional context to include in hash
    
    Returns:
        Deterministic hash string
    """
    import hashlib
    import json
    
    # Default context
    default_context = {
        "s2d_ver": os.getenv("S2D_VERSION", "unknown"),
        "easyocr_ver": "1.7.1",
        "seed": os.getenv("S2D_SEED", "42"),
    }
    
    # Merge with provided context
    if context:
        default_context.update(context)
    
    # Create hash
    h = hashlib.sha256()
    h.update(data)
    h.update(json.dumps(default_context, sort_keys=True).encode("utf-8"))
    
    return h.hexdigest()