# views.py - FINAL VERSION with Wound Analyzer Support
import json
import base64
import numpy as np
import cv2
import os
import datetime
import uuid
import threading
import time
from typing import Optional, Tuple
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import render
from agents.models import Conversation, Message
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET
from django.utils import timezone
from users.models import UserProfile

# ============================================================
# Helper Functions
# ============================================================

def get_user_context(request):
    """Get user profile context or empty dict if not exists"""
    try:
        profile = UserProfile.objects.get(user=request.user)
        return {
            "gender": profile.gender,
            "age": profile.age,
            "chronic_diseases": profile.chronic_diseases,
            "blood_type": profile.blood_type,
            "allergies": profile.allergies,
            "medications": profile.medications,
            "profile_complete": profile.is_complete
        }
    except UserProfile.DoesNotExist:
        return {}

def extract_conversation_metadata(conversation):
    """Safely extract metadata from conversation"""
    if not conversation.metadata:
        return {}
    
    if isinstance(conversation.metadata, dict):
        return conversation.metadata
    elif isinstance(conversation.metadata, str):
        try:
            return json.loads(conversation.metadata)
        except:
            return {}
    return {}

def extract_history_data(recent_messages):
    """Extract session data from message history"""
    session_id = None
    diagnosis_session_id = None
    pending_questions = []
    last_symptoms = []
    last_negative_symptoms = []
    
    for msg in recent_messages:
        if msg.role == 'assistant' and msg.metadata:
            try:
                if isinstance(msg.metadata, dict):
                    metadata = msg.metadata
                elif isinstance(msg.metadata, str):
                    metadata = json.loads(msg.metadata)
                else:
                    continue
                
                # Extract session IDs
                if not session_id and metadata.get("session_id"):
                    session_id = metadata.get("session_id")
                
                if not diagnosis_session_id and metadata.get("diagnosis_session_id"):
                    diagnosis_session_id = metadata.get("diagnosis_session_id")
                
                # Extract symptom data
                if not last_symptoms:
                    last_symptoms = metadata.get("symptoms", [])
                if not last_negative_symptoms:
                    last_negative_symptoms = metadata.get("negative_symptoms", [])
                
                # Extract pending questions
                if not pending_questions:
                    pending_questions = metadata.get("pending_questions", [])
                
            except Exception as e:
                print(f"⚠️ Error parsing message metadata: {e}")
                continue
    
    return {
        "session_id": session_id,
        "diagnosis_session_id": diagnosis_session_id,
        "pending_questions": pending_questions,
        "symptoms": last_symptoms,
        "negative_symptoms": last_negative_symptoms
    }

def get_user_location_from_data(data, recent_messages=None):
    """Extract user location from request data or message history"""
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    
    # Check request data first
    if latitude is not None and longitude is not None:
        try:
            return (float(latitude), float(longitude))
        except (ValueError, TypeError):
            pass
    
    # Check recent messages for location if provided
    if recent_messages:
        for msg in reversed(recent_messages):
            if msg.role == 'user' and msg.metadata:
                try:
                    if isinstance(msg.metadata, dict):
                        msg_meta = msg.metadata
                    elif isinstance(msg.metadata, str):
                        msg_meta = json.loads(msg.metadata)
                    else:
                        continue
                        
                    if 'latitude' in msg_meta and 'longitude' in msg_meta:
                        lat = msg_meta['latitude']
                        lon = msg_meta['longitude']
                        if lat is not None and lon is not None:
                            return (float(lat), float(lon))
                except:
                    continue
    
    return None

def import_langgraph_app():
    """Import LangGraph app with fallbacks"""
    try:
        from agents.graph.build_graph import app
        print("✅ Imported LangGraph from agents.graph.build_graph")
        return app
    except ImportError:
        try:
            from graph.build_graph import app
            print("✅ Imported LangGraph from graph.build_graph")
            return app
        except ImportError:
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
            
            def fallback_node(state):
                return {
                    **state,
                    "current_agent": "fallback",
                    "agent_output": f"Fallback response: {state['user_input']}",
                    "metadata": {"processed_by": "fallback"}
                }
            
            workflow.add_node("fallback", fallback_node)
            workflow.set_entry_point("fallback")
            workflow.add_edge("fallback", END)
            return workflow.compile()

def create_bot_response_metadata(result, current_agent, user_context, history_data, 
                                 preferred_agent=None, forced_agent=None, message_type="regular"):
    """Create metadata for bot response"""
    metadata = {
        "agent_used": current_agent,
        "user_context_present": bool(user_context),
        "profile_complete": user_context.get("profile_complete", False) if user_context else False,
        "session_id": result.get("session_id") or history_data.get("session_id"),
        "diagnosis_session_id": result.get("diagnosis_session_id") or history_data.get("diagnosis_session_id"),
        "pending_questions": result.get("pending_questions", []),
        "diagnosis_complete": result.get("diagnosis_complete", False),
        "symptoms": result.get("symptoms", []),
        "negative_symptoms": result.get("negative_symptoms", []),
        "diagnoses": result.get("diagnoses", []),
    }
    
    # Add routing info
    routing_info = {
        "type": message_type,
        "preferred_agent_used": preferred_agent,
        "forced_agent_used": forced_agent
    }
    
    if message_type == "regular":
        routing_info["was_handled_by_gatekeeper"] = result.get("gatekeeper_decision", {}).get("should_route", True) == False
        routing_info["gatekeeper_decision"] = result.get("gatekeeper_decision", {})
        metadata["langgraph_state"] = {
            "intent": result.get("intent"),
            "emergency_level": result.get("emergency_level"),
            "confidence": result.get("confidence_score", 0.0)
        }
    elif message_type == "direct_agent":
        routing_info["requested_agent"] = forced_agent
        routing_info["success"] = current_agent != "router"
        
        # Check if forced routing was detected
        if "metadata" in result and "forced_routing" in result["metadata"]:
            routing_info["forced_routing_details"] = result["metadata"]["forced_routing"]
            routing_info["routing_successful"] = True
        else:
            routing_info["routing_successful"] = False
    
    metadata["routing_info"] = routing_info
    
    # Add healthcare recommendation if available
    if result.get("places") or result.get("nearby_facilities") or result.get("latitude") or result.get("longitude"):
        metadata["recommendation"] = {
            "service_type": result.get("service_type", ""),
            "immediate_care": result.get("immediate_care", False),
            "places": result.get("places", result.get("nearby_facilities", [])),
            "latitude": result.get("latitude"),
            "longitude": result.get("longitude")
        }
    
    # Add wound analysis data if available
    if result.get("wound_analysis"):
        metadata["wound_analysis"] = result.get("wound_analysis")
        metadata["severity"] = result.get("severity", "unknown")
        metadata["urgency"] = result.get("urgency", "unknown")
    
    return metadata

def prepare_messages_history(recent_messages):
    """Prepare message history for LangGraph"""
    messages_history = []
    for msg in recent_messages:
        msg_dict = {
            "role": msg.role,
            "content": msg.content
        }
        if msg.metadata:
            if isinstance(msg.metadata, dict):
                msg_dict["metadata"] = msg.metadata
            elif isinstance(msg.metadata, str):
                try:
                    msg_dict["metadata"] = json.loads(msg.metadata)
                except:
                    pass
        messages_history.append(msg_dict)
    return messages_history

# ============================================================
# Main Views
# ============================================================

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
            "message_count": c.messages.filter(is_deleted=False).count(),
            "metadata": c.metadata if hasattr(c, 'metadata') else {}
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
        agent = data.get("agent")
        
        metadata = {}
        if agent:
            metadata["agent"] = agent
        
        conversation = Conversation.objects.create(
            user=request.user, 
            title=title,
            metadata=metadata if metadata else None
        )
        
        return JsonResponse({
            "success": True,
            "conversation": {
                "id": conversation.id,
                "title": conversation.title,
                "created_at": conversation.created_at.isoformat(),
                "is_pinned": conversation.is_pinned,
                "metadata": conversation.metadata
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
# View 1: Regular Message (Uses Conversation Metadata)
# ============================================================
@csrf_exempt
@login_required
def add_message(request, conversation_id):
    """
    Add a message and get response from LangGraph agents.
    For REGULAR messages where routing is determined by:
    1. Conversation metadata (if it's an agent-specific conversation)
    2. Router agent (if it's a general conversation)
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method"}, status=400)
    
    try:
        # Parse request data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)
        
        role = data.get("role")
        content = data.get("content", "").strip()
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        image_data = data.get("image")  # Extract image data for wound analyzer
        
        # Validate data
        if role not in ['user', 'assistant']:
            return JsonResponse({"success": False, "message": "Invalid role"}, status=400)
        
        if not content:
            return JsonResponse({"success": False, "message": "Content is required"}, status=400)
        
        # Handle new conversation
        if str(conversation_id).lower() == 'new':
            title = content[:30] + "..." if len(content) > 30 else content
            conversation = Conversation.objects.create(user=request.user, title=title)
            conversation_id = conversation.id
        else:
            try:
                conversation = Conversation.objects.get(id=conversation_id, user=request.user)
            except Conversation.DoesNotExist:
                return JsonResponse({"success": False, "message": "Conversation not found"}, status=404)
        
        # Save user message with location metadata and image data
        message_metadata = {}
        if latitude is not None and longitude is not None:
            try:
                message_metadata = {
                    "latitude": float(latitude),
                    "longitude": float(longitude)
                }
            except (ValueError, TypeError):
                pass  # Ignore invalid coordinates
        
        if image_data:
            message_metadata["image"] = image_data
        
        user_message = Message.objects.create(
            conversation=conversation, 
            role=role, 
            content=content,
            metadata=message_metadata if message_metadata else None
        )
        
        # Get user profile context
        user_context = get_user_context(request)
        
        # Get recent messages for history
        recent_messages = conversation.messages.filter(
            is_deleted=False
        ).order_by('-created_at')[:10]
        
        # Extract data from history
        history_data = extract_history_data(recent_messages)
        
        # Extract location
        user_location = get_user_location_from_data(data, recent_messages)
        
        # Get preferred agent from conversation metadata
        conversation_meta = extract_conversation_metadata(conversation)
        preferred_agent = conversation_meta.get('agent')
        if preferred_agent:
            print(f"🎯 Found preferred_agent from conversation metadata: {preferred_agent}")
        
        # Import and run LangGraph
        app = import_langgraph_app()
        
        # Prepare message history for LangGraph
        messages_history = prepare_messages_history(recent_messages)
        
        # Prepare LangGraph state for REGULAR message
        langgraph_state = {
            "user_input": content,
            "messages": messages_history,
            "current_agent": None,
            "next_agent": None,
            "agent_output": None,
            "user_location": user_location,
            "user_input_location": None,
            "pending_questions": history_data.get("pending_questions", []),
            "diagnosis_session_id": history_data.get("diagnosis_session_id"),
            "symptoms": history_data.get("symptoms", []),
            "negative_symptoms": history_data.get("negative_symptoms", []),
            "metadata": {
                "conversation_id": conversation_id,
                "user_id": request.user.id,
                "user_context": user_context,
                "message_type": "regular",
                "conversation_metadata": conversation_meta,  # Pass conversation metadata
                "image": image_data,  # Pass image data for wound analyzer
            },
            "session_id": history_data.get("session_id"),
            "diagnosis_complete": False,
            "preferred_agent": preferred_agent,
            "forced_agent": None,
        }
        
        print(f"🚀 Invoking LangGraph for REGULAR message in conversation {conversation_id}...")
        if preferred_agent:
            print(f"   Using preferred_agent from conversation metadata: {preferred_agent}")
        if image_data:
            print(f"   Image data included for wound analysis")
        
        # Run LangGraph
        try:
            result = app.invoke(langgraph_state)
            bot_content = result.get("agent_output", "I apologize, but I couldn't generate a response.")
            current_agent = result.get("current_agent", "unknown")
            
            # Create metadata for bot response
            metadata = create_bot_response_metadata(
                result=result,
                current_agent=current_agent,
                user_context=user_context,
                history_data=history_data,
                preferred_agent=preferred_agent,
                message_type="regular"
            )
            
            print(f"✅ LangGraph completed. Agent: {current_agent}")
            
        except Exception as e:
            print(f"❌ LangGraph error: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback response
            bot_content = f"I received your message: '{content}'. I'm currently experiencing technical difficulties with my advanced processing."
            metadata = {
                "agent_used": "fallback",
                "error": str(e),
                "user_context_present": bool(user_context),
                "routing_info": {
                    "type": "regular",
                    "error": str(e)
                }
            }
        
        # Save bot response
        bot_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=bot_content,
            metadata=metadata
        )
        
        print(f"✅ Bot message saved with metadata")
        
        return JsonResponse({
            "success": True,
            "conversation_id": conversation.id,
            "bot_message": {
                "id": bot_message.id,
                "role": bot_message.role,
                "content": bot_message.content,
                "agent": current_agent,
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

# ============================================================
# View 2: Direct Agent Message (For Card Clicks)
# ============================================================
@csrf_exempt
@login_required
def direct_agent_message(request):
    """
    Direct message to a specific agent (for card clicks).
    Creates a NEW conversation specifically for the agent and forces routing.
    
    POST /chat/api/direct-agent-message/
    Body: {
        "content": "I have a wound on my leg",
        "agent": "wound-analyzer",  # New wound analyzer agent
        "latitude": 35.234,
        "longitude": -5.123,
        "image": "base64_image_data",  # For wound analysis
        "is_system_trigger": true
    }
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method"}, status=400)
    
    try:
        # Parse request data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)
        
        content = data.get("content", "").strip()
        agent = data.get("agent", "").strip()
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        image_data = data.get("image")
        is_system_trigger = data.get("is_system_trigger", False)
        
        # Validate data
        if not content and not is_system_trigger:
            return JsonResponse({"success": False, "message": "Content is required"}, status=400)
        
        if not agent:
            return JsonResponse({"success": False, "message": "Agent is required for direct routing"}, status=400)
        
        # Validate agent - UPDATED to include wound-analyzer
        valid_agents = ["mental-health", "symptoms-checker", "general-info", "rumor-check", "orientation", "wound-analyzer"]
        if agent not in valid_agents:
            return JsonResponse({
                "success": False, 
                "message": f"Invalid agent. Must be one of: {', '.join(valid_agents)}"
            }, status=400)
        
        # Create conversation with agent metadata
        agent_titles = {
            "mental-health": "🧠 Mental Health Support",
            "symptoms-checker": "🩺 Symptoms Checker",
            "general-info": "📚 Medical Information",
            "rumor-check": "🔍 Health Fact Check",
            "orientation": "📍 Medical Guidance",
            "wound-analyzer": "🩹 Wound Analysis"  # New title for wound analyzer
        }
        
        title = agent_titles.get(agent, "Specialized Chat")
        conversation = Conversation.objects.create(
            user=request.user,
            title=title,
            metadata={"agent": agent}
        )
        
        print(f"🎯 Created new conversation for direct agent: {agent}, title: {title}")
        print(f"   Is system trigger: {is_system_trigger}")
        print(f"   Conversation ID: {conversation.id}")
        if image_data:
            print(f"   Image data included for analysis")
        
        # Save user message (empty content for system triggers)
        message_metadata = {}
        if latitude is not None and longitude is not None:
            try:
                message_metadata = {
                    "latitude": float(latitude),
                    "longitude": float(longitude)
                }
            except (ValueError, TypeError):
                pass
        
        if image_data:
            message_metadata["image"] = image_data
        
        user_message = Message.objects.create(
            conversation=conversation,
            role='user',
            content=content if not is_system_trigger else "",  # Empty for system triggers
            metadata=message_metadata if message_metadata else None
        )
        
        # Get user profile context
        user_context = get_user_context(request)
        
        # === CRITICAL FIX ===
        # If this is a SYSTEM TRIGGER (card click with no content),
        # DO NOT invoke LangGraph. Just return a welcome message.
        if is_system_trigger:
            print(f"🚫 SYSTEM TRIGGER DETECTED - NOT invoking LangGraph, returning welcome message")
            
            # Agent-specific welcome messages - UPDATED to include wound analyzer
            welcome_messages = {
                "mental-health": "Hello! I'm your mental health assistant. I'm here to provide emotional support and coping strategies. How are you feeling today?",
                "symptoms-checker": "Hello! I'm your symptoms checker. Please describe your symptoms in detail, and I'll help you understand possible causes and when to seek medical attention.",
                "general-info": "Hello! I'm your medical information assistant. I can provide evidence-based information about health conditions, medications, and treatments. What would you like to know?",
                "rumor-check": "Hello! I'm your health fact checker. I can verify medical claims and provide evidence-based information. What health claim would you like me to check?",
                "orientation": "Hello! I'm your medical guidance assistant. I provide step-by-step instructions for medical procedures and first aid. How can I guide you today?",
                "wound-analyzer": "Hello! I'm your wound analysis assistant. I can analyze wounds, cuts, burns, and skin conditions. Please describe your wound or upload an image for analysis."  # New welcome
            }
            
            bot_content = welcome_messages.get(agent, f"Hello! I'm your {agent.replace('-', ' ')} assistant. How can I help you today?")
            
            metadata = {
                "agent_used": agent,
                "user_context_present": bool(user_context),
                "profile_complete": user_context.get("profile_complete", False) if user_context else False,
                "routing_info": {
                    "type": "direct_agent",
                    "requested_agent": agent,
                    "was_system_trigger": True,
                    "routing_successful": True,
                    "langgraph_not_invoked": True,  # Important flag
                    "message": "Welcome message returned, waiting for user input"
                }
            }
            
            # Save bot response
            bot_message = Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=bot_content,
                metadata=metadata
            )
            
            print(f"✅ Conversation {conversation.id} ready with {agent} (welcome message only)")
            print(f"   LangGraph NOT invoked for system trigger")
            
            return JsonResponse({
                "success": True,
                "conversation_id": conversation.id,
                "agent": agent,
                "bot_message": {
                    "id": bot_message.id,
                    "role": bot_message.role,
                    "content": bot_content,
                    "agent": agent,  # ← CRITICAL: Add agent at top level
                    "metadata": metadata
                }
            })
        
        # === REGULAR DIRECT AGENT REQUEST (with content) ===
        # Only invoke LangGraph if there's actual user content
        print(f"📝 REGULAR DIRECT AGENT REQUEST with content: '{content[:100]}...'")
        
        # Import and run LangGraph
        app = import_langgraph_app()
        
        # Extract location
        user_location = None
        if latitude is not None and longitude is not None:
            try:
                user_location = (float(latitude), float(longitude))
            except (ValueError, TypeError):
                pass
        
        # Prepare LangGraph state with FORCED agent routing
        langgraph_state = {
            "user_input": content,
            "messages": [{
                "role": "user",
                "content": content,
                "metadata": message_metadata if message_metadata else {}
            }],
            "current_agent": None,
            "next_agent": None,
            "agent_output": None,
            "user_location": user_location,
            "user_input_location": None,
            "pending_questions": [],
            "diagnosis_session_id": None,
            "symptoms": [],
            "negative_symptoms": [],
            "metadata": {
                "conversation_id": conversation.id,
                "user_id": request.user.id,
                "user_context": user_context,
                "message_type": "direct_agent",
                "direct_agent_request": True,
                "is_system_trigger": False,  # Explicitly false for regular requests
                "requested_agent": agent,
                "conversation_metadata": {"agent": agent},
                "image": image_data,  # Pass image data for wound analyzer
            },
            "session_id": None,
            "diagnosis_complete": False,
            "forced_agent": agent,  # ALSO set at root level for redundancy
            "preferred_agent": None,
        }
        
        print(f"🚀 Invoking LangGraph for DIRECT agent with content")
        print(f"   State preparation complete:")
        print(f"     - forced_agent at root: {langgraph_state.get('forced_agent')}")
        print(f"     - requested_agent in metadata: {langgraph_state.get('metadata', {}).get('requested_agent')}")
        print(f"     - direct_agent_request: {langgraph_state.get('metadata', {}).get('direct_agent_request')}")
        print(f"     - message_type: {langgraph_state.get('metadata', {}).get('message_type')}")
        print(f"   User message: {content[:100]}...")
        if image_data:
            print(f"   Image data included for analysis")
        
        # Run LangGraph
        try:
            result = app.invoke(langgraph_state)
            bot_content = result.get("agent_output", "I apologize, but I couldn't generate a response.")
            current_agent = result.get("current_agent", "unknown")
            
            # Create metadata for bot response
            metadata = create_bot_response_metadata(
                result=result,
                current_agent=current_agent,
                user_context=user_context,
                history_data={},  # Empty for new conversation
                forced_agent=agent,
                message_type="direct_agent"
            )
            
            # Add forced routing info to response metadata
            if "metadata" in result and "forced_routing" in result["metadata"]:
                metadata["forced_routing"] = result["metadata"]["forced_routing"]
            
            print(f"✅ Direct agent routing completed.")
            print(f"   Requested agent: {agent}")
            print(f"   Actual agent used: {current_agent}")
            print(f"   Routing successful: {current_agent != 'router'}")
            
        except Exception as e:
            print(f"❌ LangGraph error in direct agent: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback response with agent-specific welcome
            agent_welcome_messages = {
                "mental-health": "Hello! I'm your mental health assistant. I'm here to provide emotional support and coping strategies. How are you feeling today?",
                "symptoms-checker": "Hello! I'm your symptoms checker. Please describe your symptoms in detail, and I'll help you understand possible causes and when to seek medical attention.",
                "general-info": "Hello! I'm your medical information assistant. I can provide evidence-based information about health conditions, medications, and treatments. What would you like to know?",
                "rumor-check": "Hello! I'm your health fact checker. I can verify medical claims and provide evidence-based information. What health claim would you like me to check?",
                "orientation": "Hello! I'm your medical guidance assistant. I provide step-by-step instructions for medical procedures and first aid. How can I guide you today?",
                "wound-analyzer": "Hello! I'm your wound analysis assistant. I can analyze wounds, cuts, burns, and skin conditions. Please describe your wound or upload an image for analysis."
            }
            
            bot_content = agent_welcome_messages.get(agent, f"I'm your {agent.replace('-', ' ')} assistant. How can I help you today?")
            metadata = {
                "agent_used": "fallback",
                "error": str(e),
                "routing_info": {
                    "type": "direct_agent_request",
                    "requested_agent": agent,
                    "forced_agent_used": False,
                    "error": str(e),
                    "was_system_trigger": False
                }
            }
        
        # Save bot response
        bot_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=bot_content,
            metadata=metadata
        )
        
        # Log success
        print(f"✅ Conversation {conversation.id} ready with {agent}")
        print(f"   Bot message saved with {len(bot_content)} characters")
        
        return JsonResponse({
            "success": True,
            "conversation_id": conversation.id,
            "agent": agent,
            "bot_message": {
                "id": bot_message.id,
                "role": bot_message.role,
                "content": bot_content,
                "agent": agent,  # ← CRITICAL: Add agent at top level
                "metadata": metadata
            }
        })
        
    except Exception as e:
        print(f"❌ Critical error in direct_agent_message: {e}")
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
_transcriber_sessions = {}

def _cleanup_old_sessions():
    """Clean up transcriber sessions older than 5 minutes (background task)"""
    # This is a simple cleanup - in production, use a proper task queue
    pass

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
        user_context = get_user_context(request)
        
        # Save user message with transcription
        message_metadata = {}
        if latitude is not None and longitude is not None:
            try:
                message_metadata = {
                    "latitude": float(latitude),
                    "longitude": float(longitude)
                }
            except (ValueError, TypeError):
                pass
        message_metadata["was_audio"] = True
        
        user_message = Message.objects.create(
            conversation=conversation,
            role='user',
            content=transcription,
            metadata=message_metadata if message_metadata else None
        )
        
        # Get recent messages for history
        recent_messages = conversation.messages.filter(
            is_deleted=False
        ).order_by('-created_at')[:10]
        
        # Extract data from history
        history_data = extract_history_data(recent_messages)
        
        # Extract location
        user_location = get_user_location_from_data(data, recent_messages)
        
        # Get preferred agent from conversation metadata
        conversation_meta = extract_conversation_metadata(conversation)
        preferred_agent = conversation_meta.get('agent')
        
        # Import and run LangGraph
        app = import_langgraph_app()
        
        # Prepare message history for LangGraph
        messages_history = prepare_messages_history(recent_messages)
        
        # Prepare LangGraph state
        langgraph_state = {
            "user_input": transcription,
            "messages": messages_history,
            "current_agent": None,
            "next_agent": None,
            "agent_output": None,
            "user_location": user_location,
            "user_input_location": None,
            "pending_questions": history_data.get("pending_questions", []),
            "diagnosis_session_id": history_data.get("diagnosis_session_id"),
            "symptoms": history_data.get("symptoms", []),
            "negative_symptoms": history_data.get("negative_symptoms", []),
            "metadata": {
                "conversation_id": conversation_id,
                "user_id": request.user.id,
                "user_context": user_context,
                "was_audio": True,
                "conversation_metadata": conversation_meta,  # Pass conversation metadata
            },
            "session_id": history_data.get("session_id"),
            "diagnosis_complete": False,
            "preferred_agent": preferred_agent,
            "forced_agent": None,
        }
        
        print(f"🚀 Invoking LangGraph for audio message in conversation {conversation_id}...")
        print(f"   Transcription: {transcription[:100]}...")
        
        # Run LangGraph
        try:
            result = app.invoke(langgraph_state)
            bot_content = result.get("agent_output", "I apologize, but I couldn't generate a response.")
            current_agent = result.get("current_agent", "unknown")
            
            # Create metadata for bot response
            metadata = create_bot_response_metadata(
                result=result,
                current_agent=current_agent,
                user_context=user_context,
                history_data=history_data,
                preferred_agent=preferred_agent,
                message_type="regular"
            )
            metadata["was_audio"] = True
            metadata["transcription"] = transcription[:200]  # Store first 200 chars of transcription
            
        except Exception as e:
            print(f"❌ LangGraph error: {e}")
            import traceback
            traceback.print_exc()
            bot_content = "I received your voice message, but encountered an error processing it. Please try again."
            metadata = {
                "was_audio": True,
                "error": str(e),
                "transcription": transcription[:200] if transcription else ""
            }
        
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
                "agent": current_agent,  # ← CRITICAL: Add agent at top level
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

# ============================================================
# MENTAL HEALTH VIEWS
# ============================================================

# DeepFace (mood detection)
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except Exception:
    DeepFace = None
    DEEPFACE_AVAILABLE = False

def _decode_base64_image(data_url: str):
    """
    Accepts:
      - "data:image/jpeg;base64,AAAA..."
      - or raw base64 "AAAA..."
    Returns: OpenCV image (BGR) or None
    """
    if not data_url:
        return None

    try:
        # remove dataurl prefix if exists
        if "," in data_url:
            data_url = data_url.split(",", 1)[1]

        raw = base64.b64decode(data_url)
        np_arr = np.frombuffer(raw, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)  # BGR
        return img
    except Exception:
        return None

def _detect_mood_from_image(img_bgr):
    """
    Returns dominant emotion string, or "unknown".
    Uses DeepFace if installed.
    """
    if not DEEPFACE_AVAILABLE or img_bgr is None:
        return "unknown"

    try:
        result = DeepFace.analyze(
            img_path=img_bgr,
            actions=["emotion"],
            enforce_detection=False
        )
        if isinstance(result, list):
            result = result[0]
        mood = (result.get("dominant_emotion") or "unknown").strip().lower()
        return mood or "unknown"
    except Exception:
        return "unknown"

@login_required
def mental_health_chat(request):
    """Dedicated UI page for the mental health agent only."""
    try:
        profile = UserProfile.objects.get(user=request.user)
        profile_complete = profile.is_complete
    except UserProfile.DoesNotExist:
        profile_complete = False
    
    return render(request, "mental_health.html", {
        "user": request.user,
        "profile_complete": profile_complete
    })

@csrf_exempt
@login_required
@require_POST
def mental_health_send(request):
    """
    Dedicated API endpoint that talks ONLY to mental_health_agent.
    """
    print("=" * 60)
    print("DEBUG: mental_health_send endpoint called!")
    print(f"DEBUG: User: {request.user}")
    print(f"DEBUG: Method: {request.method}")
    
    try:
        # Read the raw body
        body = request.body.decode('utf-8')
        print(f"DEBUG: Raw body length: {len(body)} chars")
        
        data = json.loads(body)
        user_text = (data.get("content") or "").strip()
        image_data = data.get("image")
        
        print(f"DEBUG: Content received: '{user_text[:50]}...'")
        print(f"DEBUG: Image data present: {'YES' if image_data else 'NO'}")
        
        if image_data:
            print(f"DEBUG: Image data length: {len(image_data)} chars")
            print(f"DEBUG: Image data starts with: {image_data[:50]}...")
        
    except Exception as e:
        print(f"DEBUG: Error parsing request: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    if not user_text:
        print("DEBUG: Empty message, returning error")
        return JsonResponse({"success": False, "message": "Empty message"}, status=400)

    # 1) Detect mood
    detected_mood = "unknown"
    if image_data:
        try:
            print("DEBUG: Attempting to decode image...")
            img = _decode_base64_image(image_data)
            if img is not None:
                print(f"DEBUG: Image decoded successfully, shape: {img.shape}")
                detected_mood = _detect_mood_from_image(img)
                print(f"DEBUG: Mood detected: {detected_mood}")
            else:
                print("DEBUG: Failed to decode image")
        except Exception as e:
            print(f"DEBUG: Error during mood detection: {str(e)}")
            import traceback
            traceback.print_exc()
    else:
        print("DEBUG: No image data provided for mood detection")

    print(f"DEBUG: Final mood: {detected_mood}")
    
    # 2) Create/find a dedicated conversation for mental health
    try:
        conversation, created = Conversation.objects.get_or_create(
            user=request.user,
            title="🧠 Mental Health (private)",
            defaults={
                "is_pinned": True,
                "metadata": {"agent": "mental-health"}
            }
        )
        print(f"DEBUG: Conversation: {conversation.id}, Created: {created}")
    except Exception as e:
        print(f"DEBUG: Error creating conversation: {str(e)}")
        return JsonResponse({
            "success": False,
            "message": "Error creating conversation",
            "detected_mood": detected_mood
        }, status=500)

    # Save user message (store mood in metadata too, so you can review later)
    try:
        user_msg_metadata = {"detected_mood": detected_mood} if detected_mood != "unknown" else {}
        user_msg = Message.objects.create(
            conversation=conversation,
            role="user",
            content=user_text,
            metadata=user_msg_metadata
        )
        print(f"DEBUG: User message saved: {user_msg.id}")
    except Exception as e:
        print(f"DEBUG: Error saving user message: {str(e)}")
        return JsonResponse({
            "success": False,
            "message": "Error saving message",
            "detected_mood": detected_mood
        }, status=500)

    # 3) Build history (last 12 messages)
    try:
        recent = conversation.messages.filter(is_deleted=False).order_by("-created_at")[:12]
        history = [{"role": m.role, "content": m.content} for m in reversed(recent)]
        print(f"DEBUG: History built with {len(history)} messages")
    except Exception as e:
        print(f"DEBUG: Error building history: {str(e)}")
        history = []

    # 4) Call ONLY the mental_health_agent
    try:
        print("DEBUG: Trying to import mental_health_agent")
        from agents.mental_health.agent import mental_health_agent
        print("DEBUG: Import successful")
    except ImportError as e:
        print(f"DEBUG: Import error: {e}")
        # Return a basic response if agent not available
        bot_text = f"I'm here to listen and support you. You mentioned: {user_text[:100]}..."
        meta = {
            "detected_mood": detected_mood,
            "agent_used": "fallback",
            "error": "Mental health agent not available"
        }
        
        try:
            bot_msg = Message.objects.create(
                conversation=conversation,
                role="assistant",
                content=bot_text,
                metadata=meta
            )
            
            return JsonResponse({
                "success": True,
                "conversation_id": conversation.id,
                "detected_mood": detected_mood,
                "bot_message": {
                    "id": bot_msg.id,
                    "role": "assistant",
                    "content": bot_text,
                    "metadata": meta
                }
            })
        except Exception as save_error:
            print(f"DEBUG: Error saving fallback message: {save_error}")
            return JsonResponse({
                "success": False,
                "message": "Error processing request",
                "detected_mood": detected_mood
            }, status=500)

    state = {
        "user_input": user_text,
        "messages": history,
        "metadata": {
            "conversation_id": conversation.id,
            "user_id": request.user.id,
            "detected_mood": detected_mood,
        },
        "current_agent": None,
        "next_agent": None,
        "agent_output": None,
    }

    try:
        print("DEBUG: Calling mental_health_agent...")
        out = mental_health_agent(state)
        print(f"DEBUG: Agent returned: {type(out)}")
        
        bot_text = out.get("agent_output") or "Sorry, I couldn't generate a response."
        meta = out.get("metadata", {}) or {}
        # Ensure mood is always included in response metadata (so UI can display it if you want)
        meta["detected_mood"] = detected_mood
        meta["agent_used"] = "mental-health"
        
        print(f"DEBUG: Bot text length: {len(bot_text)}")
        
    except Exception as e:
        print(f"DEBUG: Error in mental_health_agent: {str(e)}")
        import traceback
        traceback.print_exc()
        bot_text = f"I'm sorry, I encountered an error: {str(e)[:100]}"
        meta = {
            "detected_mood": detected_mood,
            "agent_used": "mental-health",
            "error": str(e)[:100]
        }

    # Save bot message with metadata
    try:
        bot_msg = Message.objects.create(
            conversation=conversation,
            role="assistant",
            content=bot_text,
            metadata=meta
        )
        print(f"DEBUG: Bot message saved: {bot_msg.id}")
    except Exception as e:
        print(f"DEBUG: Error saving bot message: {str(e)}")
        # Still return a response even if saving fails
        return JsonResponse({
            "success": False,
            "message": "Error saving response",
            "detected_mood": detected_mood,
            "bot_message": {
                "content": bot_text,
                "metadata": meta
            }
        }, status=500)

    print(f"DEBUG: Returning successful response with mood: {detected_mood}")
    return JsonResponse({
        "success": True,
        "conversation_id": conversation.id,
        "detected_mood": detected_mood,
        "bot_message": {
            "id": bot_msg.id,
            "role": "assistant",
            "content": bot_text,
            "metadata": meta
        }
    })

@csrf_exempt
@login_required
@require_POST
def mental_health_mood_detect(request):
    """
    Real-time mood detection endpoint (separate from chat).
    Called periodically when camera is enabled.
    """
    print("=" * 60)
    print("DEBUG: Real-time mood detection endpoint called!")
    
    try:
        data = json.loads(request.body)
        image_data = data.get("image")
        
        print(f"DEBUG: Image data present: {'YES' if image_data else 'NO'}")
        
        if not image_data:
            print("DEBUG: No image data provided")
            return JsonResponse({
                "success": False,
                "detected_mood": "no image",
                "message": "No image provided"
            })
        
        # Decode image and detect mood
        img = _decode_base64_image(image_data)
        if img is None:
            print("DEBUG: Failed to decode image")
            return JsonResponse({
                "success": False,
                "detected_mood": "decode error",
                "message": "Failed to decode image"
            })
        
        print(f"DEBUG: Image decoded successfully, shape: {img.shape}")
        
        # Detect mood using DeepFace
        detected_mood = _detect_mood_from_image(img)
        print(f"DEBUG: Mood detected: {detected_mood}")
        
        return JsonResponse({
            "success": True,
            "detected_mood": detected_mood,
            "message": "Mood detected successfully"
        })
        
    except json.JSONDecodeError:
        print("DEBUG: Invalid JSON")
        return JsonResponse({
            "success": False,
            "detected_mood": "unknown",
            "message": "Invalid JSON"
        }, status=400)
    except Exception as e:
        print(f"DEBUG: Error in mood detection: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            "success": False,
            "detected_mood": "error",
            "message": str(e)[:100]
        }, status=500)

# ============================================================
# WOUND ANALYZER VIEWS (NEW)
# ============================================================

@login_required
def wound_analyzer_chat(request):
    """Dedicated UI page for the wound analyzer agent only."""
    try:
        profile = UserProfile.objects.get(user=request.user)
        profile_complete = profile.is_complete
    except UserProfile.DoesNotExist:
        profile_complete = False
    
    return render(request, "wound_analyzer.html", {
        "user": request.user,
        "profile_complete": profile_complete
    })

@csrf_exempt
@login_required
@require_POST
def analyze_wound(request):
    """
    Dedicated endpoint for wound analysis.
    Uses the wound analyzer agent specifically.
    """
    print("=" * 60)
    print("🔍 WOUND ANALYZER endpoint called!")
    
    try:
        data = json.loads(request.body)
        user_text = (data.get("content") or "").strip()
        image_data = data.get("image")
        wound_type = data.get("wound_type", "")  # Optional: burn, cut, rash, etc.
        
        print(f"🔍 Content received: '{user_text[:50]}...'")
        print(f"🔍 Image data present: {'YES' if image_data else 'NO'}")
        print(f"🔍 Wound type specified: {wound_type if wound_type else 'Not specified'}")
        
    except Exception as e:
        print(f"🔍 Error parsing request: {str(e)}")
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    if not user_text and not image_data:
        print("🔍 No content or image provided")
        return JsonResponse({"success": False, "message": "Please describe your wound or upload an image"}, status=400)

    # Create/find a dedicated conversation for wound analysis
    try:
        conversation, created = Conversation.objects.get_or_create(
            user=request.user,
            title="🩹 Wound Analysis",
            defaults={
                "is_pinned": True,
                "metadata": {"agent": "wound-analyzer"}
            }
        )
        print(f"🔍 Conversation: {conversation.id}, Created: {created}")
    except Exception as e:
        print(f"🔍 Error creating conversation: {str(e)}")
        return JsonResponse({
            "success": False,
            "message": "Error creating conversation"
        }, status=500)

    # Save user message with wound metadata
    try:
        user_msg_metadata = {}
        if wound_type:
            user_msg_metadata["wound_type"] = wound_type
        if image_data:
            user_msg_metadata["has_image"] = True
        
        user_msg = Message.objects.create(
            conversation=conversation,
            role="user",
            content=user_text if user_text else "Image upload for wound analysis",
            metadata=user_msg_metadata
        )
        print(f"🔍 User message saved: {user_msg.id}")
    except Exception as e:
        print(f"🔍 Error saving user message: {str(e)}")
        return JsonResponse({
            "success": False,
            "message": "Error saving message"
        }, status=500)

    # Build history
    try:
        recent = conversation.messages.filter(is_deleted=False).order_by("-created_at")[:10]
        history = [{"role": m.role, "content": m.content} for m in reversed(recent)]
        print(f"🔍 History built with {len(history)} messages")
    except Exception as e:
        print(f"🔍 Error building history: {str(e)}")
        history = []

    # Prepare state for wound analyzer agent
    state = {
        "user_input": user_text,
        "messages": history,
        "metadata": {
            "conversation_id": conversation.id,
            "user_id": request.user.id,
            "has_wound_image": bool(image_data),
            "wound_type": wound_type,
            "image_data": image_data[:1000] + "..." if image_data and len(image_data) > 1000 else image_data if image_data else None,
            "agent": "wound-analyzer"
        },
        "current_agent": None,
        "next_agent": None,
        "agent_output": None,
        "pending_questions": [],
    }

    # Try to call wound analyzer agent
    try:
        print("🔍 Trying to import wound_analyzer_agent")
        from agents.wound_analyzer.agent import wound_analyzer_agent
        print("🔍 Import successful, calling wound analyzer...")
        
        result = wound_analyzer_agent(state)
        
        bot_text = result.get("agent_output") or "I've analyzed your wound. Please provide more details about the symptoms you're experiencing."
        meta = result.get("metadata", {}) or {}
        meta["agent_used"] = "wound-analyzer"
        meta["has_image_analyzed"] = bool(image_data)
        
        # Extract wound analysis results
        if "wound_analysis" in result:
            meta["wound_analysis"] = result["wound_analysis"]
        if "severity" in result:
            meta["severity"] = result["severity"]
        if "urgency" in result:
            meta["urgency"] = result["urgency"]
        if "recommendations" in result:
            meta["recommendations"] = result["recommendations"]
        
        print(f"🔍 Bot response generated: {len(bot_text)} chars")
        
    except ImportError as e:
        print(f"🔍 Import error: {e}")
        # Fallback response if wound analyzer not available
        bot_text = "I'm your wound analysis assistant. I can help you understand wound care, infections, burns, cuts, and skin conditions. "
        if image_data:
            bot_text += "I see you uploaded an image. For proper wound analysis, please describe: 1) How did the injury happen? 2) When did it occur? 3) What symptoms are you experiencing (pain, swelling, redness, discharge)? 4) Do you have any fever or other systemic symptoms?"
        else:
            bot_text += "Please describe your wound in detail or upload an image for better analysis."
        
        meta = {
            "agent_used": "fallback",
            "error": "Wound analyzer agent not available",
            "has_image_analyzed": bool(image_data)
        }
    except Exception as e:
        print(f"🔍 Error in wound analyzer: {str(e)}")
        import traceback
        traceback.print_exc()
        bot_text = f"I encountered an error analyzing your wound: {str(e)[:100]}"
        meta = {
            "agent_used": "wound-analyzer",
            "error": str(e)[:100],
            "has_image_analyzed": bool(image_data)
        }

    # Save bot response
    try:
        bot_msg = Message.objects.create(
            conversation=conversation,
            role="assistant",
            content=bot_text,
            metadata=meta
        )
        print(f"🔍 Bot message saved: {bot_msg.id}")
    except Exception as e:
        print(f"🔍 Error saving bot message: {str(e)}")
        return JsonResponse({
            "success": False,
            "message": "Error saving response",
            "bot_message": {
                "content": bot_text,
                "metadata": meta
            }
        }, status=500)

    print(f"🔍 Returning successful wound analysis response")
    return JsonResponse({
        "success": True,
        "conversation_id": conversation.id,
        "has_image": bool(image_data),
        "bot_message": {
            "id": bot_msg.id,
            "role": "assistant",
            "content": bot_text,
            "metadata": meta
        }
    })

# ============================================================
# LangSmith Dashboard Views
# ============================================================

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