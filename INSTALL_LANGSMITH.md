# ⚡ LANGSMITH - INSTALLATION GUIDE

## 🎯 Problème actuel

```
❌ LANGSMITH_ENABLED: False
❌ API_KEY configured: False
Test Score: 5/6 passed
```

**Cause:** Variables d'environnement `.env` non configurées

---

## ✅ Solution (3 étapes - 5 minutes)

### Étape 1: Créer un compte LangSmith

1. Allez sur: **https://smith.langchain.com**
2. Cliquez "Sign Up"
3. Créez un compte (GitHub ou Email)
4. Confirmez votre email

**Temps:** 2 minutes

---

### Étape 2: Obtenir votre clé API

1. Sur le dashboard LangSmith
2. Cliquez **Settings** ⚙️ (coin bas gauche)
3. Cliquez **"API keys"**
4. Cliquez **"Create new key"**
5. Donnez un nom: `sahatek`
6. Cliquez **"Copy"** pour copier la clé
   - Format: `ls_xxxxxxxxxxxxxxxxxxxxx`

**Temps:** 1 minute

⚠️ **IMPORTANT:** Ne partagez JAMAIS cette clé!

---

### Étape 3: Créer le fichier `.env`

Fichier à créer: `e:\9raya_4eme_Sem1\Projet_Ia\sahatek\.env`

**Contenu:**
```env
# LANGSMITH CONFIGURATION
LANGCHAIN_API_KEY=ls_votre_cle_ici
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=sahatek-dev
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# GROQ API
GROQ_API_KEY=your_groq_key_here

# DJANGO
DEBUG=True
```

**Exemple réel:**
```env
LANGCHAIN_API_KEY=ls_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=sahatek-dev
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
GROQ_API_KEY=gsk_xxxxxxxxxxxx
DEBUG=True
```

**Temps:** 2 minutes

---

## ✨ Vérification

Une fois `.env` créé:

```bash
# 1. Redémarrez le terminal/VS Code

# 2. Lancez le test
python test_langsmith_integration.py

# Résultat attendu:
# ✓ LANGSMITH_ENABLED: True         (avant: False)
# ✓ API_KEY configured: True        (avant: False)
# 6/6 tests passed ✅                (avant: 5/6)
```

**Temps:** 1 minute

---

## 🚀 Après configuration

```bash
# 1. Lancer l'app
python manage.py runserver

# 2. Aller sur le dashboard
https://smith.langchain.com/projects/sahatek-dev

# 3. Faire une requête sur l'app
http://localhost:8000/chat

# 4. Voir les traces apparaître en temps réel!
```

---

## 📊 Que vais-je voir sur LangSmith?

Une fois configuré, vous verrez:

```
Project: sahatek-dev
├─ medical_agent::process_query [2.3s]
│  ├─ chroma_vector_db [0.2s]
│  ├─ web_search_duckduckgo [0.1s]
│  └─ groq_invoke [1.89s]
├─ triage_agent::extract_symptoms [0.5s]
├─ mental_health_agent::mental_health_processing [1.8s]
└─ rumor_agent traces...
```

Chaque trace inclut:
- ⏱️ Durée d'exécution
- 🔢 Tokens consommés
- 💾 Inputs/Outputs
- 📊 Métadonnées
- ❌ Erreurs (si présentes)

---

## 🆘 Problèmes?

### ".env not found"
```
Solution: Créer le fichier à la racine (même dossier que manage.py)
```

### "API key invalid"
```
Solution: Vérifier la clé exacte depuis https://smith.langchain.com/settings/api-keys
```

### "Tracing still disabled"
```
Solution: 
1. Vérifier que .env est au bon endroit
2. Redémarrer le terminal/VS Code
3. Relancer l'app
```

### "Module not found: langsmith"
```
Solution: pip install langsmith
```

---

## 📝 Checklist

- [ ] Compte LangSmith créé
- [ ] Clé API obtenue (format: ls_xxx)
- [ ] Fichier `.env` créé
- [ ] LANGCHAIN_API_KEY rempli
- [ ] LANGCHAIN_TRACING_V2=true
- [ ] Terminal/VS Code redémarré
- [ ] Test lancé: `python test_langsmith_integration.py`
- [ ] 6/6 tests passed ✅
- [ ] App lancée: `python manage.py runserver`
- [ ] Traces visibles sur https://smith.langchain.com/projects

---

## 🎉 C'est tout!

Une fois ces 3 étapes faites:
- ✅ LangSmith est activé
- ✅ Toutes les traces enregistrées
- ✅ Dashboard disponible
- ✅ Monitoring en temps réel

**Durée totale:** ~5 minutes

---

Pour plus de détails, voir: **README_LANGSMITH_COMPLETE.md**

Bon courage! 🍀
