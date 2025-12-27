#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_langsmith_interactive.py
==============================
Script interactif pour configurer LangSmith pas à pas

Usage:
    python setup_langsmith_interactive.py
"""

import os
import sys
from pathlib import Path

def print_banner():
    """Affiche la bannière"""
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║        🚀 LANGSMITH SETUP WIZARD FOR SAHATEK 🚀           ║
║                                                            ║
║           Configurez LangSmith en 5 minutes!              ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
""")

def print_step(number, title):
    """Affiche une étape"""
    print(f"\n{'='*60}")
    print(f"Étape {number}: {title}")
    print(f"{'='*60}\n")

def step_1_account():
    """Étape 1: Créer un compte"""
    print_step(1, "Créer un compte LangSmith")
    
    print("1. Ouvrez: https://smith.langchain.com")
    print("2. Cliquez 'Sign Up'")
    print("3. Choisissez: GitHub ou Email")
    print("4. Confirmez votre email")
    print("\n✅ Vous avez un compte? (oui/non): ", end="")
    
    response = input().strip().lower()
    return response in ['oui', 'yes', 'y', 'o']

def step_2_api_key():
    """Étape 2: Obtenir la clé API"""
    print_step(2, "Obtenir votre clé API")
    
    print("1. Allez à: https://smith.langchain.com")
    print("2. Menu en bas à gauche → Settings ⚙️")
    print("3. Cliquez 'API keys'")
    print("4. 'Create new key' → 'Copy'")
    print("\nFormat attendu: ls_xxxxxxxxxxxxxxxxxxxxx")
    print("\n⚠️  Ne partagez jamais cette clé!")
    
    while True:
        print("\n🔑 Copiez votre clé API: ", end="")
        api_key = input().strip()
        
        if not api_key:
            print("❌ La clé ne peut pas être vide")
            continue
        
        if not api_key.startswith('ls_'):
            print("⚠️  Attention: La clé devrait commencer par 'ls_'")
            print("Continuer? (oui/non): ", end="")
            if input().strip().lower() not in ['oui', 'yes', 'y', 'o']:
                continue
        
        return api_key

def step_3_create_env():
    """Étape 3: Créer .env"""
    print_step(3, "Créer le fichier .env")
    
    env_path = Path(".env")
    
    if env_path.exists():
        print("⚠️  Le fichier .env existe déjà!")
        print("\nVoulez-vous le mettre à jour? (oui/non): ", end="")
        if input().strip().lower() not in ['oui', 'yes', 'y', 'o']:
            return False
    
    return True

def step_4_write_env(api_key):
    """Étape 4: Écrire le .env"""
    print_step(4, "Écrire la configuration")
    
    env_content = f"""# ============================================================
# LANGSMITH CONFIGURATION - Sahatek
# ============================================================
LANGCHAIN_API_KEY={api_key}
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=sahatek-dev
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# ============================================================
# OTHER CONFIGURATIONS (à compléter)
# ============================================================
GROQ_API_KEY=your_groq_key_here
DEBUG=True
"""
    
    try:
        env_path = Path(".env")
        with open(env_path, "w") as f:
            f.write(env_content)
        
        print(f"✅ Fichier .env créé: {env_path.absolute()}")
        print("\nContenu du fichier:")
        print("-" * 60)
        for line in env_content.split("\n"):
            if line.startswith("LANGCHAIN_API_KEY"):
                print(f"LANGCHAIN_API_KEY={api_key[:10]}...{api_key[-4:]}")
            else:
                print(line)
        print("-" * 60)
        
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la création: {e}")
        return False

def step_5_verify():
    """Étape 5: Vérifier la configuration"""
    print_step(5, "Vérifier la configuration")
    
    print("Vérification en cours...\n")
    
    # Charger .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠️  python-dotenv non installé")
        print("   Installez: pip install python-dotenv")
        return False
    
    checks = {
        "LANGCHAIN_API_KEY": "Clé API",
        "LANGCHAIN_TRACING_V2": "Tracing activé",
        "LANGCHAIN_PROJECT": "Nom du projet",
    }
    
    all_good = True
    for env_var, description in checks.items():
        value = os.getenv(env_var)
        if value:
            if env_var == "LANGCHAIN_API_KEY":
                print(f"✅ {description}: {value[:10]}...{value[-4:]}")
            else:
                print(f"✅ {description}: {value}")
        else:
            print(f"❌ {description}: NON DÉFINI")
            all_good = False
    
    # Vérifier LangSmith
    print("\nVérification LangSmith...")
    try:
        import langsmith
        print(f"✅ LangSmith installé (v{langsmith.__version__})")
    except ImportError:
        print("⚠️  LangSmith non installé")
        print("   Installez: pip install langsmith")
        return False
    
    return all_good

def step_6_test():
    """Étape 6: Tester"""
    print_step(6, "Lancer le test complet")
    
    print("Voulez-vous lancer le test d'intégration? (oui/non): ", end="")
    if input().strip().lower() not in ['oui', 'yes', 'y', 'o']:
        return True
    
    print("\nLancement du test...")
    print("-" * 60)
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "test_langsmith_integration.py"],
            capture_output=False
        )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def step_7_next_steps():
    """Étape 7: Prochaines étapes"""
    print_step(7, "🎉 Configuration terminée!")
    
    print("""
✅ LangSmith est maintenant configuré!

Prochaines étapes:

1️⃣  REDÉMARREZ votre terminal ou VS Code
    (Pour charger les variables d'environnement)

2️⃣  LANCEZ votre application Sahatek
    python manage.py runserver

3️⃣  TESTEZ les traces
    - Accédez à http://localhost:8000/
    - Effectuez une requête
    - Allez sur https://smith.langchain.com/projects
    - Vous verrez vos traces en temps réel!

4️⃣  EXPLOREZ le dashboard LangSmith
    - Voir les performances
    - Analyser les erreurs
    - Optimiser les agents

📚 Documentation:
   - Quick start: LANGSMITH_QUICKSTART.md
   - Guide complet: LANGSMITH_INTEGRATION.md
   - Diagnostic: python diagnostic_langsmith_setup.py

🆘 Problèmes?
   - Diagnostic: python diagnostic_langsmith_setup.py
   - FAQ: LANGSMITH_INTEGRATION.md
""")

def main():
    """Fonction principale"""
    try:
        print_banner()
        
        # Étape 1: Compte
        if not step_1_account():
            print("\n❌ Configuration annulée")
            return False
        
        # Étape 2: Clé API
        api_key = step_2_api_key()
        
        # Étape 3: Vérification .env
        if not step_3_create_env():
            print("\n❌ Configuration annulée")
            return False
        
        # Étape 4: Écrire .env
        if not step_4_write_env(api_key):
            print("\n❌ Erreur lors de la création de .env")
            return False
        
        # Étape 5: Vérifier
        if not step_5_verify():
            print("\n⚠️  Certaines vérifications ont échoué")
            print("Vérifiez que .env est correctement configuré")
        
        # Étape 6: Test
        test_success = step_6_test()
        
        # Étape 7: Prochaines étapes
        step_7_next_steps()
        
        return True
    except KeyboardInterrupt:
        print("\n\n❌ Configuration annulée par l'utilisateur")
        return False
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
