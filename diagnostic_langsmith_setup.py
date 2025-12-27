#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnostic_langsmith_setup.py
=============================
Outil interactif pour configurer et diagnostiquer LangSmith

Usage:
    python diagnostic_langsmith_setup.py
"""

import os
import sys
from pathlib import Path

def print_header(title):
    """Affiche un titre formaté"""
    print(f"\n{'='*60}")
    print(f"🔍 {title}")
    print(f"{'='*60}\n")

def print_success(msg):
    """Affiche un message de succès"""
    print(f"✅ {msg}")

def print_error(msg):
    """Affiche un message d'erreur"""
    print(f"❌ {msg}")

def print_warning(msg):
    """Affiche un message d'avertissement"""
    print(f"⚠️  {msg}")

def print_info(msg):
    """Affiche un message d'information"""
    print(f"ℹ️  {msg}")

def check_env_file():
    """Vérifie la présence du fichier .env"""
    print_header("1️⃣  Vérification du fichier .env")
    
    env_path = Path(".env")
    env_template_path = Path(".env.template")
    
    if env_path.exists():
        print_success(f".env trouvé à: {env_path.absolute()}")
        return True
    elif env_template_path.exists():
        print_warning(f".env.template trouvé, mais pas .env")
        print_info("Créez .env en copiant .env.template")
        return False
    else:
        print_error("Ni .env ni .env.template trouvé!")
        print_info("Créez .env à la racine du projet")
        return False

def check_env_variables():
    """Vérifie les variables d'environnement"""
    print_header("2️⃣  Vérification des variables d'environnement")
    
    required_vars = {
        "LANGCHAIN_API_KEY": "Clé API LangSmith",
        "LANGCHAIN_TRACING_V2": "Activation du tracing",
        "LANGCHAIN_PROJECT": "Nom du projet",
    }
    
    all_set = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            if var == "LANGCHAIN_API_KEY":
                # Affiche la clé partiellement pour la sécurité
                masked = f"{value[:10]}...{value[-4:]}" if len(value) > 14 else "***"
                print_success(f"{var}: {masked}")
            else:
                print_success(f"{var}: {value}")
        else:
            print_error(f"{var}: ❌ NON DÉFINI")
            all_set = False
    
    return all_set

def check_langsmith_package():
    """Vérifie si LangSmith est installé"""
    print_header("3️⃣  Vérification de l'installation LangSmith")
    
    try:
        import langsmith
        version = langsmith.__version__
        print_success(f"langsmith installé (v{version})")
        
        try:
            from langsmith import Client
            print_success("Client LangSmith disponible")
            return True
        except ImportError as e:
            print_error(f"Client LangSmith non disponible: {e}")
            return False
    except ImportError:
        print_error("langsmith NOT installed!")
        print_info("Installez-le avec: pip install langsmith")
        return False

def test_langsmith_connection():
    """Teste la connexion à LangSmith"""
    print_header("4️⃣  Test de connexion LangSmith")
    
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        print_warning("LANGCHAIN_API_KEY non défini, skip")
        return False
    
    try:
        from langsmith import Client
        client = Client(api_key=api_key)
        print_success("Connexion à LangSmith réussie!")
        
        # Test de création de project
        try:
            project = client.get_project()
            print_success(f"Project: {project}")
            return True
        except Exception as e:
            print_warning(f"Impossible d'accéder au project: {e}")
            return False
    except Exception as e:
        print_error(f"Erreur de connexion: {e}")
        return False

def check_decorators():
    """Vérifie les décorateurs LangSmith dans le code"""
    print_header("5️⃣  Vérification des décorateurs")
    
    try:
        from agents.langsmith_decorators import (
            trace_agent_node,
            trace_llm_call,
            trace_retrieval,
            trace_tool_call,
        )
        print_success("Tous les décorateurs importés avec succès")
        return True
    except ImportError as e:
        print_error(f"Erreur d'import: {e}")
        return False

def generate_env_template():
    """Génère un template .env"""
    print_header("📝 Génération d'un template .env")
    
    template = """# ============================================================
# LANGSMITH CONFIGURATION
# ============================================================
LANGCHAIN_API_KEY=ls_your_api_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=sahatek-dev
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# ============================================================
# OTHER CONFIGURATIONS
# ============================================================
GROQ_API_KEY=your_groq_key_here
DEBUG=True
"""
    
    env_path = Path(".env")
    if not env_path.exists():
        with open(env_path, "w") as f:
            f.write(template)
        print_success(f".env créé à: {env_path.absolute()}")
        print_info("⚠️  N'oubliez pas de remplacer les valeurs!")
        return True
    else:
        print_warning(".env existe déjà")
        return False

def run_full_diagnostic():
    """Lance un diagnostic complet"""
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║         DIAGNOSTIC LANGSMITH SAHATEK                       ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    results = {}
    
    # 1. Vérifier .env
    results["env_file"] = check_env_file()
    
    # 2. Charger les variables d'environnement
    from dotenv import load_dotenv
    load_dotenv()
    
    # 3. Vérifier les variables
    results["env_vars"] = check_env_variables()
    
    # 4. Vérifier LangSmith installé
    results["langsmith_package"] = check_langsmith_package()
    
    # 5. Vérifier les décorateurs
    results["decorators"] = check_decorators()
    
    # 6. Tester la connexion
    if results["langsmith_package"] and results["env_vars"]:
        results["connection"] = test_langsmith_connection()
    else:
        results["connection"] = False
    
    # Résumé final
    print_header("📊 RÉSUMÉ DU DIAGNOSTIC")
    
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {check}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\n{passed}/{total} vérifications réussies\n")
    
    # Recommandations
    if not results["env_file"]:
        print("⚡ ACTION REQUISE:")
        print("   1. Créez .env à la racine du projet")
        print("   2. Copiez le contenu de .env.template")
        print("   3. Remplacez LANGCHAIN_API_KEY par votre clé")
    
    if not results["env_vars"]:
        print("\n⚡ ACTION REQUISE:")
        print("   Ajoutez à .env:")
        print("   LANGCHAIN_API_KEY=ls_your_key")
        print("   LANGCHAIN_TRACING_V2=true")
    
    if not results["langsmith_package"]:
        print("\n⚡ ACTION REQUISE:")
        print("   pip install langsmith")
    
    if results["env_vars"] and results["langsmith_package"] and not results["connection"]:
        print("\n⚡ ACTION REQUISE:")
        print("   Vérifiez votre API key sur https://smith.langchain.com")
    
    if passed == total:
        print("\n🎉 TOUT EST CONFIGURÉ! Vous pouvez utiliser LangSmith")
        print("   Les traces apparaîtront sur: https://smith.langchain.com/projects")
    
    return passed == total

def main():
    """Fonction principale"""
    try:
        # Charger dotenv si disponible
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            print_warning("python-dotenv non installé")
            print_info("Installez-le avec: pip install python-dotenv")
        
        # Lancer le diagnostic
        success = run_full_diagnostic()
        
        sys.exit(0 if success else 1)
    except Exception as e:
        print_error(f"Erreur pendant le diagnostic: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
