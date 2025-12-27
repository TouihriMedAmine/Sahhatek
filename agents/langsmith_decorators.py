# agents/langsmith_decorators.py
"""
LangSmith Decorators & Utilities - Réutilisable pour tous les agents
Intégration optimale et cohérente across tous les agents LangGraph
"""

import os
import functools
import logging
from typing import Any, Callable, Dict, Optional
from datetime import datetime

# Load environment variables from .env file FIRST (before anything else)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION LANGSMITH
# ============================================================

LANGSMITH_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGSMITH_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGCHAIN_PROJECT", "sahatek-dev")

# Import dynamique pour éviter les erreurs si LangSmith n'est pas installé
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = LANGSMITH_ENABLED and LANGSMITH_API_KEY is not None
except ImportError:
    LANGSMITH_AVAILABLE = False
    
    # Fallback decorator si LangSmith n'est pas disponible
    def traceable(func=None, *, run_type: str = "chain", name: Optional[str] = None, **kwargs):
        def decorator(f):
            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                return f(*args, **kwargs)
            return wrapper
        return decorator if func is None else decorator(func)


# ============================================================
# WRAPPERS UNIVERSELS POUR TOUS LES AGENTS
# ============================================================

def trace_agent_node(agent_name: str, node_name: Optional[str] = None):
    """
    Décorateur universel pour tracer les nœuds d'agents LangGraph
    Capture correctement l'input ET l'output (state.agent_output)
    
    Usage:
        @trace_agent_node("medical_agent", "diagnosis_node")
        def medical_diagnosis_node(state):
            ...
    """
    def decorator(func: Callable) -> Callable:
        trace_name = node_name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract state from arguments
            input_state = args[0] if args else kwargs.get('state', {})
            input_message = input_state.get('user_input', '') if isinstance(input_state, dict) else ''
            
            # Execute the function
            result_state = func(*args, **kwargs)
            
            # Extract output from result
            output_message = result_state.get('agent_output', '') if isinstance(result_state, dict) else ''
            
            if LANGSMITH_AVAILABLE:
                # Create a traceable function that captures the correct input/output
                @traceable(
                    run_type="chain",
                    name=f"{agent_name}::{trace_name}"
                )
                def trace_operation():
                    """Trace the agent node execution with proper input/output"""
                    return {
                        "input": input_message,
                        "output": output_message,
                        "agent": agent_name,
                        "node": trace_name,
                        "state_keys": list(result_state.keys()) if isinstance(result_state, dict) else []
                    }
                
                # Execute the trace
                trace_operation()
            
            return result_state
        
        return wrapper
    
    return decorator


def trace_llm_call(agent_name: str, model_name: Optional[str] = None):
    """
    Décorateur pour tracer les appels LLM
    
    Usage:
        @trace_llm_call("medical_agent", "groq_llama")
        def invoke_llm(prompt):
            ...
    """
    def decorator(func: Callable) -> Callable:
        trace_name = model_name or func.__name__
        
        if LANGSMITH_AVAILABLE:
            decorated = traceable(
                func,
                run_type="llm",
                name=f"{agent_name}::{trace_name}"
            )
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                logger.debug(f"[LLM {agent_name}::{trace_name}] Call started")
                result = func(*args, **kwargs)
                logger.debug(f"[LLM {agent_name}::{trace_name}] Call completed")
                return result
            decorated = wrapper
        
        return decorated
    
    return decorator


def trace_retrieval(agent_name: str, retriever_type: str = "vector"):
    """
    Décorateur pour tracer les opérations de récupération (RAG)
    
    Usage:
        @trace_retrieval("medical_agent", "chroma_db")
        def retrieve_documents(query):
            ...
    """
    def decorator(func: Callable) -> Callable:
        if LANGSMITH_AVAILABLE:
            decorated = traceable(
                func,
                run_type="retriever",
                name=f"{agent_name}::retrieve_{retriever_type}"
            )
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                logger.debug(f"[RETRIEVAL {agent_name}::{retriever_type}] Started")
                result = func(*args, **kwargs)
                logger.debug(f"[RETRIEVAL {agent_name}::{retriever_type}] Completed")
                return result
            decorated = wrapper
        
        return decorated
    
    return decorator


def trace_tool_call(agent_name: str, tool_name: str):
    """
    Décorateur pour tracer les appels à des outils/APIs externes
    
    Usage:
        @trace_tool_call("medical_agent", "web_search")
        def search_web(query):
            ...
    """
    def decorator(func: Callable) -> Callable:
        if LANGSMITH_AVAILABLE:
            decorated = traceable(
                func,
                run_type="tool",
                name=f"{agent_name}::{tool_name}"
            )
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                logger.debug(f"[TOOL {agent_name}::{tool_name}] Execution started")
                result = func(*args, **kwargs)
                logger.debug(f"[TOOL {agent_name}::{tool_name}] Execution completed")
                return result
            decorated = wrapper
        
        return decorated
    
    return decorator


# ============================================================
# UTILITAIRES POUR ENRICHIR LES MÉTADONNÉES
# ============================================================

def add_metadata_to_state(state: Dict[str, Any], agent_name: str, 
                         metadata_key: str, metadata_value: Any) -> Dict[str, Any]:
    """
    Enrichit le state avec des métadonnées LangSmith
    
    Usage:
        state = add_metadata_to_state(state, "medical_agent", "retrieval", {
            "docs_retrieved": 5,
            "vector_db": "chroma"
        })
    """
    if "metadata" not in state:
        state["metadata"] = {}
    
    if agent_name not in state["metadata"]:
        state["metadata"][agent_name] = {}
    
    state["metadata"][agent_name][metadata_key] = metadata_value
    state["metadata"][agent_name]["timestamp"] = datetime.now().isoformat()
    
    return state


def trace_state_update(state: Dict[str, Any], agent_name: str, 
                       previous_state: Optional[Dict[str, Any]] = None) -> None:
    """
    Log les changements de state pour debugging/monitoring
    
    Usage:
        trace_state_update(new_state, "medical_agent", old_state)
    """
    if not logger.isEnabledFor(logging.DEBUG):
        return
    
    logger.debug(f"[{agent_name}] State updated:")
    if "agent_output" in state and state["agent_output"]:
        logger.debug(f"  - agent_output length: {len(state['agent_output'])}")
    if "messages" in state:
        logger.debug(f"  - messages count: {len(state['messages'])}")
    if "metadata" in state and agent_name in state["metadata"]:
        logger.debug(f"  - metadata keys: {list(state['metadata'][agent_name].keys())}")


# ============================================================
# CONFIGURATION LANGSMITH
# ============================================================

def setup_langsmith_logging():
    """Configure le logging pour LangSmith"""
    if LANGSMITH_AVAILABLE:
        logger.info(f"✅ LangSmith enabled for project: {LANGSMITH_PROJECT}")
    else:
        logger.warning("⚠️  LangSmith tracing disabled - set LANGCHAIN_TRACING_V2=true")


# ============================================================
# VÉRIFICATION DE CONFIGURATION
# ============================================================

if __name__ == "__main__":
    print("\n📊 LangSmith Configuration Status:")
    print(f"  Enabled: {LANGSMITH_AVAILABLE}")
    print(f"  Project: {LANGSMITH_PROJECT}")
    print(f"  API Key configured: {LANGSMITH_API_KEY is not None}")
    setup_langsmith_logging()
