import math
import re

def preprocess_text(text: str) -> list[str]:
    """Tokenize and clean text by converting to lowercase and removing punctuation."""
    # Convert to lowercase and find all words
    words = re.findall(r'\b\w+\b', text.lower())
    return words

def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """Calculates the Jaccard similarity between two texts based on word sets.
    
    Jaccard Similarity = |A ∩ B| / |A ∪ B|
    Returns a float between 0.0 and 1.0.
    """
    words1 = set(preprocess_text(text1))
    words2 = set(preprocess_text(text2))
    
    if not words1 and not words2:
        return 1.0
        
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union)

def calculate_cosine_similarity(text1: str, text2: str) -> float:
    """Calculates the Cosine similarity between two texts based on term frequencies.
    
    Cosine Similarity = (A · B) / (||A|| * ||B||)
    Returns a float between 0.0 and 1.0.
    """
    words1 = preprocess_text(text1)
    words2 = preprocess_text(text2)
    
    if not words1 and not words2:
        return 1.0
        
    # Count term frequencies
    tf1 = {}
    for word in words1:
        tf1[word] = tf1.get(word, 0) + 1
        
    tf2 = {}
    for word in words2:
        tf2[word] = tf2.get(word, 0) + 1
        
    # Get all unique words
    all_words = set(tf1.keys()).union(set(tf2.keys()))
    
    # Compute dot product and magnitudes
    dot_product = 0.0
    magnitude1 = 0.0
    magnitude2 = 0.0
    
    for word in all_words:
        val1 = tf1.get(word, 0)
        val2 = tf2.get(word, 0)
        
        dot_product += val1 * val2
        magnitude1 += val1 ** 2
        magnitude2 += val2 ** 2
        
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
        
    return dot_product / (math.sqrt(magnitude1) * math.sqrt(magnitude2))
