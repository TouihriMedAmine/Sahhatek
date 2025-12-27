# agents/langsmith_config.py
"""
Configuration LangSmith pour le monitoring et debugging des agents LangGraph
Intégration simple et recommandée pour le projet Sahatek
"""

import os
from langsmith import Client
from langsmith.utils import LangSmithEnvironmentError

# ============================================================
# LANGSMITH CONFIGURATION
# ============================================================

def setup_langsmith():
    """
    Configure LangSmith pour monitorer les agents
    
    Pour utiliser LangSmith:
    1. Créer un compte sur https://smith.langchain.com
    2. Générer une API key
    3. Ajouter à votre fichier .env:
       LANGCHAIN_API_KEY=your_api_key_here
       LANGCHAIN_TRACING_V2=true
       LANGCHAIN_PROJECT=sahatek  # Nom du projet
    """
    
    # Configuration via variables d'environnement
    api_key = os.getenv("LANGCHAIN_API_KEY")
    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    project_name = os.getenv("LANGCHAIN_PROJECT", "sahatek-dev")
    
    if not api_key:
        print("⚠️  LANGCHAIN_API_KEY not configured")
        print("   To use LangSmith, set: LANGCHAIN_API_KEY=your_key")
        return False
    
    if not tracing_enabled:
        print("⚠️  LangSmith tracing disabled")
        print("   To enable, set: LANGCHAIN_TRACING_V2=true")
        return False
    
    try:
        client = Client(api_key=api_key)
        print(f"✅ LangSmith configured successfully")
        print(f"   Project: {project_name}")
        print(f"   Monitoring: Enabled")
        return True
    except Exception as e:
        print(f"❌ Error configuring LangSmith: {e}")
        return False

def get_langsmith_client():
    """Récupère le client LangSmith"""
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if api_key:
        return Client(api_key=api_key)
    return None

# ============================================================
# UTILS - CUSTOM TRACING
# ============================================================

def trace_agent_call(agent_name: str, input_data: dict) -> dict:
    """
    Fonction helper pour tracer les appels d'agents
    Wrapper simple autour de la tracing LangSmith
    """
    from langsmith import trace
    
    @trace(name=f"{agent_name}_call")
    def _traced_call():
        return {"agent": agent_name, "input": input_data}
    
    return _traced_call()

# ============================================================
# ENVIRONMENT SETUP
# ============================================================

def print_langsmith_setup_guide():
    """Affiche le guide de configuration"""
    guide = """
╔════════════════════════════════════════════════════════════╗
║         LANGSMITH SETUP GUIDE FOR SAHATEK                  ║
╚════════════════════════════════════════════════════════════╝

1️⃣  CREATE ACCOUNT
    → Go to https://smith.langchain.com
    → Sign up with GitHub or Email

2️⃣  GET API KEY
    → Click "Settings" (bottom left)
    → Copy your API key

3️⃣  CONFIGURE ENVIRONMENT
    Create a .env file in your project root:

    LANGCHAIN_API_KEY=ls_your_api_key_here
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_PROJECT=sahatek-dev
    LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

4️⃣  VERIFY SETUP
    Run:
    python -c "from agents.langsmith_config import setup_langsmith; setup_langsmith()"

5️⃣  MONITOR TRACES
    → Open https://smith.langchain.com/projects
    → Your traces will appear in real-time

╔════════════════════════════════════════════════════════════╗
║ WHAT WILL BE TRACED:                                       ║
║ ✓ Each LLM call (Groq API)                                ║
║ ✓ Database operations                                      ║
║ ✓ Vector search (Chroma)                                  ║
║ ✓ Agent routing decisions                                 ║
║ ✓ Full LangGraph execution flow                           ║
╚════════════════════════════════════════════════════════════╝
"""
    print(guide)

if __name__ == "__main__":
    print_langsmith_setup_guide()
    setup_langsmith()
