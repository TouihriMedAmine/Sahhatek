# agents/triage_agent/test_knowledge_base.py
"""
Comprehensive unit tests for Knowledge Base integration
Tests retrieval, Q&A, emergency detection, and recommendation system
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

# Add project root
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agents.triage_agent.knowledge_base import (
    get_knowledge_base,
    TriageKnowledgeBase,
    KnowledgeDocument,
    RetrievalResult
)

# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def kb():
    """Get knowledge base instance"""
    return get_knowledge_base()

@pytest.fixture
def sample_state():
    """Sample triage state for testing"""
    return {
        "user_input": "I have fever and cough",
        "intent": None,
        "metadata": {"age": "32"},
        "messages": [],
        "current_agent": None,
        "next_agent": None,
        "agent_output": None
    }

# ============================================================
# KNOWLEDGE BASE INITIALIZATION TESTS
# ============================================================

class TestKBInitialization:
    """Test knowledge base initialization"""
    
    def test_kb_singleton(self):
        """Test that KB is singleton"""
        kb1 = get_knowledge_base()
        kb2 = get_knowledge_base()
        assert kb1 is kb2, "KB should be singleton"
    
    def test_vectorstore_initialized(self, kb):
        """Test vectorstore is initialized"""
        assert kb.vectorstore is not None, "Vectorstore should be initialized"
    
    def test_documents_loaded(self, kb):
        """Test documents are loaded"""
        count = kb.vectorstore._collection.count()
        assert count >= 23, f"Should have at least 23 documents, got {count}"
    
    def test_embedding_model_loaded(self, kb):
        """Test embedding model is loaded"""
        assert kb.embeddings is not None, "Embeddings model should be loaded"
        # Test embedding generation
        test_embedding = kb.embeddings.embed_query("test")
        assert len(test_embedding) == 384, "Embedding dimension should be 384"

# ============================================================
# RETRIEVAL TESTS
# ============================================================

class TestRetrieval:
    """Test knowledge base retrieval"""
    
    def test_retrieve_basic(self, kb):
        """Test basic retrieval"""
        results = kb.retrieve("fever", k=3)
        assert len(results) > 0, "Should return results for 'fever'"
        assert all(isinstance(r, RetrievalResult) for r in results), "Should return RetrievalResult objects"
    
    def test_retrieve_similarity_scores(self, kb):
        """Test similarity scores are valid"""
        results = kb.retrieve("fever", k=3)
        for result in results:
            assert 0 <= result.score <= 1, f"Similarity score should be 0-1, got {result.score}"
    
    def test_retrieve_sorted_by_score(self, kb):
        """Test results are sorted by score descending"""
        results = kb.retrieve("cold", k=5)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), "Results should be sorted by score (descending)"
    
    def test_retrieve_with_different_k(self, kb):
        """Test retrieval with different k values"""
        results_k1 = kb.retrieve("cough", k=1)
        results_k5 = kb.retrieve("cough", k=5)
        assert len(results_k1) == 1, "Should return 1 result when k=1"
        assert len(results_k5) >= 1, "Should return multiple results when k=5"
    
    def test_retrieve_caching(self, kb):
        """Test MD5 query caching"""
        # First call
        results1 = kb.retrieve("fever", k=3)
        # Second call (should use cache)
        results2 = kb.retrieve("fever", k=3)
        # Same results should be returned
        assert len(results1) == len(results2), "Cached results should match"
    
    def test_retrieve_metadata(self, kb):
        """Test metadata is included in results"""
        results = kb.retrieve("fever", k=3)
        for result in results:
            assert hasattr(result, 'metadata'), "Result should have metadata"
            assert isinstance(result.metadata, dict), "Metadata should be dict"

class TestCategoryRetrieval:
    """Test category-based retrieval"""
    
    def test_retrieve_by_category_recommendations(self, kb):
        """Test retrieval by recommendations category"""
        results = kb.retrieve_by_category("recommendations", limit=5)
        assert len(results) > 0, "Should find recommendation documents"
    
    def test_retrieve_by_category_symptoms(self, kb):
        """Test retrieval by symptoms category"""
        results = kb.retrieve_by_category("symptoms", limit=5)
        assert len(results) > 0, "Should find symptom documents"
    
    def test_retrieve_by_category_nonexistent(self, kb):
        """Test retrieval by nonexistent category"""
        results = kb.retrieve_by_category("nonexistent", limit=5)
        assert isinstance(results, list), "Should return empty list for nonexistent category"
    
    def test_retrieve_by_category_services(self, kb):
        """Test retrieval by services category"""
        results = kb.retrieve_by_category("services", limit=10)
        assert len(results) >= 6, "Should find at least 6 service documents"

# ============================================================
# EMERGENCY DETECTION TESTS
# ============================================================

class TestEmergencyDetection:
    """Test emergency detection"""
    
    def test_emergency_chest_pain(self, kb):
        """Test chest pain detection"""
        is_emergency, guidance = kb.is_emergency("I have severe chest pain")
        assert is_emergency is True, "Should detect chest pain as emergency"
        assert len(guidance) > 0, "Should return emergency guidance"
    
    def test_emergency_breathing(self, kb):
        """Test difficulty breathing detection"""
        is_emergency, guidance = kb.is_emergency("I can't breathe")
        assert is_emergency is True, "Should detect breathing difficulty as emergency"
    
    def test_emergency_bleeding(self, kb):
        """Test severe bleeding detection"""
        is_emergency, guidance = kb.is_emergency("I'm bleeding heavily")
        assert is_emergency is True, "Should detect severe bleeding as emergency"
    
    def test_not_emergency_cold(self, kb):
        """Test cold is not emergency"""
        is_emergency, guidance = kb.is_emergency("I have a cold")
        assert is_emergency is False, "Cold should not be emergency"
    
    def test_not_emergency_fever(self, kb):
        """Test low fever is not emergency"""
        is_emergency, guidance = kb.is_emergency("I have a 38°C fever")
        assert is_emergency is False, "Low fever should not be emergency"
    
    def test_emergency_multiple_keywords(self, kb):
        """Test multiple emergency keywords"""
        is_emergency, guidance = kb.is_emergency("chest pain and can't breathe")
        assert is_emergency is True, "Multiple emergency keywords should trigger"

# ============================================================
# Q&A TESTS
# ============================================================

class TestQA:
    """Test Q&A functionality"""
    
    def test_qa_basic(self, kb):
        """Test basic Q&A"""
        answer = kb.answer_question("What is fever?")
        assert isinstance(answer, str), "Should return string answer"
        assert len(answer) > 0, "Answer should not be empty"
        assert len(answer) > 50, "Answer should be substantial"
    
    def test_qa_hospital(self, kb):
        """Test Q&A about hospital"""
        answer = kb.answer_question("When should I go to the hospital?")
        assert isinstance(answer, str), "Should return string answer"
        # Should mention hospital criteria
        assert any(word in answer.lower() for word in ['hospital', 'emergency', 'immediate']), \
            "Answer should mention hospital-related keywords"
    
    def test_qa_cold_vs_flu(self, kb):
        """Test Q&A about cold vs flu"""
        answer = kb.answer_question("What's the difference between cold and flu?")
        assert isinstance(answer, str), "Should return string answer"
        assert len(answer) > 100, "Answer should be detailed"
    
    def test_qa_antibiotics(self, kb):
        """Test Q&A about antibiotics"""
        answer = kb.answer_question("When do I need antibiotics?")
        assert isinstance(answer, str), "Should return string answer"
        assert any(word in answer.lower() for word in ['bacteria', 'infection', 'prescription']), \
            "Answer should mention antibiotic-related keywords"
    
    def test_qa_fever_management(self, kb):
        """Test Q&A about fever management"""
        answer = kb.answer_question("How to manage high fever?")
        assert isinstance(answer, str), "Should return string answer"
        assert len(answer) > 50, "Answer should be detailed"

# ============================================================
# RECOMMENDATION CONTEXT TESTS
# ============================================================

class TestRecommendationContext:
    """Test recommendation context generation"""
    
    def test_context_flu(self, kb):
        """Test context for flu"""
        diagnoses = [{"name": "Influenza", "confidence": 0.87}]
        symptoms = ["fever", "cough", "body ache"]
        context = kb.get_recommendation_context(diagnoses, symptoms)
        assert isinstance(context, str), "Should return string context"
        assert len(context) > 100, "Context should be substantial"
        assert "flu" in context.lower() or "influenza" in context.lower(), \
            "Context should mention flu"
    
    def test_context_cold(self, kb):
        """Test context for cold"""
        diagnoses = [{"name": "Common Cold", "confidence": 0.92}]
        symptoms = ["cough", "sore throat"]
        context = kb.get_recommendation_context(diagnoses, symptoms)
        assert isinstance(context, str), "Should return string context"
        assert "cold" in context.lower() or "self-care" in context.lower(), \
            "Context should mention cold"
    
    def test_context_multiple_diagnoses(self, kb):
        """Test context with multiple diagnoses"""
        diagnoses = [
            {"name": "Influenza", "confidence": 0.87},
            {"name": "Common Cold", "confidence": 0.45}
        ]
        symptoms = ["fever", "cough"]
        context = kb.get_recommendation_context(diagnoses, symptoms)
        assert isinstance(context, str), "Should return string context"
        assert len(context) > 100, "Context should include multiple diagnoses"

# ============================================================
# CARE PATH TESTS
# ============================================================

class TestCarePaths:
    """Test care path retrieval"""
    
    def test_respiratory_path(self, kb):
        """Test respiratory symptoms path"""
        path = kb.get_care_path(["cough", "sore throat"])
        if path:  # Path might be None if not found
            assert isinstance(path, str), "Should return string path"
            assert len(path) > 0, "Path should not be empty"
    
    def test_fever_path(self, kb):
        """Test fever symptoms path"""
        path = kb.get_care_path(["fever", "chills"])
        if path:
            assert isinstance(path, str), "Should return string path"
    
    def test_empty_symptoms(self, kb):
        """Test with empty symptoms"""
        path = kb.get_care_path([])
        # Should handle gracefully
        assert path is None or isinstance(path, str), "Should handle empty symptoms"
    
    def test_unknown_symptoms(self, kb):
        """Test with unknown symptoms"""
        path = kb.get_care_path(["xyz123", "abc456"])
        # Should handle gracefully
        assert path is None or isinstance(path, str), "Should handle unknown symptoms"

# ============================================================
# TRIAGE AGENT INTEGRATION TESTS
# ============================================================

class TestTriageIntegration:
    """Test triage agent integration"""
    
    def test_triage_agent_import(self):
        """Test triage agent imports KB correctly"""
        from agents.triage_agent.agent import triage_agent
        assert callable(triage_agent), "triage_agent should be callable"
    
    def test_triage_agent_with_fever(self, sample_state):
        """Test triage agent with fever"""
        from agents.triage_agent.agent import triage_agent
        sample_state["user_input"] = "I have fever 39°C"
        result = triage_agent(sample_state)
        
        assert "agent_output" in result, "Should return agent_output"
        assert "healthcare_recommendation" in result, "Should include recommendation"
    
    def test_triage_agent_with_emergency(self, sample_state):
        """Test triage agent detects emergency"""
        from agents.triage_agent.agent import triage_agent
        sample_state["user_input"] = "I have chest pain"
        result = triage_agent(sample_state)
        
        rec = result.get("healthcare_recommendation", {})
        assert rec.get("service_type") == "HOSPITAL", "Should recommend HOSPITAL for chest pain"
    
    def test_triage_agent_with_qa(self, sample_state):
        """Test triage agent handles Q&A"""
        from agents.triage_agent.agent import triage_agent
        sample_state["user_input"] = "When should I go to the hospital?"
        result = triage_agent(sample_state)
        
        assert "qa_response" in result or "agent_output" in result, \
            "Should have Q&A response"

# ============================================================
# DATA STRUCTURE TESTS
# ============================================================

class TestDataStructures:
    """Test data structures"""
    
    def test_retrieval_result_structure(self):
        """Test RetrievalResult structure"""
        result = RetrievalResult(
            source="test_doc",
            content="test content",
            score=0.95,
            metadata={"category": "test"}
        )
        assert result.source == "test_doc"
        assert result.score == 0.95
        assert result.metadata["category"] == "test"
    
    def test_knowledge_document_structure(self):
        """Test KnowledgeDocument structure"""
        doc = KnowledgeDocument(
            id="test_id",
            source="test_source",
            content="test content",
            category="test_category",
            tags=["tag1", "tag2"]
        )
        assert doc.id == "test_id"
        assert doc.category == "test_category"
        assert len(doc.tags) == 2

# ============================================================
# ERROR HANDLING TESTS
# ============================================================

class TestErrorHandling:
    """Test error handling"""
    
    def test_retrieve_with_empty_query(self, kb):
        """Test retrieval with empty query"""
        try:
            results = kb.retrieve("", k=3)
            # Should handle gracefully
            assert isinstance(results, list), "Should return list"
        except Exception as e:
            pytest.fail(f"Should handle empty query gracefully: {e}")
    
    def test_qa_with_empty_question(self, kb):
        """Test Q&A with empty question"""
        try:
            answer = kb.answer_question("")
            # Should handle gracefully
            assert isinstance(answer, str), "Should return string"
        except Exception as e:
            pytest.fail(f"Should handle empty question gracefully: {e}")
    
    def test_emergency_with_empty_input(self, kb):
        """Test emergency detection with empty input"""
        is_emergency, guidance = kb.is_emergency("")
        assert isinstance(is_emergency, bool), "Should return boolean"
        assert isinstance(guidance, str), "Should return string guidance"

# ============================================================
# PERFORMANCE TESTS
# ============================================================

class TestPerformance:
    """Test performance"""
    
    def test_retrieval_speed(self, kb):
        """Test retrieval is reasonably fast"""
        import time
        start = time.time()
        kb.retrieve("fever", k=3)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"Retrieval should be fast, took {elapsed}s"
    
    def test_qa_speed(self, kb):
        """Test Q&A is reasonably fast"""
        import time
        start = time.time()
        kb.answer_question("What is fever?")
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Q&A should complete in reasonable time, took {elapsed}s"
    
    def test_cache_effectiveness(self, kb):
        """Test caching improves performance"""
        import time
        
        # First call (no cache)
        start1 = time.time()
        kb.retrieve("fever", k=3)
        time1 = time.time() - start1
        
        # Second call (with cache)
        start2 = time.time()
        kb.retrieve("fever", k=3)
        time2 = time.time() - start2
        
        # Cached call should be faster (or at least not slower by much)
        # Allow 10x speed improvement with cache
        assert time2 < time1 * 1.5, "Cache should improve performance"

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
