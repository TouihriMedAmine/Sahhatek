import json
import random
import string
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.conf import settings
from .models import User, UserProfile

# -------------------------------------------------------
# Utility: Generate 6-digit verification code
# -------------------------------------------------------
def generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))

# -------------------------------------------------------
# SIGNUP STEP 1 — Create user + send verification code
# -------------------------------------------------------
@csrf_exempt
def signup_step1(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})

    data = json.loads(request.body.decode("utf-8"))
    username = data.get("username")
    email = data.get("email")
    phone = data.get("phone")
    password1 = data.get("password1")
    password2 = data.get("password2")

    # Validation
    if password1 != password2:
        return JsonResponse({"success": False, "message": "Passwords do not match."})

    if User.objects.filter(username=username).exists():
        return JsonResponse({"success": False, "message": "Username already exists."})

    if email and User.objects.filter(email=email).exists():
        return JsonResponse({"success": False, "message": "Email already used."})

    # Generate code
    code = generate_verification_code()

    # Store signup data in session (temporary storage)
    request.session['signup_data'] = {
        "username": username,
        "email": email,
        "phone": phone,
        "password": password1,
        "code": code,
        "code_created_at": timezone.now().isoformat()
    }

    # Send code via email
    if email:
        try:
            send_mail(
                subject="Your Sahatek Verification Code",
                message=f"""Welcome to Sahatek!
                
Your verification code is: {code}
                
This code will expire in 10 minutes.
                
Thank you for choosing Sahatek for your medical assistance needs.
                
Best regards,
Sahatek Team""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Email sending failed: {e}")
            return JsonResponse({
                "success": False, 
                "message": "Failed to send verification email. Please check your email address."
            })

    return JsonResponse({
        "success": True,
        "message": "Verification code sent to your email. Enter it to complete signup."
    })

# -------------------------------------------------------
# SIGNUP STEP 2 — Verify code and activate account
# -------------------------------------------------------
@csrf_exempt
def verify_code(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})

    data = json.loads(request.body.decode("utf-8"))
    code = data.get("code")

    signup_data = request.session.get('signup_data')
    if not signup_data:
        return JsonResponse({"success": False, "message": "No signup in progress."})

    # Check code validity (10 min)
    code_created_at = timezone.datetime.fromisoformat(signup_data['code_created_at'])
    if signup_data['code'] != code:
        return JsonResponse({"success": False, "message": "Invalid code."})

    if timezone.now() > code_created_at + timedelta(minutes=10):
        return JsonResponse({"success": False, "message": "Code expired."})

    # Create user
    try:
        user = User.objects.create_user(
            username=signup_data['username'],
            email=signup_data['email'],
            password=signup_data['password']
        )
        
        # Add phone number
        if signup_data['phone']:
            user.phone_number = signup_data['phone']
        
        # Mark as verified
        user.is_verified = True
        user.save()
        
        # Profile is automatically created via signal
        
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Error creating user: {str(e)}"})

    # Login user
    login(request, user)

    # Clear session
    del request.session['signup_data']

    return JsonResponse({
        "success": True, 
        "message": "Account verified and created successfully.",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone_number,
            "profile_complete": False  # Flag for frontend onboarding
        }
    })

# -------------------------------------------------------
# RESEND CODE
# -------------------------------------------------------
@csrf_exempt
def resend_code(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})

    # Get signup data from session (user doesn't exist yet during signup)
    signup_data = request.session.get('signup_data')
    if not signup_data:
        return JsonResponse({"success": False, "message": "No signup in progress. Please start over."})

    # Generate new code
    code = generate_verification_code()
    
    # Update session with new code
    signup_data['code'] = code
    signup_data['code_created_at'] = timezone.now().isoformat()
    request.session['signup_data'] = signup_data
    request.session.modified = True

    # Send code via email
    email = signup_data.get('email')
    if email:
        try:
            send_mail(
                subject="Your New Sahatek Verification Code",
                message=f"""Your new verification code is: {code}
                
This code will expire in 10 minutes.
                
If you didn't request this code, please ignore this email.
                
Best regards,
Sahatek Team""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Email sending failed: {e}")
            return JsonResponse({
                "success": False, 
                "message": "Failed to send verification email. Please check your email address."
            })

    return JsonResponse({"success": True, "message": "New verification code sent to your email."})

# -------------------------------------------------------
# LOGIN
# -------------------------------------------------------
@csrf_exempt
def login_user(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})

    data = json.loads(request.body.decode("utf-8"))
    username = data.get("username")
    password = data.get("password")
    remember_me = data.get("remember_me", False)

    user = authenticate(request, username=username, password=password)

    if user is None:
        return JsonResponse({"success": False, "message": "Invalid username or password."})

    if not user.is_verified:
        return JsonResponse({"success": False, "message": "Please verify your account first."})

    login(request, user)
    
    # Set session expiry
    if not remember_me:
        request.session.set_expiry(0)  # Browser session
    else:
        request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days

    # Check profile completion
    try:
        profile = UserProfile.objects.get(user=user)
        profile_complete = profile.is_complete
    except UserProfile.DoesNotExist:
        profile_complete = False

    return JsonResponse({
        "success": True, 
        "message": "Login successful.",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone_number,
            "profile_complete": profile_complete
        }
    })

# -------------------------------------------------------
# LOGOUT
# -------------------------------------------------------
@csrf_exempt
def logout_user(request):
    from django.contrib.auth import logout
    logout(request)
    return JsonResponse({"success": True, "message": "Logged out successfully."})

# -------------------------------------------------------
# GET CURRENT USER (for chat initialization)
# -------------------------------------------------------
@csrf_exempt
def get_current_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "message": "Not authenticated"}, status=401)
    
    user = request.user
    try:
        profile = UserProfile.objects.get(user=user)
        profile_data = {
            "gender": profile.gender,
            "age": profile.age,
            "chronic_diseases": profile.chronic_diseases,
            "blood_type": profile.blood_type,
            "allergies": profile.allergies,
            "medications": profile.medications,
            "completed": profile.is_complete,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None
        }
    except UserProfile.DoesNotExist:
        profile_data = {
            "gender": None,
            "age": None,
            "chronic_diseases": [],
            "blood_type": None,
            "allergies": [],
            "medications": [],
            "completed": False,
            "created_at": None,
            "updated_at": None
        }
    
    return JsonResponse({
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone_number,
            "is_verified": user.is_verified,
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
            "profile": profile_data
        }
    })

# -------------------------------------------------------
# UPDATE PROFILE (with onboarding data)
# -------------------------------------------------------
@csrf_exempt
def update_profile(request):
    if request.method == "GET":
        # Return current profile data
        if not request.user.is_authenticated:
            return JsonResponse({"success": False, "message": "Not authenticated"}, status=401)
        
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
                    "is_complete": profile.is_complete,
                    "created_at": profile.created_at.isoformat() if profile.created_at else None,
                    "updated_at": profile.updated_at.isoformat() if profile.updated_at else None
                }
            })
        except UserProfile.DoesNotExist:
            return JsonResponse({
                "success": True,
                "profile": None
            })
    
    elif request.method == "POST":
        if not request.user.is_authenticated:
            return JsonResponse({"success": False, "message": "Not authenticated"}, status=401)

        try:
            data = json.loads(request.body.decode("utf-8"))
            user = request.user
            
            # Update user fields
            if 'username' in data and data['username'] != user.username:
                username = data['username']
                if User.objects.filter(username=username).exclude(id=user.id).exists():
                    return JsonResponse({"success": False, "message": "Username already taken."})
                user.username = username
            
            if 'email' in data and data['email'] != user.email:
                email = data['email']
                if User.objects.filter(email=email).exclude(id=user.id).exists():
                    return JsonResponse({"success": False, "message": "Email already taken."})
                user.email = email
            
            if 'phone' in data:
                user.phone_number = data['phone']
            
            if 'password' in data and data['password']:
                user.set_password(data['password'])
            
            user.save()
            
            # Get or create profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # Update profile fields (onboarding/medical data)
            profile_fields = ['gender', 'age', 'blood_type']
            json_fields = ['chronic_diseases', 'allergies', 'medications']
            
            for field in profile_fields:
                if field in data:
                    setattr(profile, field, data[field])
            
            for field in json_fields:
                if field in data:
                    if isinstance(data[field], list):
                        setattr(profile, field, data[field])
                    elif data[field]:
                        # Handle single value
                        setattr(profile, field, [data[field]])
            
            profile.save()
            
            # Re-login the user if password was changed
            if 'password' in data and data['password']:
                login(request, user)

            return JsonResponse({
                "success": True, 
                "message": "Profile updated successfully.",
                "profile_complete": profile.is_complete,
                "profile": {
                    "gender": profile.gender,
                    "age": profile.age,
                    "chronic_diseases": profile.chronic_diseases,
                    "blood_type": profile.blood_type,
                    "allergies": profile.allergies,
                    "medications": profile.medications
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "Invalid JSON data."}, status=400)
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)
    
    return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

# -------------------------------------------------------
# GET PROFILE STATUS (for chat to check onboarding)
# -------------------------------------------------------
@csrf_exempt
def get_profile_status(request):
    """Quick endpoint to check if profile is complete for onboarding"""
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "message": "Not authenticated"}, status=401)
    
    try:
        profile = UserProfile.objects.get(user=request.user)
        return JsonResponse({
            "success": True,
            "profile_complete": profile.is_complete,
            "has_profile": True
        })
    except UserProfile.DoesNotExist:
        return JsonResponse({
            "success": True,
            "profile_complete": False,
            "has_profile": False
        })
    





# ------------------------------ DASHBOARD --------------------------------------
import json
from collections import Counter

from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .models import UserProfile
from agents.models import Conversation, Message  # ✅ your chat models are in agents/models.py


@login_required
def dashboard_page(request):
    """Renders the dashboard UI (dashboard.html)"""
    return render(request, "dashboard.html")


@login_required
def dashboard_data(request):
    """Returns dashboard data as JSON (used by dashboard.html JS)"""
    user = request.user

    # -------------------------
    # Profile data
    # -------------------------
    try:
        profile = UserProfile.objects.get(user=user)
        profile_data = {
            "gender": profile.gender,
            "age": profile.age,
            "blood_type": profile.blood_type,
            "chronic_diseases": profile.chronic_diseases or [],
            "allergies": profile.allergies or [],
            "medications": profile.medications or [],
            "chronic_diseases_count": len(profile.chronic_diseases or []),
            "allergies_count": len(profile.allergies or []),
            "medications_count": len(profile.medications or []),
            "is_complete": profile.is_complete,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }
    except UserProfile.DoesNotExist:
        profile_data = {
            "gender": None,
            "age": None,
            "blood_type": None,
            "chronic_diseases": [],
            "allergies": [],
            "medications": [],
            "chronic_diseases_count": 0,
            "allergies_count": 0,
            "medications_count": 0,
            "is_complete": False,
            "updated_at": None,
        }

    # -------------------------
    # Chat totals (REAL)
    # -------------------------
    conv_qs = Conversation.objects.filter(user=user, is_deleted=False)
    total_conversations = conv_qs.count()

    msg_qs = Message.objects.filter(conversation__user=user, is_deleted=False)
    total_messages = msg_qs.count()

    # -------------------------
    # Chat analytics (only works if Message has metadata field)
    # Your agents/views.py tries to store it but ignores if field doesn't exist. :contentReference[oaicite:3]{index=3}
    # -------------------------
    agents_counter = Counter()
    intent_counter = Counter()
    urgency_counter = Counter()

    def safe_load_meta(m):
        # Works only if Message has metadata attribute
        if not hasattr(m, "metadata"):
            return {}
        raw = getattr(m, "metadata", None)
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except Exception:
            return {}

    assistant_qs = msg_qs.filter(role="assistant")

    for m in assistant_qs:
        meta = safe_load_meta(m)

        # agent_used
        agent = meta.get("agent_used") or "unknown"
        agents_counter[str(agent)] += 1

        # intent & emergency
        lang_state = meta.get("langgraph_state") or {}
        intent = lang_state.get("intent")
        emergency = lang_state.get("emergency_level")

        if intent:
            intent_counter[str(intent)] += 1
        if emergency:
            urgency_counter[str(emergency)] += 1

        # fallback gatekeeper decision (optional)
        gk = meta.get("gatekeeper_decision") or {}
        if not emergency and gk.get("emergency_level"):
            urgency_counter[str(gk["emergency_level"])] += 1

    agents_usage = [{"name": k, "count": v} for k, v in agents_counter.most_common()]
    top_topics = [{"topic": k, "count": v} for k, v in intent_counter.most_common(8)]
    urgency_counts = [{"level": k, "count": v} for k, v in urgency_counter.most_common()]

    dashboard = {
        "account": {
            "username": user.username,
            "email": user.email,
            "phone": getattr(user, "phone_number", None),
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        },
        "profile": profile_data,
        "chat": {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "agents_usage": agents_usage,
            "top_topics": top_topics,
            "urgency_counts": urgency_counts,
        }
    }

    return JsonResponse({"success": True, "dashboard": dashboard})






#----------------------------PROFILE UPDATE-----------------------------
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import UserProfile

@login_required
def profile_edit_page(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # ✅ Put blood type choices here (not in template)
    blood_choices = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"]

    if request.method == "POST":
        gender = request.POST.get("gender") or None
        age_raw = (request.POST.get("age") or "").strip()
        blood_type = request.POST.get("blood_type") or None

        chronic_text = (request.POST.get("chronic_diseases") or "").strip()
        allergies_text = (request.POST.get("allergies") or "").strip()
        meds_text = (request.POST.get("medications") or "").strip()

        def to_list(text: str):
            if not text:
                return []
            return [x.strip() for x in text.split(",") if x.strip()]

        profile.gender = gender
        profile.age = int(age_raw) if age_raw.isdigit() else None
        profile.blood_type = blood_type

        profile.chronic_diseases = to_list(chronic_text)
        profile.allergies = to_list(allergies_text)
        profile.medications = to_list(meds_text)

        profile.save()
        return redirect("/auth/dashboard/")

    return render(request, "profile_edit.html", {
        "profile": profile,
        "blood_choices": blood_choices
    })
