# agents/triage_agent/knowledge_base.py
"""
Triage Knowledge Base System
Converts documentation into a searchable knowledge base using embeddings and vector storage.
Integrates with Q&A and recommendation systems for comprehensive triage support.
"""

from __future__ import annotations
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import hashlib

import httpx
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================
KB_PATH = "triage_knowledge_base"
EMB_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
RETRIEVER_K = 5

# ============================================================
# DATA STRUCTURES
# ============================================================
@dataclass
class KnowledgeDocument:
    """Structured knowledge document"""
    id: str
    title: str
    category: str  # triage_guidance, symptoms, conditions, recommendations, care_paths
    content: str
    metadata: Dict[str, Any]

@dataclass
class RetrievalResult:
    """Result from knowledge base retrieval"""
    content: str
    score: float
    metadata: Dict[str, Any]
    source: str

# ============================================================
# KNOWLEDGE BASE DOCUMENTS (Converted from MD files)
# ============================================================
KNOWLEDGE_DOCUMENTS: List[KnowledgeDocument] = [
    # HEALTHCARE SERVICES
    KnowledgeDocument(
        id="service_stay_home",
        title="STAY_HOME Service Type",
        category="recommendations",
        content="""STAY_HOME Service Type:
Use for self-limiting viral illnesses that typically resolve on their own.
Examples: Mild flu, common cold, mild viral infections, runny nose.
Characteristics:
- Self-care with rest, fluids, supportive measures
- Monitor for worsening symptoms
- Seek care if symptoms escalate
Recommendations:
- Rest and sleep (7-9 hours daily)
- Stay hydrated with water, electrolytes
- Use humidifier if needed
- Monitor temperature
- Seek emergency care if: difficulty breathing, chest pain, confusion""",
        metadata={"service_type": "STAY_HOME", "severity": "mild", "immediate_care": False}
    ),
    
    KnowledgeDocument(
        id="service_pharmacy",
        title="PHARMACY Service Type",
        category="recommendations",
        content="""PHARMACY Service Type:
Use for minor conditions treatable with over-the-counter medications.
Examples: Mild headache, allergy symptoms, skin irritation, mild digestive issues.
Characteristics:
- OTC medications available
- No prescription needed
- Relief typically within 24-48 hours
Common OTC Options:
- Pain relief: Ibuprofen, Paracetamol
- Allergy: Antihistamines
- Digestive: Antacids, anti-diarrheal
- Skin: Antibiotic ointments, hydrocortisone
When to escalate:
- Symptoms worsen despite OTC
- Allergic reaction develops
- Symptoms persist >7 days""",
        metadata={"service_type": "PHARMACY", "severity": "mild", "immediate_care": False}
    ),
    
    KnowledgeDocument(
        id="service_doctor",
        title="DOCTOR/CLINIC Service Type",
        category="recommendations",
        content="""DOCTOR/CLINIC Service Type:
Use for moderate conditions requiring professional evaluation.
Examples: Persistent symptoms, moderate pain, chronic conditions needing management.
Characteristics:
- Professional diagnosis needed
- May require prescription
- Follow-up appointments may be necessary
When to visit doctor:
- Symptoms persist >7-10 days
- Need prescription medication
- Uncertain diagnosis
- Chronic condition management
- Preventive care/vaccines
Expected appointment time: 1-2 weeks for routine, 2-3 days for urgent""",
        metadata={"service_type": "DOCTOR", "severity": "moderate", "immediate_care": False}
    ),
    
    KnowledgeDocument(
        id="service_urgent",
        title="URGENT_CARE Service Type",
        category="recommendations",
        content="""URGENT_CARE Service Type:
Use for urgent but not life-threatening conditions needing same-day evaluation.
Examples: Severe pain, high fever, injuries, acute infections.
Characteristics:
- Available same-day or next appointment
- Extended hours available
- Faster than regular clinic appointment
When to use URGENT_CARE:
- Severe pain (7-10/10)
- Fever >39°C (102°F)
- Acute illness symptoms
- Minor injuries needing evaluation
- Unable to see regular doctor immediately
NOT for emergencies:
- Chest pain at rest
- Difficulty breathing
- Severe bleeding
- Loss of consciousness""",
        metadata={"service_type": "URGENT_CARE", "severity": "moderate-severe", "immediate_care": True}
    ),
    
    KnowledgeDocument(
        id="service_hospital",
        title="HOSPITAL Service Type",
        category="recommendations",
        content="""HOSPITAL Service Type:
Use for serious or life-threatening conditions requiring emergency care.
Examples: Chest pain, difficulty breathing, severe trauma, neurological symptoms.
Characteristics:
- 24/7 availability
- Emergency department with specialists
- Advanced diagnostic capabilities
- Potential hospitalization needed
Go to HOSPITAL immediately if:
- Chest pain or pressure
- Difficulty breathing or shortness of breath
- Severe abdominal pain
- Loss of consciousness
- Severe bleeding
- Severe head/neck/back injury
- Poisoning or overdose
- Severe allergic reaction
- Symptoms of stroke (facial drooping, arm weakness, speech difficulty)
Call ambulance or go directly to emergency department""",
        metadata={"service_type": "HOSPITAL", "severity": "severe", "immediate_care": True}
    ),
    
    KnowledgeDocument(
        id="service_mental_health",
        title="MENTAL_HEALTH Service Type",
        category="recommendations",
        content="""MENTAL_HEALTH Service Type:
Use for mental health crises and psychological support.
Examples: Severe anxiety, depression, suicidal ideation, acute stress.
Characteristics:
- Mental health professionals
- Crisis intervention available
- Psychiatric assessment and treatment
- Support services
When to seek MENTAL_HEALTH care:
- Suicidal or homicidal thoughts
- Severe anxiety or panic
- Inability to function (work, self-care)
- Substance abuse crisis
- Acute trauma response
- Severe depression with hopelessness
CRISIS HOTLINES (available 24/7):
- National Suicide Prevention Lifeline: 1-800-273-8255
- Crisis Text Line: Text HOME to 741741
- International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/""",
        metadata={"service_type": "MENTAL_HEALTH", "severity": "variable", "immediate_care": True}
    ),
    
    # SYMPTOM ASSESSMENT
    KnowledgeDocument(
        id="symptom_assessment_fever",
        title="Fever Assessment",
        category="symptoms",
        content="""Fever Assessment:
Definition: Body temperature above 37.5°C (99.5°F)
Significance:
- Sign of infection or inflammation
- Body's immune response
- Usually self-limiting with viral illness
Fever levels:
- Low-grade: 37.5-38.5°C (comfort level usually maintained)
- Moderate: 38.5-39.5°C (significant discomfort)
- High: >39.5°C (requires medical attention)
Associated symptoms:
- Chills, sweating
- Body aches
- Fatigue
- Headache
When fever is concerning:
- >40°C (104°F)
- Lasting >7 days without cause identified
- With difficulty breathing
- With confusion or altered mental status
- In infants <3 months with any fever
- In elderly or immunocompromised
Treatment:
- Fluids, rest
- Ibuprofen or Paracetamol (dosage per weight/age)
- Cool compress (NOT ice bath)
- Light clothing""",
        metadata={"symptom": "fever", "severity": "variable", "alert_level": "medium"}
    ),
    
    KnowledgeDocument(
        id="symptom_assessment_cough",
        title="Cough Assessment",
        category="symptoms",
        content="""Cough Assessment:
Definition: Involuntary expulsion of air from lungs
Types:
- Dry cough: No mucus production (viral, asthma, post-viral)
- Wet/Productive: With mucus (bronchitis, pneumonia)
- Chronic: Lasting >3 weeks
Associated symptoms:
- Sore throat
- Runny nose
- Fever
- Chest pain
- Shortness of breath
Concerning features:
- Blood in sputum
- Shortness of breath at rest
- High fever (>39.5°C)
- Persistent >3 weeks
- Green/yellow sputum (possible bacterial infection)
Management:
- Most coughs viral (self-limiting 1-3 weeks)
- Honey can help (adults, not <1 year)
- Humidifier may help
- Avoid irritants (smoke, pollution)
When to see doctor:
- Productive cough >2 weeks
- Hemoptysis (coughing blood)
- Shortness of breath
- Asthma/COPD with worsening cough""",
        metadata={"symptom": "cough", "severity": "variable", "alert_level": "medium"}
    ),
    
    KnowledgeDocument(
        id="symptom_assessment_chest_pain",
        title="Chest Pain Assessment (RED FLAG)",
        category="symptoms",
        content="""Chest Pain Assessment - RED FLAG SYMPTOM:
SEEK EMERGENCY CARE IF:
- Chest pain with pressure/tightness
- Pain radiating to arm, jaw, or back
- Shortness of breath with chest pain
- Diaphoresis (sudden sweating)
- Nausea/vomiting with chest pain
Immediate action: Call 911 or go to emergency department
Types of chest pain:
1. Cardiac: Pressure, heaviness, radiating, with exertion
2. Musculoskeletal: Reproducible with pressure, positional
3. Pleuritic: Sharp, worse with breathing/coughing
4. Gastrointestinal: Burning, worse after eating
5. Anxiety: Sharp, localized, with palpitations
Assessment questions:
- When started? Sudden or gradual?
- Constant or intermittent?
- What makes it worse/better?
- Associated symptoms?
- Medical history/risk factors?
DO NOT ignore chest pain - always seek professional evaluation
Risk factors requiring immediate attention:
- Age >50
- Hypertension
- Diabetes
- High cholesterol
- Smoking
- Family history of heart disease""",
        metadata={"symptom": "chest_pain", "severity": "critical", "alert_level": "critical"}
    ),
    
    # CONDITION-SPECIFIC GUIDANCE
    KnowledgeDocument(
        id="condition_flu",
        title="Influenza (Flu) Management",
        category="conditions",
        content="""Influenza (Flu) Management:
Definition: Viral respiratory infection, highly contagious
Typical symptoms:
- Fever 38-40°C
- Muscle/body aches
- Fatigue
- Cough (usually dry initially)
- Headache
- Sore throat
Onset: Sudden (1-3 days)
Duration: 7-10 days for most, cough may persist 2+ weeks
Complications risk (requires doctor visit):
- Secondary bacterial infection
- Pneumonia
- Bronchitis
- In high-risk groups: severe illness
Management:
- Rest 7-10 days
- Hydration (fluids, electrolytes)
- Antipyretics for fever (Ibuprofen/Paracetamol)
- Cough support (honey, humidifier)
- Isolation to prevent spread (5-7 days)
When to seek care:
- Symptoms not improving by day 7
- Shortness of breath
- Confusion
- Persistent fever >3 days despite medication
- High-risk patients (age >65, pregnancy, chronic illness)
Prevention:
- Annual flu vaccine (most effective prevention)
- Handwashing
- Respiratory hygiene
Antiviral treatment:
- Oseltamivir (Tamiflu) can reduce duration if started early (<48h)
- Most effective for high-risk patients""",
        metadata={"condition": "flu", "severity": "mild-moderate", "recommended_service": "STAY_HOME or PHARMACY"}
    ),
    
    KnowledgeDocument(
        id="condition_cold",
        title="Common Cold Management",
        category="conditions",
        content="""Common Cold Management:
Definition: Mild viral respiratory infection
Typical symptoms:
- Runny/stuffy nose
- Cough
- Sore throat
- Sneezing
- Mild fatigue
- Usually NO fever (or low-grade)
Onset: Gradual (1-2 days)
Duration: 7-10 days typical
Symptoms timeline:
- Days 1-3: Nasal symptoms, sneezing
- Days 4-7: Congestion, possibly cough
- Days 8-10: Lingering cough possible
Management:
- Rest and fluids
- Saline nasal drops/spray
- Humidifier
- Warm compress for sinus
- Lozenges for throat
- Honey for cough
OTC medications:
- Decongestants (limited use 3-5 days max)
- Antihistamines (if allergic component)
- Pain relief (if sore throat/headache)
NO antibiotics (viral infection)
When to escalate care:
- Symptoms progress after 10 days
- Fever develops (>38°C)
- Green sputum (possible bacterial infection)
- Shortness of breath
- Ear pain (possible infection)
Prevention:
- Handwashing
- Avoid touching face
- Respiratory etiquette
- Stay hydrated
- Sleep adequate hours""",
        metadata={"condition": "cold", "severity": "mild", "recommended_service": "STAY_HOME or PHARMACY"}
    ),
    
    # TRIAGE DECISION PATHS
    KnowledgeDocument(
        id="triage_path_respiratory",
        title="Respiratory Symptom Triage Path",
        category="care_paths",
        content="""Respiratory Symptom Triage Path:
START: Cough and/or sore throat
├─ With chest pain and/or shortness of breath?
│  ├─ YES → HOSPITAL (possible pneumonia/pulmonary issue)
│  └─ NO → Continue
├─ Fever >39.5°C?
│  ├─ YES → URGENT_CARE (evaluate for bacterial infection)
│  └─ NO → Continue
├─ Green/yellow sputum or hemoptysis?
│  ├─ YES → DOCTOR/URGENT_CARE (possible bacterial infection)
│  └─ NO → Continue
├─ Shortness of breath at rest?
│  ├─ YES → URGENT_CARE or HOSPITAL
│  └─ NO → Continue
├─ Symptom duration?
│  ├─ <3 days → STAY_HOME (likely viral, give supportive care 3-5 more days)
│  ├─ 3-7 days → PHARMACY (OTC support)
│  └─ >7 days → DOCTOR (persistent viral or bacterial infection)
└─ No concerning features → STAY_HOME with monitoring
Follow-up: Seek care if worsening or new symptoms develop""",
        metadata={"symptom_group": "respiratory", "complexity": "moderate"}
    ),
    
    KnowledgeDocument(
        id="triage_path_fever",
        title="Fever Triage Path",
        category="care_paths",
        content="""Fever Triage Path:
START: Fever (>37.5°C)
├─ Fever >40.5°C (104.9°F)?
│  ├─ YES → HOSPITAL (seek immediate evaluation)
│  └─ NO → Continue
├─ Associated confusion, severe headache, or neck stiffness?
│  ├─ YES → HOSPITAL (possible meningitis)
│  └─ NO → Continue
├─ Difficulty breathing?
│  ├─ YES → URGENT_CARE/HOSPITAL
│  └─ NO → Continue
├─ Other concerning symptoms?
│  ├─ Rash → HOSPITAL (possible measles/meningococcal)
│  ├─ Abdominal pain → URGENT_CARE
│  ├─ Severe pain anywhere → URGENT_CARE
│  └─ NO → Continue
├─ Fever duration?
│  ├─ <3 days, mild symptoms → STAY_HOME (observe)
│  ├─ 3-7 days, moderate symptoms → PHARMACY or DOCTOR
│  └─ >7 days without clear cause → DOCTOR (investigate)
├─ Age risk factors?
│  ├─ <3 months → DOCTOR (any fever warrants evaluation)
│  ├─ >65 years → DOCTOR or URGENT_CARE
│  └─ Otherwise → Continue pathway
└─ Manage with rest, fluids, antipyretics; reassess in 48-72 hours""",
        metadata={"symptom_group": "fever", "complexity": "moderate"}
    ),
    
    # EMERGENCY RED FLAGS
    KnowledgeDocument(
        id="emergency_red_flags",
        title="Emergency Red Flags - SEEK IMMEDIATE CARE",
        category="triage_guidance",
        content="""Emergency Red Flags - GO TO HOSPITAL/CALL 911 IMMEDIATELY:
Critical symptoms requiring immediate emergency evaluation:
CARDIOVASCULAR:
- Chest pain/pressure/heaviness
- Severe shortness of breath
- Heart palpitations with dizziness
RESPIRATORY:
- Severe difficulty breathing
- Stridor (high-pitched breathing)
- Cyanosis (blue lips/fingers)
NEUROLOGICAL:
- Loss of consciousness
- Severe headache with fever/stiff neck
- Facial drooping
- Arm/leg weakness (stroke signs)
- Slurred speech
- Severe dizziness/vertigo
- Seizures
GASTROINTESTINAL:
- Severe abdominal pain
- Vomiting with severe pain
- Hematemesis (coughing/vomiting blood)
TRAUMA/INJURY:
- Severe bleeding
- Head/neck/spine injury
- Suspected fractures
TOXICOLOGICAL:
- Poisoning or overdose
- Allergic reaction (throat swelling, breathing difficulty)
GENERAL:
- Altered mental status/confusion
- Extreme weakness/lethargy
- Core temperature <35°C or >40.5°C
- Signs of shock (pale, cold, sweaty, confusion)
PSYCHIATRIC:
- Suicidal/homicidal ideation with intent
- Acute severe psychiatric crisis
ACTION: Call emergency services or go directly to hospital
DO NOT DELAY - These conditions are potentially life-threatening""",
        metadata={"severity": "critical", "requires_immediate_care": True}
    ),
    
    # Q&A GUIDANCE
    KnowledgeDocument(
        id="qa_when_antibiotics",
        title="When Are Antibiotics Needed?",
        category="triage_guidance",
        content="""When Are Antibiotics Needed?
Understanding bacterial vs viral infections:
VIRAL INFECTIONS (NO antibiotics help):
- Common cold, flu, bronchitis (in most cases)
- Most sore throats
- Most coughs
- Chickenpox, measles
- Respiratory syncytial virus (RSV)
Duration: Self-limiting, typically 7-14 days
BACTERIAL INFECTIONS (antibiotics needed):
- Strep throat
- Ear infections (some)
- Sinus infections (some)
- Urinary tract infections
- Pneumonia (bacterial)
- Whooping cough
- Skin/soft tissue infections (impetigo, cellulitis)
Signs suggesting BACTERIAL infection:
- Green/yellow sputum
- Persistent high fever >3-5 days
- Rapid worsening after initial improvement
- Pus-filled lesions
- Specific symptoms (e.g., red throat with white patches = possible strep)
Signs suggesting VIRAL infection:
- Gradual onset
- General malaise, body aches
- Clear/watery nasal discharge
- Cough without sputum
- Self-improving over 7-10 days
Important notes:
- Taking antibiotics for viral infections: not helpful, increases resistance
- Antibiotic resistance is global health threat
- Some infections clear better with supportive care alone
- Always ask: "Is this likely bacterial?"
When in doubt: See doctor for proper diagnosis (throat culture, etc.)""",
        metadata={"topic": "antibiotics", "educational_level": "general"}
    ),
    
    KnowledgeDocument(
        id="qa_when_hospital",
        title="When Should I Go to the Hospital?",
        category="triage_guidance",
        content="""When Should I Go to the Hospital?
Hospital is for emergencies and serious conditions:
GO TO HOSPITAL IF:
EMERGENCIES (life-threatening):
- Chest pain or pressure
- Severe difficulty breathing
- Sudden severe headache
- Symptoms of stroke (face drooping, arm weakness, speech trouble)
- Severe abdominal pain
- Loss of consciousness
- Severe bleeding
- Poisoning/overdose
- Anaphylaxis (severe allergic reaction)
URGENT (needs evaluation today):
- High fever >39.5°C not responding to medication
- Moderate-severe pain
- Possible pneumonia (fever + chest pain + shortness of breath)
- Acute injuries
- Signs of infection spreading (spreading redness, increasing pain)
GO TO URGENT CARE IF:
- Moderate symptoms needing same-day evaluation
- Cannot reach regular doctor
- Minor injuries needing evaluation
- Symptoms concerning but not emergency
GO TO DOCTOR IF:
- Mild-moderate symptoms
- Can wait 1-3 days
- Ongoing condition management
STAY HOME IF:
- Mild symptoms (cold, mild flu)
- Able to care for self
- No emergency signs
- Symptoms manageable at home
Remember: When in doubt, call a nurse hotline or doctor for guidance
Many ERs are overcrowded - use appropriately for true emergencies""",
        metadata={"topic": "hospital_usage", "practical_guidance": True}
    ),
]

# ============================================================
# TRIAGE KNOWLEDGE BASE
# ============================================================
class TriageKnowledgeBase:
    """Triage-specific knowledge base with embeddings and retrieval"""
    
    def __init__(self, path: str = KB_PATH):
        """Initialize knowledge base"""
        logger.info("🔧 Initializing Triage Knowledge Base...")
        self.path = path
        self.embeddings = HuggingFaceEmbeddings(model_name=EMB_MODEL)
        self.vectorstore = None
        self.documents = []
        self.query_cache = {}
        self._initialize_vectorstore()
    
    def _initialize_vectorstore(self):
        """Initialize or load vectorstore"""
        try:
            # Try to load existing vectorstore
            self.vectorstore = Chroma(
                persist_directory=self.path,
                embedding_function=self.embeddings,
                collection_name="triage_kb"
            )
            count = self.vectorstore._collection.count()
            if count > 0:
                logger.info(f"✅ Loaded existing knowledge base with {count} documents")
                return
        except Exception as e:
            logger.warning(f"Could not load existing KB: {e}")
        
        # Create new vectorstore from documents
        logger.info("📚 Building knowledge base from documents...")
        self._build_vectorstore()
    
    def _build_vectorstore(self):
        """Build vectorstore from knowledge documents"""
        docs_to_store = []
        
        for kb_doc in KNOWLEDGE_DOCUMENTS:
            # Split each document into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            chunks = text_splitter.split_text(kb_doc.content)
            
            for i, chunk in enumerate(chunks):
                metadata = {
                    "doc_id": kb_doc.id,
                    "title": kb_doc.title,
                    "category": kb_doc.category,
                    "chunk": i,
                    **kb_doc.metadata
                }
                doc = Document(page_content=chunk, metadata=metadata)
                docs_to_store.append(doc)
        
        if docs_to_store:
            self.vectorstore = Chroma.from_documents(
                documents=docs_to_store,
                embedding=self.embeddings,
                persist_directory=self.path,
                collection_name="triage_kb"
            )
            self.vectorstore.persist()
            logger.info(f"✅ Built knowledge base with {len(docs_to_store)} chunks")
    
    def retrieve(self, query: str, k: int = RETRIEVER_K, category: Optional[str] = None) -> List[RetrievalResult]:
        """Retrieve relevant documents from knowledge base"""
        cache_key = hashlib.md5(f"{query}_{k}_{category}".encode()).hexdigest()
        
        if cache_key in self.query_cache:
            return self.query_cache[cache_key]
        
        try:
            if not self.vectorstore:
                logger.warning("Knowledge base not initialized")
                return []
            
            # Build filter if category specified
            filter_dict = None
            if category:
                filter_dict = {"category": category}
            
            # Similarity search
            docs = self.vectorstore.similarity_search_with_score(
                query,
                k=k,
                filter=filter_dict
            )
            
            results = [
                RetrievalResult(
                    content=doc.page_content,
                    score=score,
                    metadata=doc.metadata,
                    source=doc.metadata.get("title", "Unknown")
                )
                for doc, score in docs
            ]
            
            self.query_cache[cache_key] = results
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            return []
    
    def retrieve_by_category(self, category: str, limit: int = 10) -> List[RetrievalResult]:
        """Retrieve all documents in a category"""
        try:
            if not self.vectorstore:
                return []
            
            docs = self.vectorstore.get(
                where={"category": category},
                limit=limit
            )
            
            results = [
                RetrievalResult(
                    content=doc["documents"][i],
                    score=1.0,
                    metadata=doc["metadatas"][i],
                    source=doc["metadatas"][i].get("title", "Unknown")
                )
                for i, doc in enumerate(docs.get("documents", []))
            ]
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving by category: {e}")
            return []
    
    def get_recommendation_context(self, diagnoses: List[Dict[str, Any]], symptoms: List[str]) -> str:
        """Get contextual recommendations based on diagnoses"""
        context_parts = []
        
        # Get service type guidance
        for diagnosis in diagnoses[:3]:  # Top 3 diagnoses
            cond_name = diagnosis.get("name", "")
            results = self.retrieve(cond_name, k=1, category="conditions")
            if results:
                context_parts.append(results[0].content)
        
        # Get symptom-specific guidance
        for symptom in symptoms[:3]:
            results = self.retrieve(symptom, k=1, category="symptoms")
            if results:
                context_parts.append(results[0].content)
        
        return "\n\n".join(context_parts)
    
    def answer_question(self, question: str, context: Optional[str] = None) -> str:
        """Answer a question using the knowledge base"""
        from groq import Groq
        
        # Retrieve relevant documents
        results = self.retrieve(question, k=RETRIEVER_K)
        
        if not results:
            return "I couldn't find relevant information in the knowledge base. Please consult a healthcare professional."
        
        kb_context = "\n\n".join([r.content for r in results[:3]])
        
        # Build prompt
        system_prompt = """You are a medical triage assistant with access to a knowledge base.
Answer questions based on the provided knowledge base content.
Be accurate, safe, and recommend professional care when appropriate.
Always encourage consulting healthcare professionals for serious concerns.
Format: Clear, concise, actionable information."""
        
        if context:
            user_message = f"Knowledge Base Content:\n{kb_context}\n\nPatient Context:\n{context}\n\nQuestion: {question}"
        else:
            user_message = f"Knowledge Base Content:\n{kb_context}\n\nQuestion: {question}"
        
        try:
            client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return "Unable to generate response. Please consult a healthcare professional."
    
    def is_emergency(self, user_input: str) -> Tuple[bool, Optional[str]]:
        """Check if input contains emergency indicators"""
        emergency_keywords = [
            "chest pain", "difficulty breathing", "shortness of breath",
            "unconscious", "stroke", "severe bleeding", "poisoning",
            "overdose", "allergic reaction", "anaphylaxis", "severe headache",
            "call ambulance", "emergency", "911", "suicidal", "homicidal",
            "cannot breathe", "choking"
        ]
        
        input_lower = user_input.lower()
        for keyword in emergency_keywords:
            if keyword in input_lower:
                results = self.retrieve("emergency red flags", k=1, category="triage_guidance")
                if results:
                    return True, results[0].content
                return True, "EMERGENCY DETECTED - Seek immediate medical care!"
        
        return False, None
    
    def get_care_path(self, symptoms: List[str]) -> Optional[str]:
        """Get triage care path for symptoms"""
        # Map symptoms to care paths
        if any(s in "cough sore throat shortness of breath" for s in " ".join(symptoms).lower()):
            results = self.retrieve("respiratory triage path", k=1, category="care_paths")
            if results:
                return results[0].content
        
        if any(s in "fever temperature" for s in " ".join(symptoms).lower()):
            results = self.retrieve("fever triage path", k=1, category="care_paths")
            if results:
                return results[0].content
        
        return None


# ============================================================
# GLOBAL INSTANCE
# ============================================================
_kb_instance: Optional[TriageKnowledgeBase] = None

def get_knowledge_base() -> TriageKnowledgeBase:
    """Get or initialize global knowledge base instance"""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = TriageKnowledgeBase()
    return _kb_instance
