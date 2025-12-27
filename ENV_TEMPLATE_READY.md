# ✅ VOTRE .env - Template prêt à utiliser

## 🎯 Instructions

1. **Copier ce fichier** (tout le contenu)
2. **Créer un fichier `.env`** à la racine du projet
3. **Coller le contenu**
4. **Remplacer** `ls_your_api_key_here` par votre vraie clé

---

## 📋 CONTENU À COPIER

Copiez TOUT ce qui est entre les lignes pointillées et collez dans votre `.env`

```
.....................................................................

# ============================================================
# LANGSMITH CONFIGURATION
# ============================================================
# LangSmith API Key (get from https://smith.langchain.com/settings/api-keys)
LANGCHAIN_API_KEY=ls_your_api_key_here

# Enable tracing to LangSmith
LANGCHAIN_TRACING_V2=true

# Project name in LangSmith
LANGCHAIN_PROJECT=sahatek-dev

# LangSmith endpoint
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# ============================================================
# EXISTING CONFIGURATIONS (à compléter)
# ============================================================
# Groq API Key (for LLM calls)
GROQ_API_KEY=your_groq_key_here

# Django settings
DEBUG=True
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=sqlite:///db.sqlite3

.....................................................................
```

---

## 📝 ÉTAPES DÉTAILLÉES

### Étape 1: Créer le fichier `.env`

**Option A**: VS Code
1. Cliquez **File** → **New File**
2. Nommez-le `.env`
3. Sauvegardez à la racine (même dossier que `manage.py`)

**Option B**: PowerShell
```powershell
New-Item .env -ItemType File
```

**Option C**: CMD
```cmd
echo. > .env
```

---

### Étape 2: Obtenir votre clé API

1. Allez sur: **https://smith.langchain.com/settings/api-keys**
2. Cliquez **"Create new key"**
3. Donnez un nom: `sahatek`
4. Cliquez **"Copy"** (sur la nouvelle clé)
5. Cela copie quelque chose comme: `ls_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

---

### Étape 3: Remplir `.env`

Ouvrez le fichier `.env` que vous venez de créer et collez:

```env
# ============================================================
# LANGSMITH CONFIGURATION
# ============================================================
LANGCHAIN_API_KEY=ls_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=sahatek-dev
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# ============================================================
# EXISTING CONFIGURATIONS
# ============================================================
GROQ_API_KEY=your_groq_key_here
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///db.sqlite3
```

**⚠️ IMPORTANT**: Remplacez `ls_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6` par VOTRE vraie clé!

---

### Étape 4: Sauvegarder

Appuyez sur **Ctrl+S** dans VS Code

---

### Étape 5: Vérifier

Lancez:
```bash
python diagnostic_langsmith_setup.py
```

Devrait afficher:
```
✅ PASS - env_file
✅ PASS - env_vars
✅ PASS - langsmith_package
✅ PASS - decorators
✅ PASS - connection

5/5 vérifications réussies
🎉 TOUT EST CONFIGURÉ!
```

---

## 🔐 SÉCURITÉ

✅ **Jamais committer `.env`** dans Git
✅ Vérifiez que `.gitignore` contient `.env`:

```bash
# Vérifié?
grep -E "^\.env$" .gitignore
```

Ou ajoutez manuellement au `.gitignore`:
```
.env
.env.local
*.env
```

---

## 📍 LOCALISATION

Le fichier `.env` doit être:
```
e:\9raya_4eme_Sem1\Projet_Ia\sahatek\.env
                                      ^^^^
                                      Ici (à la racine)
```

Même dossier que:
```
manage.py
requirements.txt
README.md
```

---

## ❌ ERREURS COMMUNES

### Erreur 1: `.env` au mauvais endroit
```
❌ MAUVAIS: e:\...\agents\.env
✅ BON: e:\...\sahatek\.env
```

### Erreur 2: Mauvais format de clé
```
❌ MAUVAIS: LANGCHAIN_API_KEY = ls_xxx
✅ BON: LANGCHAIN_API_KEY=ls_xxx
         (pas d'espaces autour du =)
```

### Erreur 3: Clé incompète
```
❌ MAUVAIS: LANGCHAIN_API_KEY=ls_incomplete
✅ BON: LANGCHAIN_API_KEY=ls_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

### Erreur 4: `.env` non reloadé
```
Solution: Redémarrez le terminal ou VS Code
```

---

## ✅ CHECKLIST FINALE

- [ ] Compte LangSmith créé (https://smith.langchain.com)
- [ ] Clé API obtenue (https://smith.langchain.com/settings/api-keys)
- [ ] Fichier `.env` créé dans le bon dossier
- [ ] Contenu copié et collé
- [ ] Clé API remplacée
- [ ] Fichier sauvegardé (Ctrl+S)
- [ ] Terminal redémarré
- [ ] Diagnostic lancé: `python diagnostic_langsmith_setup.py`
- [ ] Tous les tests passent
- [ ] Prêt pour `python manage.py runserver`

---

## 🎯 PROCHAINES ÉTAPES

Une fois `.env` créé:

```bash
# 1. Vérifier
python diagnostic_langsmith_setup.py

# 2. Lancer les tests
python test_langsmith_integration.py

# 3. Redémarrer VS Code
# (Fermer et ouvrir)

# 4. Lancer l'app
python manage.py runserver

# 5. Accéder au dashboard
# http://localhost:8000
# https://smith.langchain.com/projects
```

---

## 💡 TIPS

### Pour tester rapidement
```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('API Key:', bool(os.getenv('LANGCHAIN_API_KEY'))); print('Tracing:', os.getenv('LANGCHAIN_TRACING_V2'))"
```

### Pour voir le contenu de `.env`
```bash
cat .env
# ou
Get-Content .env  # PowerShell
type .env  # CMD
```

### Pour voir la clé complète (attention!)
```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('LANGCHAIN_API_KEY'))"
```

---

## 📞 BESOIN D'AIDE?

```bash
# Diagnostic complet
python diagnostic_langsmith_setup.py

# Ou assistant interactif
python setup_langsmith_interactive.py

# Ou lire la documentation
# Voir: LANGSMITH_ACTIVATION.md
```

---

## 🎉 C'EST TOUT!

Une fois `.env` créé et sauvegardé:
- ✅ LangSmith est configuré
- ✅ Les tests vont passer
- ✅ Votre app va tracer les appels
- ✅ Le monitoring va fonctionner

**Vous êtes prêt!** 🚀

---

**Template créé**: 18 décembre 2024
**Format**: .env file
**Destination**: Racine du projet
