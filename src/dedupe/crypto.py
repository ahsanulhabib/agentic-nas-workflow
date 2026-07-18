import blake3

def calculate_blake3(file_path: str) -> str:
    """Generates a BLAKE3 hash for exact duplicate detection."""
    hasher = blake3.blake3()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()