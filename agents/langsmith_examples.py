# agents/langsmith_examples.py
"""
Exemples d'utilisation LangSmith avec les agents Sahatek
"""

from langsmith import trace, Client
import os

# ============================================================
# EXEMPLE 1: Tracer un appel d'agent simple
# ============================================================

@trace(name="rumor_verification_example")
def example_1_trace_agent_call():
    """
    Exemple 1: Tracer un appel d'agent
    Les traces LangSmith capturent automatiquement ce qui se passe
    """
    from agents.rumor.agent import RumorLangGraphAgent, RumorAgentState
    
    agent = RumorLangGraphAgent()
    
    state = RumorAgentState(
        user_input="Is vitamin C a cure for cold?",
        agent_output=None,
        current_agent="rumor",
        next_agent=None,
        metadata={},
        messages=[],
        rumor="",
        category="",
        verdict="",
        score=0,
        credibility_percentage=0.0,
        official_sources=[],
        web_sources=[],
        verification_details=None,
        language="en",
        safety_checks_passed=False
    )
    
    result = agent.process_query(state)
    return result

# ============================================================
# EXEMPLE 2: Créer des traces imbriquées
# ============================================================

@trace(name="conversation_flow")
def example_2_nested_traces():
    """
    Exemple 2: Traces imbriquées
    Montre la hiérarchie des appels
    """
    
    @trace(name="step_1_analyze_input")
    def analyze_input(text):
        # Analyser le texte
        return {"length": len(text), "language": "en"}
    
    @trace(name="step_2_route_to_agent")
    def route_to_agent(analysis):
        # Router vers l'agent approprié
        if analysis["length"] > 50:
            return "rumor_agent"
        else:
            return "general_agent"
    
    @trace(name="step_3_execute_agent")
    def execute_agent(agent_name, text):
        # Exécuter l'agent
        return {"agent": agent_name, "result": "processed"}
    
    text = "Is drinking lemon water good for you?"
    analysis = analyze_input(text)
    agent = route_to_agent(analysis)
    result = execute_agent(agent, text)
    
    return result

# ============================================================
# EXEMPLE 3: Évaluer les traces
# ============================================================

@trace(name="evaluate_rumor_quality")
def example_3_evaluate_quality(rumor):
    """
    Exemple 3: Évaluer la qualité d'une vérification
    Utilise les méthodes de scoring de LangSmith
    """
    from langsmith import evaluate
    
    # Exécuter l'agent
    from agents.rumor.agent import RumorLangGraphAgent, RumorAgentState
    
    agent = RumorLangGraphAgent()
    state = RumorAgentState(
        user_input=rumor,
        agent_output=None,
        current_agent="rumor",
        next_agent=None,
        metadata={},
        messages=[],
        rumor="",
        category="",
        verdict="",
        score=0,
        credibility_percentage=0.0,
        official_sources=[],
        web_sources=[],
        verification_details=None,
        language="en",
        safety_checks_passed=False
    )
    
    result = agent.process_query(state)
    
    # Retourner le résultat avec métrique
    return {
        "output": result["agent_output"],
        "score": result["credibility_percentage"],
        "verdict": result["verdict"]
    }

# ============================================================
# EXEMPLE 4: Utiliser le client LangSmith
# ============================================================

def example_4_client_operations():
    """
    Exemple 4: Opérations directes via le client LangSmith
    """
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        print("❌ LANGCHAIN_API_KEY not configured")
        return
    
    client = Client(api_key=api_key)
    
    # Lister les projets
    print("\n📋 Projets disponibles:")
    for project in client.list_projects():
        print(f"  - {project.name}")
    
    # Lister les traces récentes
    print("\n📊 Traces récentes:")
    for run in client.list_runs(project_name="sahatek-dev", limit=5):
        print(f"  - {run.name} ({run.status}) - {run.end_time}")
    
    # Créer un dataset
    print("\n📝 Création d'un dataset de test:")
    dataset = client.create_dataset(
        name="health_rumors_test",
        description="Test dataset pour la vérification de rumeurs",
        data=[
            {
                "inputs": {"rumor": "Lemon water detoxes your body"},
                "outputs": {"verdict": "NOT_CREDIBLE"},
            },
            {
                "inputs": {"rumor": "Vitamin C prevents colds"},
                "outputs": {"verdict": "QUESTIONABLE"},
            },
        ]
    )
    print(f"  ✅ Dataset créé: {dataset.name} ({len(dataset.data)} exemples)")

# ============================================================
# EXEMPLE 5: Comparer les versions d'agents
# ============================================================

@trace(name="compare_agent_versions")
def example_5_compare_versions():
    """
    Exemple 5: Comparer deux versions d'un agent
    Utile pour l'AB testing
    """
    
    test_rumors = [
        "Lemon water helps detox",
        "Vitamin C cures cold",
        "Coffee is bad for your health",
    ]
    
    results = {
        "v1": [],
        "v2": [],
    }
    
    # Version 1
    @trace(name="agent_v1")
    def agent_v1(rumor):
        # Votre première version d'agent
        return {"verdict": "UNKNOWN", "score": 0.5}
    
    # Version 2
    @trace(name="agent_v2")
    def agent_v2(rumor):
        # Votre deuxième version d'agent (avec amélioration)
        return {"verdict": "CREDIBLE", "score": 0.8}
    
    for rumor in test_rumors:
        results["v1"].append(agent_v1(rumor))
        results["v2"].append(agent_v2(rumor))
    
    return results

# ============================================================
# UTILISATION
# ============================================================

if __name__ == "__main__":
    import sys
    
    # Charger .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except:
        pass
    
    print("="*60)
    print("🚀 LANGSMITH EXAMPLES")
    print("="*60)
    
    examples = {
        "1": ("Tracer un appel d'agent", example_1_trace_agent_call),
        "2": ("Traces imbriquées", example_2_nested_traces),
        "3": ("Évaluer la qualité", lambda: example_3_evaluate_quality("Is water good for you?")),
        "4": ("Opérations client", example_4_client_operations),
        "5": ("Comparer les versions", example_5_compare_versions),
    }
    
    print("\nChoisir un exemple à exécuter:")
    for key, (desc, _) in examples.items():
        print(f"  {key}. {desc}")
    
    choice = input("\nChoix (1-5, ou 'q' pour quitter): ").strip()
    
    if choice == 'q':
        print("Au revoir!")
        sys.exit(0)
    
    if choice in examples:
        name, func = examples[choice]
        print(f"\n▶️  Exécution: {name}")
        print("-"*60)
        
        try:
            result = func()
            print("\n✅ Résultat:")
            print(result)
            print("-"*60)
            print("📊 La trace a été enregistrée dans LangSmith!")
            print("   Voir: https://smith.langchain.com/projects")
        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            print("\n💡 Conseil: Assurez-vous que LANGCHAIN_API_KEY est configurée")
    else:
        print("❌ Choix invalide")
