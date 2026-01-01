import json
import os
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import hashlib
from datetime import datetime

class MedicalKBVectorStore:
    def __init__(self, persist_directory: str = "medical_kb_vectorstore"):
        """
        Initialize ChromaDB vector store for medical knowledge base
        
        Args:
            persist_directory: Directory to persist the vector database
        """
        self.persist_directory = persist_directory
        
        # Initialize embedding model
        print("🔍 Loading embedding model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize ChromaDB client
        print("📚 Initializing ChromaDB...")
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Create or get collection
        self.collection = self.client.get_or_create_collection(
            name="medical_knowledge_base",
            metadata={"description": "Medical emergency and first aid knowledge base"}
        )
        
        print(f"✅ Medical KB Vector Store initialized at: {persist_directory}")
    
    def _create_document_id(self, condition: str, section: str = None) -> str:
        """Create unique document ID"""
        base = f"{condition}_{section}" if section else condition
        return hashlib.md5(base.encode()).hexdigest()[:16]
    
    def _flatten_condition_data(self, condition_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Flatten a condition into multiple documents for better retrieval
        
        Returns list of documents with:
        - Main document (overview)
        - Section documents (symptoms, first aid, etc.)
        """
        documents = []
        condition_name = condition_data.get("condition_name", "Unknown Condition")
        
        # Use .get() with default values to handle missing keys
        category = condition_data.get("category", "uncategorized")
        description = condition_data.get("description", "No description available")
        
        # Handle lists with defaults
        causes = condition_data.get("causes", ["Unknown causes"])
        risk_factors = condition_data.get("risk_factors", ["Unknown risk factors"])
        prevention = condition_data.get("prevention", ["No prevention information"])
        references = condition_data.get("references", ["No references"])
        
        # Handle nested symptoms structure
        symptoms_data = condition_data.get("symptoms", {})
        common_symptoms = symptoms_data.get("common", ["No common symptoms listed"])
        danger_signs = symptoms_data.get("danger_signs", ["No danger signs listed"])
        
        # Handle first aid and related fields
        first_aid_steps = condition_data.get("first_aid_steps", ["No first aid steps available"])
        what_not_to_do = condition_data.get("what_not_to_do", ["No specific don'ts listed"])
        when_to_call_emergency = condition_data.get("when_to_call_emergency", ["Seek medical help if symptoms worsen"])
        
        # 1. Create main overview document
        overview_text = f"""
        Condition: {condition_name}
        Category: {category}
        Description: {description}
        
        Causes: {', '.join(causes) if isinstance(causes, list) else causes}
        Risk Factors: {', '.join(risk_factors) if isinstance(risk_factors, list) else risk_factors}
        
        Common Symptoms: {', '.join(common_symptoms) if isinstance(common_symptoms, list) else common_symptoms}
        Danger Signs: {', '.join(danger_signs) if isinstance(danger_signs, list) else danger_signs}
        
        Key Prevention: {', '.join(prevention) if isinstance(prevention, list) else prevention}
        References: {', '.join(references) if isinstance(references, list) else references}
        """
        
        documents.append({
            "id": self._create_document_id(condition_name, "overview"),
            "condition": condition_name,
            "text": overview_text,
            "metadata": {
                "condition": condition_name,
                "category": category,
                "document_type": "overview",
                "has_symptoms": len(common_symptoms) > 0 or len(danger_signs) > 0,
                "has_first_aid": len(first_aid_steps) > 0,
                "danger_signs_count": len(danger_signs),
                "common_symptoms_count": len(common_symptoms),
                "first_aid_steps_count": len(first_aid_steps),
                "created_at": datetime.now().isoformat()
            }
        })
        
        # 2. Symptoms document (separate for better symptom-based retrieval)
        symptoms_text = f"""
        Condition: {condition_name}
        
        Common Symptoms:
        {chr(10).join(['• ' + s for s in common_symptoms])}
        
        Danger Signs (Emergency Indicators):
        {chr(10).join(['⚠️ ' + s for s in danger_signs])}
        """
        
        documents.append({
            "id": self._create_document_id(condition_name, "symptoms"),
            "condition": condition_name,
            "text": symptoms_text,
            "metadata": {
                "condition": condition_name,
                "category": category,
                "document_type": "symptoms",
                "symptom_count": len(common_symptoms) + len(danger_signs),
                "emergency_indicators": len(danger_signs),
                "tags": "symptoms,clinical_signs,emergency_indicators"
            }
        })
        
        # 3. First Aid Steps document
        first_aid_text = f"""
        Condition: {condition_name}
        
        First Aid Steps:
        {chr(10).join([f'{i+1}. ' + s for i, s in enumerate(first_aid_steps)])}
        
        What NOT to Do:
        {chr(10).join(['✗ ' + s for s in what_not_to_do])}
            
        When to Call Emergency:
        {chr(10).join(['🚨 ' + s for s in when_to_call_emergency])}
        """
        
        documents.append({
            "id": self._create_document_id(condition_name, "first_aid"),
            "condition": condition_name,
            "text": first_aid_text,
            "metadata": {
                "condition": condition_name,
                "category": category,
                "document_type": "first_aid",
                "first_aid_steps_count": len(first_aid_steps),
                "emergency_triggers_count": len(when_to_call_emergency),
                "avoid_actions_count": len(what_not_to_do),
                "tags": "first_aid,emergency_response,treatment_guidelines"
            }
        })
        
        # 4. Causes & Prevention document
        causes_prevention_text = f"""
        Condition: {condition_name}
        
        Causes:
        {chr(10).join(['• ' + s for s in causes])}
        
        Risk Factors:
        {chr(10).join(['• ' + s for s in risk_factors])}
        
        Prevention Measures:
        {chr(10).join(['✓ ' + s for s in prevention])}
        """
        
        documents.append({
            "id": self._create_document_id(condition_name, "causes_prevention"),
            "condition": condition_name,
            "text": causes_prevention_text,
            "metadata": {
                "condition": condition_name,
                "category": category,
                "document_type": "causes_prevention",
                "causes_count": len(causes),
                "risk_factors_count": len(risk_factors),
                "prevention_measures_count": len(prevention),
                "tags": "etiology,risk_factors,prevention"
            }
        })
        
        return documents
    
    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts"""
        print(f"🤖 Generating embeddings for {len(texts)} texts...")
        embeddings = self.embedding_model.encode(
            texts, 
            normalize_embeddings=True,
            show_progress_bar=True
        )
        return embeddings.tolist()
    
    def store_conditions(self, conditions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Store medical conditions in vector database
        
        Args:
            conditions_data: List of condition dictionaries from your KB
            
        Returns:
            Dictionary with statistics about stored data
        """
        print(f"📥 Processing {len(conditions_data)} medical conditions...")
        
        all_documents = []
        all_metadatas = []
        all_ids = []
        
        # Process each condition
        for condition in conditions_data:
            condition_name = condition.get("condition_name", "Unknown")
            print(f"  Processing: {condition_name}")
            
            try:
                # Flatten condition into multiple documents
                condition_docs = self._flatten_condition_data(condition)
                
                for doc in condition_docs:
                    all_documents.append(doc["text"])
                    all_metadatas.append(doc["metadata"])
                    all_ids.append(doc["id"])
            except Exception as e:
                print(f"  ⚠️ Error processing {condition_name}: {e}")
                # Skip this condition if there's an error
                continue
        
        print(f"📝 Total documents to store: {len(all_documents)}")
        
        # If no documents were successfully processed
        if len(all_documents) == 0:
            print("❌ No documents to store. Exiting.")
            return {"error": "No documents processed"}
        
        # Generate embeddings in batches (to avoid memory issues)
        batch_size = 100
        total_batches = (len(all_documents) + batch_size - 1) // batch_size
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, len(all_documents))
            
            batch_docs = all_documents[start_idx:end_idx]
            batch_metadatas = all_metadatas[start_idx:end_idx]
            batch_ids = all_ids[start_idx:end_idx]
            
            print(f"🔧 Processing batch {batch_idx + 1}/{total_batches} ({len(batch_docs)} documents)")
            
            try:
                # Generate embeddings for this batch
                batch_embeddings = self._generate_embeddings(batch_docs)
                
                # Add to collection
                self.collection.add(
                    embeddings=batch_embeddings,
                    documents=batch_docs,
                    metadatas=batch_metadatas,
                    ids=batch_ids
                )
                
                print(f"✅ Batch {batch_idx + 1} stored successfully")
            except Exception as e:
                print(f"  ⚠️ Error storing batch {batch_idx + 1}: {e}")
                # Continue with next batch even if this one fails
                continue
        
        # Create statistics
        successful_conditions = len(set([meta.get("condition", "") for meta in all_metadatas])) - 1  # Subtract 1 for "Unknown"
        categories = list(set([meta.get("category", "") for meta in all_metadatas if meta.get("category")]))
        
        stats = {
            "total_conditions": successful_conditions,
            "total_documents": len(all_documents),
            "document_types": {
                "overview": len([d for d in all_documents if "Overview" in d[:100]]),
                "symptoms": len([d for d in all_documents if "Common Symptoms" in d[:100]]),
                "first_aid": len([d for d in all_documents if "First Aid Steps" in d[:100]]),
                "causes_prevention": len([d for d in all_documents if "Causes:" in d[:100]])
            },
            "categories": categories,
            "conditions_count_by_category": {},
            "stored_at": datetime.now().isoformat()
        }
        
        # Count conditions by category
        for metadata in all_metadatas:
            category = metadata.get("category", "unknown")
            if category != "unknown":
                stats["conditions_count_by_category"][category] = \
                    stats["conditions_count_by_category"].get(category, 0) + 1
        
        print(f"\n🎉 Medical Knowledge Base stored successfully!")
        print(f"   Conditions: {stats['total_conditions']}")
        print(f"   Total documents: {stats['total_documents']}")
        print(f"   Categories: {', '.join(stats['categories'])}")
        
        return stats
    
    def search(self, query: str, n_results: int = 5, filter_metadata: Dict = None) -> Dict[str, Any]:
        """
        Search the medical knowledge base
        
        Args:
            query: Search query
            n_results: Number of results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            Search results with documents and metadata
        """
        # Generate query embedding
        query_embedding = self.embedding_model.encode(
            query, 
            normalize_embeddings=True
        ).tolist()
        
        # Search in collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format results
        formatted_results = []
        if results["documents"]:
            for i in range(len(results["documents"][0])):
                formatted_results.append({
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                    "score": 1 - results["distances"][0][i]  # Convert distance to similarity score
                })
        
        return {
            "query": query,
            "results": formatted_results,
            "total_results": len(formatted_results)
        }
    
    def get_condition_info(self, condition_name: str) -> Dict[str, Any]:
        """
        Get all information about a specific condition
        
        Args:
            condition_name: Name of the condition
            
        Returns:
            Combined information from all document types for the condition
        """
        # Search for all documents related to this condition
        results = self.collection.query(
            query_texts=condition_name,
            n_results=10,
            where={"condition": condition_name},
            include=["documents", "metadatas"]
        )
        
        if not results["documents"]:
            return {"error": f"Condition '{condition_name}' not found"}
        
        # Organize by document type
        organized_data = {
            "condition": condition_name,
            "overview": None,
            "symptoms": None,
            "first_aid": None,
            "causes_prevention": None
        }
        
        for i, metadata in enumerate(results["metadatas"][0]):
            doc_type = metadata.get("document_type", "unknown")
            if doc_type in organized_data:
                organized_data[doc_type] = {
                    "text": results["documents"][0][i],
                    "metadata": metadata
                }
        
        return organized_data
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection"""
        count = self.collection.count()
        
        # Get unique conditions
        all_metadatas = self.collection.get(include=["metadatas"])
        conditions = set()
        categories = set()
        
        for metadata in all_metadatas["metadatas"]:
            if metadata and "condition" in metadata:
                conditions.add(metadata["condition"])
            if metadata and "category" in metadata:
                categories.add(metadata["category"])
        
        return {
            "total_documents": count,
            "unique_conditions": len(conditions),
            "unique_categories": len(categories),
            "categories": list(categories),
            "sample_conditions": list(conditions)[:10] if conditions else []
        }

def load_medical_kb_from_file(file_path: str = "medical_knowledge_base.json") -> List[Dict]:
    """
    Load medical knowledge base from JSON file
    
    Args:
        file_path: Path to JSON file containing medical KB
        
    Returns:
        List of medical condition dictionaries
    """
    try:
        # Ensure the file path is properly formatted
        file_path = os.path.normpath(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📖 Loaded {len(data)} conditions from {file_path}")
        return data
        
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        print("Using the provided KB data from your code...")
        
        # Return your provided KB data
        return [
            {
                "condition_name": "Asthma attack",
                "category": "clinical/breathing",
                "description": "Acute narrowing of the airways causing difficulty breathing, triggered by allergens, infection, exercise, or irritants.",
                "causes": [
                    "Respiratory infections",
                    "Allergens (dust, pollen, animals)",
                    "Exercise",
                    "Cold air or smoke exposure"
                ],
                "risk_factors": [
                    "History of asthma",
                    "Previous severe attacks",
                    "Exposure to triggers (smoke, allergens)"
                ],
                "symptoms": {
                    "common": [
                        "Shortness of breath",
                        "Wheezing",
                        "Coughing",
                        "Tight chest"
                    ],
                    "danger_signs": [
                        "Difficulty speaking full sentences",
                        "Very fast breathing",
                        "Blue lips or nails",
                        "Silent chest (no air movement)"
                    ]
                },
                "first_aid_steps": [
                    "Help the person sit upright and stay calm.",
                    "Encourage slow, steady breathing.",
                    "Use their prescribed inhaler if available (e.g., salbutamol).",
                    "Loosen tight clothing.",
                    "Monitor breathing while waiting for improvement.",
                    "Call emergency medical services if danger signs appear or symptoms worsen."
                ],
                "what_not_to_do": [
                    "Do not make the person lie down.",
                    "Do not force deep breathing if it worsens symptoms.",
                    "Do not delay calling for help in severe cases."
                ],
                "when_to_call_emergency": [
                    "No improvement after using rescue inhaler.",
                    "Severe breathing difficulty or blue lips.",
                    "Unable to speak in full sentences."
                ],
                "prevention": [
                    "Avoid known triggers.",
                    "Use preventive inhalers as prescribed.",
                    "Carry a rescue inhaler at all times."
                ],
                "references": [
                    "WHO Basic Emergency Care – Breathing difficulties",
                    "IFRC First Aid Guidelines 2020 – Asthma"
                ]
            }
        ]

def save_medical_kb_to_file(conditions: List[Dict], file_path: str = "main_kb_v2.json"):
    """Save medical knowledge base to JSON file"""
    # Ensure the file path is properly formatted
    file_path = os.path.normpath(file_path)
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(conditions, f, indent=2, ensure_ascii=False)
    print(f"💾 Saved {len(conditions)} conditions to {file_path}")

def main():
    """Main function to store medical KB in vector database"""
    
    # FIXED: Use the correct file path
    VECTOR_STORE_PATH = r"C:\Users\Rahma\Desktop\f\Sahhatek\agents\medical_agent\chroma_db"
    KB_FILE_PATH = r"C:\Users\Rahma\Desktop\f\Sahhatek\agents\medical_agent\main_kb_v2 copy.json"  # Fixed file name
    
    print("🏥 Medical Knowledge Base Vector Store Setup")
    print("=" * 50)
    
    # Step 1: Load medical KB
    print("\n1️⃣ Loading Medical Knowledge Base...")
    medical_kb = load_medical_kb_from_file(KB_FILE_PATH)
    
    if not medical_kb:
        print("❌ No medical KB data found. Exiting.")
        return
    
    # Step 2: Initialize vector store
    print("\n2️⃣ Initializing Vector Store...")
    
    # Create directory for vector store if it doesn't exist
    os.makedirs(VECTOR_STORE_PATH, exist_ok=True)
    
    vector_store = MedicalKBVectorStore(persist_directory=VECTOR_STORE_PATH)
    
    # Step 3: Store conditions in vector database
    print("\n3️⃣ Storing Conditions in Vector Database...")
    stats = vector_store.store_conditions(medical_kb)
    
    # Step 4: Test retrieval
    print("\n4️⃣ Testing Retrieval...")
    
    # Test queries
    test_queries = [
        "asthma symptoms",
        "chest pain emergency",
        "first aid for burns",
        "difficulty breathing",
        "child fever danger signs"
    ]
    
    for query in test_queries:
        print(f"\n🔎 Testing query: '{query}'")
        results = vector_store.search(query, n_results=3)
        
        if results["results"]:
            for i, result in enumerate(results["results"][:2]):
                print(f"  Result {i+1}: {result['metadata']['condition']} ({result['metadata']['document_type']})")
                print(f"  Score: {result['score']:.3f}")
                # Show first 100 chars of document
                preview = result['document'][:100].replace('\n', ' ')
                print(f"  Preview: {preview}...")
                print()
    
    # Step 5: Get collection statistics
    print("\n5️⃣ Collection Statistics:")
    collection_stats = vector_store.get_collection_stats()
    print(f"   Total documents: {collection_stats['total_documents']}")
    print(f"   Unique conditions: {collection_stats['unique_conditions']}")
    print(f"   Categories: {', '.join(collection_stats['categories'])}")
    
    # Step 6: Save the original KB to file (if it wasn't already saved)
    if not os.path.exists(KB_FILE_PATH):
        save_medical_kb_to_file(medical_kb, KB_FILE_PATH)
    
    print("\n" + "=" * 50)
    print("✅ Medical Knowledge Base Vector Store setup complete!")
    print(f"   Vector store location: {VECTOR_STORE_PATH}")
    print(f"   Knowledge base file: {KB_FILE_PATH}")
    print("\n📚 You can now use this vector store with your medical agent.")

if __name__ == "__main__":
    main()