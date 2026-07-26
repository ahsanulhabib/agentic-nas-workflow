from unittest.mock import MagicMock, patch
from src.retrieval.hybrid_search import HybridRetriever

@patch("src.retrieval.hybrid_search.FusekiClient")
@patch("src.retrieval.hybrid_search.QdrantClient")
@patch("src.retrieval.hybrid_search.instructor.from_openai")
def test_hybrid_search_graph_first(mock_instructor, mock_qdrant, mock_fuseki):
    # Setup Mocks
    mock_llm = MagicMock()
    mock_instructor.return_value = mock_llm
    mock_llm.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(content="Graph Answer"))]
    
    retriever = HybridRetriever("http://fake", "http://fake", MagicMock(), "test-model")
    
    # Mock Graph returning evidence
    retriever._query_graph = MagicMock(return_value=["Graph Evidence 1"])
    retriever._query_vector = MagicMock() # Should not be called
    
    result = retriever.ask("Where are my taxes?")
    
    assert result["source"] == "Knowledge Graph (Deterministic)"
    assert result["answer"] == "Graph Answer"
    retriever._query_vector.assert_not_called()

@patch("src.retrieval.hybrid_search.FusekiClient")
@patch("src.retrieval.hybrid_search.QdrantClient")
@patch("src.retrieval.hybrid_search.instructor.from_openai")
def test_hybrid_search_vector_fallback(mock_instructor, mock_qdrant, mock_fuseki):
    mock_llm = MagicMock()
    mock_instructor.return_value = mock_llm
    mock_llm.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(content="Vector Answer"))]
    
    retriever = HybridRetriever("http://fake", "http://fake", MagicMock(), "test-model")
    
    # Mock Graph failing, causing fallback to Vector
    retriever._query_graph = MagicMock(return_value=[])
    retriever._query_vector = MagicMock(return_value=["Vector Evidence 1"])
    
    result = retriever.ask("Find a picture of a beach")
    
    assert result["source"] == "Qdrant Vector Space (Probabilistic)"
    retriever._query_vector.assert_called_once()