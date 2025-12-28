import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import Conversation, Message
from users.models import UserProfile
from django.views.decorators.http import require_GET
from django.utils import timezone
import os
import datetime

def home(request):
    return render(request, 'home.html')

@login_required
def chat(request):
    """Render chat page with user profile context"""
    try:
        profile = UserProfile.objects.get(user=request.user)
        profile_complete = profile.is_complete
    except UserProfile.DoesNotExist:
        profile_complete = False
    
    return render(request, 'chat.html', {
        'user': request.user,
        'profile_complete': profile_complete
    })

# ------------------------------------------------------------------
# API Endpoints (UNIFIED - accessible via /api/)
# ------------------------------------------------------------------

@login_required
def get_conversations(request):
    """List all active conversations for the current user."""
    conversations = Conversation.objects.filter(user=request.user, is_deleted=False).order_by('-is_pinned', '-created_at')
    data = []
    for c in conversations:
        last_msg = c.messages.filter(is_deleted=False).order_by('-created_at').first()
        preview = last_msg.content[:60] if last_msg else "No messages yet"
        data.append({
            "id": c.id,
            "title": c.title,
            "preview": preview,
            "is_pinned": c.is_pinned,
            "created_at": c.created_at.isoformat(),
            "message_count": c.messages.filter(is_deleted=False).count()
        })
    return JsonResponse({"conversations": data})

@csrf_exempt
@login_required
def update_conversation(request, conversation_id):
    """Update conversation title or pin status."""
    if request.method == "POST":
        conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user, is_deleted=False)
        try:
            data = json.loads(request.body)
        except:
            return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)
        
        if 'title' in data:
            conversation.title = data['title']
        
        if 'is_pinned' in data:
            conversation.is_pinned = bool(data['is_pinned'])
            
        conversation.save()

        return JsonResponse({
            "success": True,
            "conversation": {
                "id": conversation.id,
                "title": conversation.title,
                "is_pinned": conversation.is_pinned
            }
        })
    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)

@csrf_exempt
@login_required
def create_conversation(request):
    """Create a new conversation."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except:
            return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)
        
        title = data.get("title", "New conversation")
        conversation = Conversation.objects.create(user=request.user, title=title)
        
        return JsonResponse({
            "success": True,
            "conversation": {
                "id": conversation.id,
                "title": conversation.title,
                "created_at": conversation.created_at.isoformat(),
                "is_pinned": conversation.is_pinned
            }
        })
    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)

@csrf_exempt
@login_required
def delete_conversation(request, conversation_id):
    """Soft delete a conversation."""
    if request.method == "POST":
        conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
        conversation.is_deleted = True
        conversation.save()
        return JsonResponse({"success": True, "message": "Conversation deleted"})
    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)

@login_required
def get_messages(request, conversation_id):
    """Get all active messages for a specific conversation."""
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    messages = conversation.messages.filter(is_deleted=False).order_by('created_at')
    
    data = []
    for m in messages:
        msg_data = {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat()
        }
        
        # Try to extract metadata if stored
        if hasattr(m, 'metadata') and m.metadata:
            try:
                if isinstance(m.metadata, str):
                    msg_data["metadata"] = json.loads(m.metadata)
                else:
                    msg_data["metadata"] = m.metadata
            except:
                pass
                
        data.append(msg_data)
    
    return JsonResponse({"messages": data})

# ============================================================
# Enhanced add_message with LangGraph Integration
# ============================================================
@csrf_exempt
@login_required
def add_message(request, conversation_id):
    """
    Add a message and get response from LangGraph agents.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"}, status=400)
    
    try:
        # Parse request data
        try:
            data = json.loads(request.body)
        except:
            return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)
        
        role = data.get("role")
        content = data.get("content")
        latitude = data.get("latitude")  # Extract location from request
        longitude = data.get("longitude")
        
        if role not in ['user', 'assistant'] or not content:
            return JsonResponse({"success": False, "message": "Invalid data"}, status=400)
        
        # Handle new conversation
        if str(conversation_id).lower() == 'new':
            title = content[:30] + "..." if len(content) > 30 else content
            conversation = Conversation.objects.create(user=request.user, title=title)
            conversation_id = conversation.id
        else:
            conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
        
        # Save user message with location metadata if available
        message_metadata = {}
        if latitude is not None and longitude is not None:
            message_metadata = {"latitude": latitude, "longitude": longitude}
        
        user_message = Message.objects.create(
            conversation=conversation, 
            role=role, 
            content=content,
            metadata=message_metadata if message_metadata else None
        )
        
        # Get user profile for medical context
        try:
            profile = UserProfile.objects.get(user=request.user)
            user_context = {
                "gender": profile.gender,
                "age": profile.age,
                "chronic_diseases": profile.chronic_diseases,
                "blood_type": profile.blood_type,
                "allergies": profile.allergies,
                "medications": profile.medications,
                "profile_complete": profile.is_complete
            }
        except UserProfile.DoesNotExist:
            user_context = {}
        
        # Try to import and run LangGraph
        bot_content = ""
        metadata = {}
        
        try:
            # Import LangGraph app - FIX THIS PATH based on your actual structure
            # Option 1: If your graph is in agents/graph/
            try:
                from agents.graph.build_graph import app
                print("✅ Imported LangGraph from agents.graph.build_graph")
            except ImportError:
                # Option 2: If your graph is in the root graph/
                try:
                    from graph.build_graph import app
                    print("✅ Imported LangGraph from graph.build_graph")
                except ImportError:
                    # Option 3: Create a simple fallback graph
                    print("⚠️ LangGraph not found, creating fallback")
                    from langgraph.graph import StateGraph, END
                    from typing import TypedDict, List
                    
                    class AgentState(TypedDict):
                        user_input: str
                        messages: List[dict]
                        current_agent: str
                        next_agent: str
                        agent_output: str
                        metadata: dict
                    
                    workflow = StateGraph(AgentState)
                    workflow.add_node("gatekeeper", lambda state: {
                        **state,
                        "current_agent": "gatekeeper",
                        "agent_output": f"I'm the gatekeeper. I received: {state['user_input']}",
                        "metadata": {"processed_by": "fallback_gatekeeper"}
                    })
                    workflow.set_entry_point("gatekeeper")
                    workflow.add_edge("gatekeeper", END)
                    app = workflow.compile()
            
        # Get conversation history
            recent_messages = conversation.messages.filter(
                is_deleted=False
            ).order_by('-created_at')[:10]  # Get more messages for context
            
            messages_history = []
            session_id = None
            diagnosis_session_id = None
            pending_questions_from_history = []
            last_symptoms_from_history = []
            last_negative_symptoms_from_history = []
            # recent_messages is ordered by '-created_at' => MOST RECENT first
            for msg in recent_messages:
                # Include metadata in message history so triage agent can find session_id and pending_questions
                msg_dict = {
                    "role": msg.role,
                    "content": msg.content
                }
                # Add metadata if available
                if msg.metadata:
                    try:
                        if isinstance(msg.metadata, dict):
                            msg_dict["metadata"] = msg.metadata
                        elif isinstance(msg.metadata, str):
                            msg_dict["metadata"] = json.loads(msg.metadata)
                    except:
                        pass
                messages_history.append(msg_dict)
                # Extract session_id and pending_questions from assistant messages if available
                if msg.role == 'assistant':
                    try:
                        # Handle both dict and JSON string metadata
                        if isinstance(msg.metadata, dict):
                            msg_metadata = msg.metadata
                        elif isinstance(msg.metadata, str) and msg.metadata:
                            msg_metadata = json.loads(msg.metadata)
                        else:
                            msg_metadata = {}
                        
                        # Get session_id from ANY assistant message (keep the most recent one found)
                        found_session_id = msg_metadata.get("session_id")
                        if found_session_id:
                            session_id = found_session_id
                        
                        # Get diagnosis_session_id from MOST RECENT assistant message (first in reversed order)
                        found_diagnosis_session_id = msg_metadata.get("diagnosis_session_id")
                        if found_diagnosis_session_id and not diagnosis_session_id:
                            diagnosis_session_id = found_diagnosis_session_id
                            print(f"📋 Found diagnosis_session_id from most recent assistant message: {diagnosis_session_id}")
                        
                        # Keep last known symptoms so yes/no answers don't lose context
                        if not last_symptoms_from_history:
                            last_symptoms_from_history = msg_metadata.get("symptoms", []) or []
                        if not last_negative_symptoms_from_history:
                            last_negative_symptoms_from_history = msg_metadata.get("negative_symptoms", []) or []

                        # Get pending_questions from MOST RECENT assistant message (first in reversed order)
                        # This should be the question that was just asked
                        msg_pending = msg_metadata.get("pending_questions", [])
                        if msg_pending and not pending_questions_from_history:
                            pending_questions_from_history = msg_pending
                            print(f"📋 Found pending question from most recent assistant message: {msg_pending[0] if msg_pending else 'None'}")
                        
                        # If we found both diagnosis_session_id and pending_questions from the same message, we're done
                        if diagnosis_session_id and pending_questions_from_history:
                            break
                    except Exception as e:
                        print(f"⚠️ Error parsing message metadata: {e}")
                        import traceback
                        traceback.print_exc()
                        pass
            
            print(
                f"📋 Extracted from history - session_id: {session_id}, diagnosis_session_id: {diagnosis_session_id}, "
                f"pending_questions: {len(pending_questions_from_history)}, "
                f"symptoms: {len(last_symptoms_from_history)}, negative_symptoms: {len(last_negative_symptoms_from_history)}"
            )
            
            # Extract location from request or previous messages
            user_location = None
            if latitude is not None and longitude is not None:
                user_location = (float(latitude), float(longitude))
                print(f"📍 Location from request: ({latitude}, {longitude})")
            else:
                # Try to find location in previous messages
                for msg in reversed(recent_messages):
                    if msg.role == 'user' and msg.metadata:
                        try:
                            msg_meta = msg.metadata if isinstance(msg.metadata, dict) else json.loads(msg.metadata)
                            if 'latitude' in msg_meta and 'longitude' in msg_meta:
                                user_location = (float(msg_meta['latitude']), float(msg_meta['longitude']))
                                print(f"📍 Location from previous message: ({msg_meta['latitude']}, {msg_meta['longitude']})")
                                break
                        except:
                            pass
            
            if not user_location:
                print("⚠️ No location found in request or previous messages")
            
            # Note: diagnosis_session_id is now extracted above along with pending_questions in the first loop
            
            # Prepare LangGraph state with multi-turn support
            langgraph_state = {
                "user_input": content,
                "messages": messages_history,
                "current_agent": None,
                "next_agent": None,
                "agent_output": None,
                "user_location": user_location,  # Add location to state
                "user_input_location": None,  # For text-based location input
                "pending_questions": pending_questions_from_history,  # Pass pending questions
                "diagnosis_session_id": diagnosis_session_id,  # Pass diagnosis session from history
                "symptoms": last_symptoms_from_history,
                "negative_symptoms": last_negative_symptoms_from_history,
                "metadata": {
                    "conversation_id": conversation_id,
                    "user_id": request.user.id,
                    "user_context": user_context,
                },
                "session_id": session_id,  # Preserve session for multi-turn
                "diagnosis_complete": False,
            }
            
            if user_location:
                print(f"✅ Location added to LangGraph state: {user_location}")
            else:
                print("⚠️ No location in LangGraph state")
            
            print(f"🚀 Invoking LangGraph for conversation {conversation_id}...")
            result = app.invoke(langgraph_state)
            
            # Extract response
            bot_content = result.get("agent_output", "I apologize, but I couldn't generate a response.")
            current_agent = result.get("current_agent", "unknown")
            
            # Handle multi-turn triage questions
            # Note: The triage agent now includes questions in agent_output, so we don't need to append them here
            # But we still extract pending_questions for metadata
            pending_questions = result.get("pending_questions", [])
            
            # Build metadata
            session_id = result.get("session_id") or langgraph_state.get("session_id")
            diagnosis_session_id = result.get("diagnosis_session_id") or langgraph_state.get("diagnosis_session_id")
            metadata = {
                "agent_used": current_agent,
                "was_handled_by_gatekeeper": result.get("gatekeeper_decision", {}).get("should_route", True) == False,
                "gatekeeper_decision": result.get("gatekeeper_decision", {}),
                "langgraph_state": {
                    "intent": result.get("intent"),
                    "emergency_level": result.get("emergency_level"),
                    "confidence": result.get("confidence_score", 0.0)
                },
                "user_context_present": bool(user_context),
                "profile_complete": user_context.get("profile_complete", False) if user_context else False,
                "pending_questions": pending_questions,
                "diagnosis_session_id": diagnosis_session_id,  # Save diagnosis session
                "diagnosis_complete": result.get("diagnosis_complete", False),
                "session_id": session_id,  # Ensure session_id is saved
                "symptoms": result.get("symptoms", []),
                "negative_symptoms": result.get("negative_symptoms", []),
                "diagnoses": result.get("diagnoses", []),
                "healthcare_recommendation": result.get("healthcare_recommendation", {}),
                # Format recommendation for frontend (from orientation node)
                "recommendation": {
                    "service_type": result.get("service_type", ""),
                    "immediate_care": result.get("immediate_care", False),
                    "places": result.get("places", result.get("nearby_facilities", [])),  # Use places or fallback to nearby_facilities
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude")
                } if (result.get("places") or result.get("nearby_facilities") or result.get("latitude") or result.get("longitude")) else None
            }
            
            # Add language info if available
            if result.get("metadata", {}).get("gatekeeper_agent"):
                gatekeeper_info = result["metadata"]["gatekeeper_agent"]
                metadata["language_info"] = {
                    "detected": gatekeeper_info.get("detected_language"),
                    "normalized": gatekeeper_info.get("normalized_language"),
                    "translation_used": gatekeeper_info.get("translation_used", False)
                }
            
            print(f"✅ LangGraph completed. Agent: {current_agent}")
            
        except Exception as e:
            print(f"❌ LangGraph error: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback response
            bot_content = f"I received your message: '{content}'. I'm currently experiencing technical difficulties with my advanced processing. Profile data available: {bool(user_context)}"
            metadata = {
                "agent_used": "fallback",
                "error": str(e),
                "user_context_present": bool(user_context)
            }
        
        # Save bot response
        bot_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=bot_content,
            metadata=metadata  # Store as dict directly (JSONField handles serialization)
        )
        
        print(f"✅ Bot message saved with metadata")
        
        return JsonResponse({
            "success": True,
            "conversation_id": conversation.id,
            "bot_message": {
                "id": bot_message.id,
                "role": bot_message.role,
                "content": bot_message.content,
                "metadata": metadata
            }
        })
        
    except Exception as e:
        print(f"❌ Critical error in add_message: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            "success": False, 
            "message": f"Internal server error: {str(e)}"
        }, status=500)

@csrf_exempt
@login_required
def new_conversation_message(request):
    """Handle messages for new conversations"""
    return add_message(request, 'new')

@csrf_exempt
@login_required
def delete_message(request, message_id):
    """Soft delete a specific message."""
    if request.method == "POST":
        message = get_object_or_404(Message, id=message_id, conversation__user=request.user)
        message.is_deleted = True
        message.save()
        return JsonResponse({"success": True, "message": "Message deleted"})
    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)

# ============================================================
# Streaming Audio Processing (Real-time)
# ============================================================
# Module-level dictionary to store transcriber sessions
# Key: session_id, Value: StreamingTranscriber instance
_transcriber_sessions = {}
import threading
import time

def _cleanup_old_sessions():
    """Clean up transcriber sessions older than 5 minutes (background task)"""
    # This is a simple cleanup - in production, use a proper task queue
    pass

# Start cleanup thread (optional, for production)
# threading.Thread(target=_cleanup_old_sessions, daemon=True).start()

@csrf_exempt
@login_required
def stream_audio_chunk(request, conversation_id):
    """
    Process a single audio chunk in real-time and return partial transcription.
    This endpoint is called repeatedly during recording for real-time transcription.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"}, status=400)
    
    try:
        data = json.loads(request.body)
        audio_chunk_base64 = data.get("audio_chunk")
        audio_format = data.get("audio_format", "webm")
        chunk_index = data.get("chunk_index", 0)
        is_final = data.get("is_final", False)
        session_id = data.get("session_id")  # For maintaining transcriber state
        
        if not audio_chunk_base64:
            return JsonResponse({"success": False, "message": "No audio chunk provided"}, status=400)
        
        # Decode base64
        import base64
        try:
            if ',' in audio_chunk_base64:
                audio_chunk_base64 = audio_chunk_base64.split(',')[1]
            audio_chunk = base64.b64decode(audio_chunk_base64)
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Invalid audio data: {str(e)}"}, status=400)
        
        # Get or create transcriber session
        global _transcriber_sessions
        
        transcriber = None
        if session_id and session_id in _transcriber_sessions:
            transcriber = _transcriber_sessions[session_id]
        else:
            # Create new transcriber
            from agents.speech.transcription import TranscriptionService
            model = TranscriptionService.get_instance().model
            if not model:
                return JsonResponse({"success": False, "message": "Model not loaded"}, status=500)
            
            from agents.speech.streaming import StreamingTranscriber
            transcriber = StreamingTranscriber(model)
            
            # Generate session ID if not provided
            if not session_id:
                import uuid
                session_id = str(uuid.uuid4())
            
            _transcriber_sessions[session_id] = transcriber
        
        # Process WebM chunk directly (buffering happens inside StreamingTranscriber)
        print(f"📦 Receiving chunk {chunk_index}: {len(audio_chunk)} bytes, format: {audio_format}, is_final: {is_final}")
        result = transcriber.process_webm_chunk(audio_chunk, audio_format=audio_format, is_final=is_final)
        print(f"📝 Transcription result: partial='{result.get('partial', '')}', full_text='{result.get('full_text', '')}', text='{result.get('text', '')}'")
        
        # Clean up if final
        if is_final and session_id in _transcriber_sessions:
            del _transcriber_sessions[session_id]
        
        return JsonResponse({
            "success": True,
            "session_id": session_id,
            "text": result["text"],
            "partial": result["partial"],
            "full_text": result["full_text"],
            "is_final": result["is_final"],
            "chunk_index": chunk_index
        })
        
    except Exception as e:
        print(f"❌ Stream audio chunk error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "message": str(e)}, status=500)

# ============================================================
# Audio Processing (Batch - kept for compatibility)
# ============================================================
@csrf_exempt
@login_required
def process_audio_input(request, conversation_id):
    """
    Process audio input using Vosk transcription and return LangGraph response.
    
    WARNING: This endpoint processes audio and automatically sends through LangGraph.
    For real-time transcription without auto-sending, use stream_audio_chunk instead.
    This endpoint should only be used for batch processing when you want immediate response.
    
    For the chat interface, transcription should use stream_audio_chunk, then the user
    clicks Send which calls add_message (not this endpoint).
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"}, status=400)
    
    # Log warning if this is being called (should use stream_audio_chunk for real-time)
    print("⚠️ WARNING: process_audio_input called - this auto-processes through LangGraph!")
    print("   For real-time transcription, use stream_audio_chunk instead.")
    
    try:
        # Handle new conversation
        if str(conversation_id).lower() == 'new':
            conversation = Conversation.objects.create(
                user=request.user, 
                title="Voice Consultation"
            )
            conversation_id = conversation.id
        else:
            conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
        
        try:
            data = json.loads(request.body)
        except:
            return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)
        
        audio_data_base64 = data.get("audio_data")
        audio_format = data.get("audio_format", "webm")  # Get format from client
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        
        if not audio_data_base64:
            return JsonResponse({"success": False, "message": "No audio data provided"}, status=400)
        
        # Decode base64 audio data
        import base64
        try:
            # Remove data URL prefix if present (e.g., "data:audio/wav;base64,")
            if ',' in audio_data_base64:
                audio_data_base64 = audio_data_base64.split(',')[1]
            
            audio_bytes = base64.b64decode(audio_data_base64)
            print(f"📦 Received audio: {len(audio_bytes)} bytes, format: {audio_format}")
        except Exception as e:
            print(f"❌ Error decoding audio: {e}")
            return JsonResponse({"success": False, "message": f"Invalid audio data: {str(e)}"}, status=400)
        
        # Transcribe audio using Vosk
        transcription = ""
        try:
            from agents.speech.transcription import TranscriptionService
            transcription = TranscriptionService.transcribe_audio(audio_bytes, audio_format=audio_format)
            
            if not transcription or not transcription.strip():
                transcription = "[Could not transcribe audio - please try again]"
            
            print(f"🎤 Transcribed audio: {transcription[:100]}...")
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            import traceback
            traceback.print_exc()
            transcription = "[Transcription error - please try typing your message]"
        
        # Now process the transcription through the same LangGraph flow as add_message
        # We'll reuse the same logic by calling add_message internally or duplicating the flow
        
        # Get user profile for medical context
        try:
            profile = UserProfile.objects.get(user=request.user)
            user_context = {
                "gender": profile.gender,
                "age": profile.age,
                "chronic_diseases": profile.chronic_diseases,
                "blood_type": profile.blood_type,
                "allergies": profile.allergies,
                "medications": profile.medications,
                "profile_complete": profile.is_complete
            }
        except UserProfile.DoesNotExist:
            user_context = {}
        
        # Save user message with transcription
        message_metadata = {}
        if latitude is not None and longitude is not None:
            message_metadata = {"latitude": latitude, "longitude": longitude}
        message_metadata["was_audio"] = True
        
        user_message = Message.objects.create(
            conversation=conversation,
            role='user',
            content=transcription,
            metadata=message_metadata if message_metadata else None
        )
        
        # Process through LangGraph (reuse same logic as add_message)
        bot_content = ""
        metadata = {}
        
        try:
            # Import LangGraph app
            try:
                from agents.graph.build_graph import app
                print("✅ Imported LangGraph from agents.graph.build_graph")
            except ImportError:
                try:
                    from graph.build_graph import app
                    print("✅ Imported LangGraph from graph.build_graph")
                except ImportError:
                    print("⚠️ LangGraph not found, using fallback")
                    from langgraph.graph import StateGraph, END
                    from typing import TypedDict, List
                    
                    class AgentState(TypedDict):
                        user_input: str
                        messages: List[dict]
                        current_agent: str
                        next_agent: str
                        agent_output: str
                        metadata: dict
                    
                    workflow = StateGraph(AgentState)
                    workflow.add_node("gatekeeper", lambda state: {
                        **state,
                        "current_agent": "gatekeeper",
                        "agent_output": f"I received your voice message: {state['user_input']}",
                        "metadata": {"processed_by": "fallback_gatekeeper"}
                    })
                    workflow.set_entry_point("gatekeeper")
                    workflow.add_edge("gatekeeper", END)
                    app = workflow.compile()
            
            # Get conversation history (same as add_message)
            recent_messages = conversation.messages.filter(
                is_deleted=False
            ).order_by('-created_at')[:10]
            
            messages_history = []
            session_id = None
            diagnosis_session_id = None
            pending_questions_from_history = []
            last_symptoms_from_history = []
            last_negative_symptoms_from_history = []
            
            for msg in recent_messages:
                msg_dict = {
                    "role": msg.role,
                    "content": msg.content
                }
                if msg.metadata:
                    try:
                        if isinstance(msg.metadata, dict):
                            msg_dict["metadata"] = msg.metadata
                        elif isinstance(msg.metadata, str):
                            msg_dict["metadata"] = json.loads(msg.metadata)
                    except:
                        pass
                messages_history.append(msg_dict)
                
                if msg.role == 'assistant':
                    try:
                        if isinstance(msg.metadata, dict):
                            msg_metadata = msg.metadata
                        elif isinstance(msg.metadata, str) and msg.metadata:
                            msg_metadata = json.loads(msg.metadata)
                        else:
                            msg_metadata = {}
                        
                        found_session_id = msg_metadata.get("session_id")
                        if found_session_id:
                            session_id = found_session_id
                        
                        found_diagnosis_session_id = msg_metadata.get("diagnosis_session_id")
                        if found_diagnosis_session_id and not diagnosis_session_id:
                            diagnosis_session_id = found_diagnosis_session_id
                        
                        if not last_symptoms_from_history:
                            last_symptoms_from_history = msg_metadata.get("symptoms", []) or []
                        if not last_negative_symptoms_from_history:
                            last_negative_symptoms_from_history = msg_metadata.get("negative_symptoms", []) or []
                        
                        msg_pending = msg_metadata.get("pending_questions", [])
                        if msg_pending and not pending_questions_from_history:
                            pending_questions_from_history = msg_pending
                        
                        if diagnosis_session_id and pending_questions_from_history:
                            break
                    except Exception as e:
                        print(f"⚠️ Error parsing message metadata: {e}")
                        pass
            
            # Extract location
            user_location = None
            if latitude is not None and longitude is not None:
                user_location = (float(latitude), float(longitude))
            else:
                for msg in reversed(recent_messages):
                    if msg.role == 'user' and msg.metadata:
                        try:
                            msg_meta = msg.metadata if isinstance(msg.metadata, dict) else json.loads(msg.metadata)
                            if 'latitude' in msg_meta and 'longitude' in msg_meta:
                                user_location = (float(msg_meta['latitude']), float(msg_meta['longitude']))
                                break
                        except:
                            pass
            
            # Prepare LangGraph state
            langgraph_state = {
                "user_input": transcription,
                "messages": messages_history,
                "current_agent": None,
                "next_agent": None,
                "agent_output": None,
                "user_location": user_location,
                "user_input_location": None,
                "pending_questions": pending_questions_from_history,
                "diagnosis_session_id": diagnosis_session_id,
                "symptoms": last_symptoms_from_history,
                "negative_symptoms": last_negative_symptoms_from_history,
                "metadata": {
                    "conversation_id": conversation_id,
                    "user_id": request.user.id,
                    "user_context": user_context,
                    "was_audio": True,
                },
                "session_id": session_id,
                "diagnosis_complete": False,
            }
            
            # NOTE: This should only be called when user explicitly sends a message
            # NOT automatically during transcription
            print(f"🚀 Invoking LangGraph for audio message in conversation {conversation_id}...")
            print(f"   Transcription: {transcription[:100]}...")
            result = app.invoke(langgraph_state)
            
            # Extract response
            bot_content = result.get("agent_output", "I apologize, but I couldn't generate a response.")
            current_agent = result.get("current_agent", "unknown")
            
            pending_questions = result.get("pending_questions", [])
            session_id = result.get("session_id")
            diagnosis_session_id = result.get("diagnosis_session_id")
            
            # Build metadata
            metadata = {
                "was_audio": True,
                "agent_used": current_agent,
                "user_context_present": bool(user_context),
                "profile_complete": user_context.get("profile_complete", False),
                "session_id": session_id,
                "diagnosis_session_id": diagnosis_session_id,
                "pending_questions": pending_questions,
                "symptoms": result.get("symptoms", []),
                "negative_symptoms": result.get("negative_symptoms", []),
                "transcription": transcription[:200]  # Store first 200 chars of transcription
            }
            
        except Exception as e:
            print(f"❌ LangGraph error: {e}")
            import traceback
            traceback.print_exc()
            bot_content = "I received your voice message, but encountered an error processing it. Please try again."
            metadata = {"was_audio": True, "error": str(e)}
        
        # Save bot response
        bot_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=bot_content,
            metadata=metadata
        )
        
        return JsonResponse({
            "success": True,
            "conversation_id": conversation.id,
            "transcription": transcription,
            "bot_message": {
                "id": bot_message.id,
                "role": bot_message.role,
                "content": bot_message.content,
                "metadata": metadata
            }
        })
        
    except Exception as e:
        print(f"❌ Audio processing error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "message": str(e)}, status=500)

@csrf_exempt
@login_required
def new_conversation_audio(request):
    """Handle audio for new conversations"""
    return process_audio_input(request, 'new')

# ============================================================
# User Profile Endpoint
# ============================================================
@login_required
def get_user_profile(request):
    """Get user profile data for chat context"""
    try:
        profile = UserProfile.objects.get(user=request.user)
        
        return JsonResponse({
            "success": True,
            "profile": {
                "gender": profile.gender,
                "age": profile.age,
                "chronic_diseases": profile.chronic_diseases,
                "blood_type": profile.blood_type,
                "allergies": profile.allergies,
                "medications": profile.medications,
                "completed": profile.is_complete,
                "has_profile": True
            }
        })
    except UserProfile.DoesNotExist:
        return JsonResponse({
            "success": True,
            "profile": {
                "gender": None,
                "age": None,
                "chronic_diseases": [],
                "blood_type": None,
                "allergies": [],
                "medications": [],
                "completed": False,
                "has_profile": False
            }
        })

@login_required
def langsmith_dashboard(request):
    return render(request, 'langsmith_dashboard_new.html')

@login_required
def langsmith_dashboard_agent(request, agent_name: str):
    return render(request, 'langsmith_agent_dashboard.html', {"agent_name": agent_name})

def _langsmith_client():
    try:
        from langsmith import Client
    except Exception:
        return None
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        return None
    try:
        return Client(api_key=api_key)
    except Exception:
        return None

def _extract_agent_name(run_name: str) -> str:
    if not run_name:
        return "unknown"
    if "::" in run_name:
        return run_name.split("::", 1)[0].strip()
    return run_name.strip()

def _list_runs(client, project: str, limit: int = 500, start_time: datetime.datetime | None = None) -> list:
    runs = []
    try:
        iterator = client.list_runs(project_name=project)
        for r in iterator:
            if start_time:
                try:
                    st = getattr(r, "start_time", None)
                    if st and st < start_time:
                        continue
                except Exception:
                    pass
            runs.append(r)
            if len(runs) >= limit:
                break
    except Exception:
        return []
    return runs

def _aggregate_runs(runs: list, agent_filter: str | None = None) -> dict:
    stats = {
        "total_runs": 0,
        "agents": {},
        "errors": 0,
        "success": 0
    }
    for r in runs:
        try:
            name = _extract_agent_name(getattr(r, "name", ""))
        except Exception:
            name = "unknown"
        if agent_filter and name != agent_filter:
            continue
        stats["total_runs"] += 1
        if name not in stats["agents"]:
            stats["agents"][name] = {
                "count": 0,
                "errors": 0,
                "avg_latency_ms": 0.0,
                "avg_total_tokens": 0.0
            }
        a = stats["agents"][name]
        a["count"] += 1
        err = getattr(r, "error", None)
        if err:
            a["errors"] += 1
            stats["errors"] += 1
        else:
            stats["success"] += 1
        try:
            st = getattr(r, "start_time", None)
            et = getattr(r, "end_time", None)
            if st and et:
                latency = (et - st).total_seconds() * 1000.0
                prev = a["avg_latency_ms"]
                count = a["count"]
                a["avg_latency_ms"] = ((prev * (count - 1)) + latency) / count
        except Exception:
            pass
        try:
            tokens = getattr(r, "total_tokens", None)
            if tokens is None:
                tokens = getattr(r, "prompt_tokens", 0) + getattr(r, "completion_tokens", 0)
            prevt = a["avg_total_tokens"]
            countt = a["count"]
            a["avg_total_tokens"] = ((prevt * (countt - 1)) + float(tokens or 0)) / countt
        except Exception:
            pass
    return stats

@login_required
@require_GET
def langsmith_stats(request):
    project = os.getenv("LANGCHAIN_PROJECT", "sahatek-dev")
    client = _langsmith_client()
    if not client:
        return JsonResponse({"available": False, "reason": "LangSmith non configuré"}, status=200)
    time_range = request.GET.get("time_range", "24h")
    now = timezone.now()
    start = None
    if time_range == "24h":
        start = now - datetime.timedelta(hours=24)
    elif time_range == "7d":
        start = now - datetime.timedelta(days=7)
    elif time_range == "30d":
        start = now - datetime.timedelta(days=30)
    runs = _list_runs(client, project, limit=1000, start_time=start)
    aggregated = _aggregate_runs(runs)
    agents = sorted([{ "name": k, **v } for k, v in aggregated["agents"].items()], key=lambda x: x["name"])
    return JsonResponse({
        "available": True,
        "project": project,
        "total_runs": aggregated["total_runs"],
        "errors": aggregated["errors"],
        "success": aggregated["success"],
        "agents": agents
    })

@login_required
@require_GET
def langsmith_agent_stats(request, agent_name: str):
    project = os.getenv("LANGCHAIN_PROJECT", "sahatek-dev")
    client = _langsmith_client()
    if not client:
        return JsonResponse({"available": False, "reason": "LangSmith non configuré"}, status=200)
    time_range = request.GET.get("time_range", "24h")
    now = timezone.now()
    start = None
    if time_range == "24h":
        start = now - datetime.timedelta(hours=24)
    elif time_range == "7d":
        start = now - datetime.timedelta(days=7)
    elif time_range == "30d":
        start = now - datetime.timedelta(days=30)
    runs = _list_runs(client, project, limit=1000, start_time=start)
    aggregated = _aggregate_runs(runs, agent_filter=agent_name)
    agent_stats = aggregated["agents"].get(agent_name, {"count": 0, "errors": 0, "avg_latency_ms": 0.0, "avg_total_tokens": 0.0})
    return JsonResponse({
        "available": True,
        "project": project,
        "agent": agent_name,
        "stats": agent_stats
    })

@login_required
@require_GET
def langsmith_runs(request):
    project = os.getenv("LANGCHAIN_PROJECT", "sahatek-dev")
    client = _langsmith_client()
    if not client:
        return JsonResponse({"available": False, "reason": "LangSmith non configuré"}, status=200)
    time_range = request.GET.get("time_range", "24h")
    agent = request.GET.get("agent")
    status = request.GET.get("status")
    limit = int(request.GET.get("limit", "200"))
    with_io = request.GET.get("with_io", "false").lower() == "true"
    now = timezone.now()
    start = None
    if time_range == "24h":
        start = now - datetime.timedelta(hours=24)
    elif time_range == "7d":
        start = now - datetime.timedelta(days=7)
    elif time_range == "30d":
        start = now - datetime.timedelta(days=30)
    items = []
    try:
        for r in client.list_runs(project_name=project, start_time=start):
            name = getattr(r, "name", "")
            ag = _extract_agent_name(name)
            if agent and ag != agent:
                continue
            err = getattr(r, "error", None)
            st = getattr(r, "start_time", None)
            et = getattr(r, "end_time", None)
            if status == "error" and not err:
                continue
            if status == "success" and err:
                continue
            latency = None
            if st and et:
                latency = (et - st).total_seconds() * 1000.0
            tokens = getattr(r, "total_tokens", None)
            if tokens is None:
                tokens = (getattr(r, "prompt_tokens", 0) or 0) + (getattr(r, "completion_tokens", 0) or 0)
            item = {
                "id": str(getattr(r, "id", "")),
                "trace_id": str(getattr(r, "trace_id", "")),
                "name": name,
                "agent": ag,
                "status": "error" if err else "success",
                "latency_ms": latency,
                "total_tokens": tokens,
                "start_time": st.isoformat() if st else None,
                "end_time": et.isoformat() if et else None,
            }
            if with_io:
                item["inputs"] = getattr(r, "inputs", {})
                item["outputs"] = getattr(r, "outputs", {})
            items.append(item)
            if len(items) >= limit:
                break
    except Exception as e:
        return JsonResponse({"available": False, "reason": str(e)}, status=200)
    items.sort(key=lambda x: (x["end_time"] or ""), reverse=True)
    return JsonResponse({
        "available": True,
        "project": project,
        "runs": items
    })

@login_required
@require_GET
def langsmith_run_detail(request, run_id: str):
    project = os.getenv("LANGCHAIN_PROJECT", "sahatek-dev")
    client = _langsmith_client()
    if not client:
        return JsonResponse({"available": False, "reason": "LangSmith non configuré"}, status=200)
    with_io = request.GET.get("with_io", "true").lower() == "true"
    try:
        r = client.read_run(run_id=str(run_id))
    except Exception as e:
        return JsonResponse({"available": False, "reason": str(e)}, status=200)
    if not r:
        return JsonResponse({"available": False, "reason": "Run introuvable"}, status=404)
    name = getattr(r, "name", "")
    ag = _extract_agent_name(name)
    st = getattr(r, "start_time", None)
    et = getattr(r, "end_time", None)
    latency = None
    if st and et:
        latency = (et - st).total_seconds() * 1000.0
    detail = {
        "id": str(getattr(r, "id", "")),
        "trace_id": str(getattr(r, "trace_id", "")),
        "name": name,
        "agent": ag,
        "status": "error" if getattr(r, "error", None) else "success",
        "error": getattr(r, "error", None),
        "latency_ms": latency,
        "total_tokens": getattr(r, "total_tokens", None),
        "start_time": st.isoformat() if st else None,
        "end_time": et.isoformat() if et else None,
        "run_type": getattr(r, "run_type", None),
        "metadata": getattr(r, "metadata", {}),
    }
    if with_io:
        detail["inputs"] = getattr(r, "inputs", {})
        detail["outputs"] = getattr(r, "outputs", {})
    nodes = []
    try:
        trace_id = getattr(r, "trace_id", None)
        if trace_id:
            for c in client.list_runs(project_name=project, trace_id=str(trace_id)):
                cs = getattr(c, "start_time", None)
                ce = getattr(c, "end_time", None)
                cl = None
                if cs and ce:
                    cl = (ce - cs).total_seconds() * 1000.0
                nodes.append({
                    "id": str(getattr(c, "id", "")),
                    "name": getattr(c, "name", ""),
                    "run_type": getattr(c, "run_type", None),
                    "agent": _extract_agent_name(getattr(c, "name", "")),
                    "latency_ms": cl,
                    "status": "error" if getattr(c, "error", None) else "success",
                })
        nodes.sort(key=lambda x: (x["latency_ms"] or 0), reverse=True)
    except Exception:
        nodes = []
    detail["nodes"] = nodes
    return JsonResponse({"available": True, "run": detail})

# ============================================================
# TTS Endpoint (Optional)
# ============================================================
@csrf_exempt
@login_required
def text_to_speech(request):
    """
    Convert text to speech using Arabic TTS with multiple speakers.
    
    POST /chat/api/text-to-speech/
    Body: {
        "text": "مرحبا بك",
        "speaker": "female_arabic_1",  # Optional
        "language": "ar"  # Optional, default: "ar"
    }
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            text = data.get("text", "")
            speaker = data.get("speaker", None)  # Optional speaker selection
            language = data.get("language", "ar")  # Default to Arabic
            
            if not text or not text.strip():
                return JsonResponse({
                    "success": False,
                    "message": "Text is required"
                }, status=400)
            
            # Import TTS service
            from agents.speech.tts_service import TTSService
            
            # Get TTS service instance
            tts_service = TTSService.get_instance()
            
            # Synthesize speech
            audio_data = tts_service.synthesize(text, speaker=speaker, language=language)
            
            if audio_data:
                # Convert to base64 for JSON response
                import base64
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                
                # Get available speakers for response
                available_speakers = tts_service.get_speakers()
                
                return JsonResponse({
                    "success": True,
                    "audio": audio_base64,
                    "format": "mp3",  # Edge TTS returns MP3
                    "speakers": available_speakers,
                    "current_speaker": speaker or tts_service.current_speaker,
                    "message": "Speech synthesized successfully"
                })
            else:
                return JsonResponse({
                    "success": False,
                    "message": "Failed to synthesize speech. Check server logs."
                }, status=500)
                
        except Exception as e:
            print(f"❌ TTS endpoint error: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                "success": False,
                "message": str(e)
            }, status=500)
    
    elif request.method == "GET":
        # Return available speakers
        try:
            from agents.speech.tts_service import TTSService
            tts_service = TTSService.get_instance()
            speakers = tts_service.get_speakers()
            
            return JsonResponse({
                "success": True,
                "speakers": speakers,
                "available": tts_service.is_available()
            })
        except Exception as e:
            return JsonResponse({
                "success": False,
                "message": str(e)
            }, status=500)
    
    return JsonResponse({"success": False, "message": "Invalid method"}, status=405)

# ============================================================
# Translation Service
# ============================================================
@csrf_exempt
@login_required
def translate_text(request):
    """
    Translate text from English to Arabic using transformer models.
    
    POST /chat/api/translate/
    Body: {"text": "Hello world", "source_lang": "en", "target_lang": "ar"}
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method"}, status=400)
    
    try:
        data = json.loads(request.body)
        text = data.get("text", "").strip()
        source_lang = data.get("source_lang", "en")
        target_lang = data.get("target_lang", "ar")
        
        if not text:
            return JsonResponse({"success": False, "message": "No text provided"}, status=400)
        
        # Import translation service
        from agents.translation.translation_service import TranslationService
        
        # Get translation service instance
        translation_service = TranslationService.get_instance()
        
        # Translate text
        print(f"🌐 Translating: '{text[:50]}...' from {source_lang} to {target_lang}")
        translated_text = translation_service.translate(text, source_lang=source_lang, target_lang=target_lang)
        
        return JsonResponse({
            "success": True,
            "original_text": text,
            "translated_text": translated_text,
            "source_lang": source_lang,
            "target_lang": target_lang
        })
        
    except Exception as e:
        print(f"❌ Translation error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "message": str(e)}, status=500)