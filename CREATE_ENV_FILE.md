# 🔑 CRÉER LE FICHIER `.env` - INSTRUCTIONS

## ⚠️ IMPORTANT

Le fichier `.env` doit être créé **à la racine du projet** (même dossier que `manage.py`)

```
e:\9raya_4eme_Sem1\Projet_Ia\sahatek\
├── manage.py
├── requirements.txt
├── .env                ← À CRÉER ICI
└── ...
```

---

## 📍 CHEMIN EXACT

```
e:\9raya_4eme_Sem1\Projet_Ia\sahatek\.env
```

NON PAS:
```
❌ e:\9raya_4eme_Sem1\Projet_Ia\sahatek\agents\.env
❌ e:\9raya_4eme_Sem1\Projet_Ia\.env
```

---

## 🎯 CONTENU DU FICHIER `.env`

Copiez exactement ceci dans le fichier `.env`:

```env
# ============================================================
# LANGSMITH CONFIGURATION (REQUIRED)
# ============================================================
LANGCHAIN_API_KEY=ls_votre_cle_ici_remplacer
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=sahatek-dev
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# ============================================================
# GROQ API (FOR LLM CALLS)
# ============================================================
GROQ_API_KEY=your_groq_key_here

# ============================================================
# DJANGO
# ============================================================
DEBUG=True
```

**REMPLACEZ CECI:**
```
ls_votre_cle_ici_remplacer
↓↓↓
ls_votre_vraie_cle_depuis_langsmith
```

---

## 🔐 OÙ OBTENIR LA CLÉ

1. Allez sur: **https://smith.langchain.com/settings/api-keys**
2. Cliquez: **"Create new key"**
3. Donnez un nom: `sahatek`
4. Cliquez: **"Copy"**

Vous obtenez quelque chose comme:
```
ls_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

Copiez ceci dans `.env`:
```env
LANGCHAIN_API_KEY=ls_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

---

## 🛠️ CRÉER LE FICHIER

### Option 1: VS Code (FACILE)

1. Ouvrez VS Code
2. Menu: **File** → **New File**
3. Tapez le contenu du `.env` (voir ci-dessus)
4. **File** → **Save As** → Nommez `.env`
5. Sauvegardez à la racine du projet (même dossier que manage.py)

### Option 2: Terminal PowerShell

```powershell
# Se positioner à la racine
cd e:\9raya_4eme_Sem1\Projet_Ia\sahatek

# Créer le fichier
New-Item .env -ItemType File -Value @"
LANGCHAIN_API_KEY=ls_votre_cle_ici
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=sahatek-dev
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
GROQ_API_KEY=your_groq_key_here
DEBUG=True
"@
```

### Option 3: Copier le template

Vous avez probablement un `.env.example` ou `.env.template`

```bash
# Windows CMD
copy .env.example .env

# Windows PowerShell
Copy-Item .env.example .env

# Linux/Mac
cp .env.example .env
```

Puis éditez le fichier `.env` pour remplacer:
```
ls_your_api_key_here → ls_votre_vraie_cle
```

---

## ✅ VÉRIFICATION

Une fois le fichier créé:

### Vérifier qu'il existe
```powershell
Test-Path .env
# Résultat: True
```

### Vérifier le contenu
```powershell
Get-Content .env
# Affiche le contenu du fichier
```

### Vérifier que les variables se chargent
```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('API Key:', bool(os.getenv('LANGCHAIN_API_KEY'))); print('Tracing:', os.getenv('LANGCHAIN_TRACING_V2'))"
```

**Résultat attendu:**
```
API Key: True
Tracing: true
```

---

## 🚀 APRÈS AVOIR CRÉÉ `.env`

```bash
# 1. Redémarrer le terminal
# (Fermer et ouvrir PowerShell/CMD)

# 2. Redémarrer VS Code
# (Fermer et ouvrir VS Code)

# 3. Lancer le test
python test_langsmith_integration.py

# Résultat attendu:
# ✓ LANGSMITH_ENABLED: True        (avant: False)
# ✓ API_KEY configured: True       (avant: False)
# 6/6 tests passed ✅               (avant: 5/6)
```

---

## ⚠️ ERREURS COURANTES

### Erreur: "LANGSMITH_ENABLED: False"

**Cause:** `.env` non trouvé ou non chargé

**Solution:**
```
1. Vérifier que .env existe à: e:\...\sahatek\.env
2. Redémarrer le terminal
3. Redémarrer VS Code
4. Relancer le test
```

### Erreur: "API key invalid"

**Cause:** Clé incorrecte ou mal copiée

**Solution:**
```
1. Aller sur https://smith.langchain.com/settings/api-keys
2. Copier la NOUVELLE clé (pas l'ancienne)
3. Remplacer dans .env
4. Redémarrer et tester
```

### Erreur: ".env not loaded"

**Cause:** Terminal ou VS Code ne charge pas les nouvelles variables

**Solution:**
```
1. Fermer complètement VS Code
2. Fermer complètement le terminal
3. Ouvrir VS Code
4. Ouvrir le terminal
5. Relancer le test
```

---

## 🔐 SÉCURITÉ

✅ **IMPORTANT:**
- ✅ `.env` est dans `.gitignore` (ne pas committer)
- ✅ Ne jamais partager le fichier `.env`
- ✅ Ne jamais mettre l'API key dans le code source
- ✅ Ne jamais mettre l'API key dans les commits
- ✅ `.env` est local uniquement

---

## 📝 EXEMPLE RÉEL

**Si vous avez reçu une clé comme:**
```
ls_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

**Votre `.env` devrait avoir:**
```env
LANGCHAIN_API_KEY=ls_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=sahatek-dev
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
GROQ_API_KEY=your_groq_key_here
DEBUG=True
```

**Puis redémarrer et tester:**
```bash
python test_langsmith_integration.py
# Résultat: 6/6 PASS ✅
```

---

## 🎯 CHECKLIST FINALE

- [ ] Vous avez obtenu la clé API LangSmith
- [ ] Vous avez créé le fichier `.env`
- [ ] Le fichier est à la bonne location: `sahatek/.env`
- [ ] LANGCHAIN_API_KEY est rempli correctement
- [ ] LANGCHAIN_TRACING_V2=true
- [ ] Le terminal est redémarré
- [ ] VS Code est redémarré
- [ ] Vous avez lancé: `python test_langsmith_integration.py`
- [ ] Résultat: 6/6 tests passed ✅

---

## ✨ C'EST TOUT!

Une fois cette étape faite:
- ✅ LangSmith est configuré
- ✅ Tests passent 6/6
- ✅ Vous êtes prêt à lancer l'app
- ✅ Toutes les traces seront enregistrées

**Prochaine étape:**
```bash
python manage.py runserver
# Puis allez sur: https://smith.langchain.com/projects
```

---

**Questions?** Voir: **README_LANGSMITH_COMPLETE.md**

Bon courage! 🍀
