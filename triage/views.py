
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from . import logic

# Logger
logger = logging.getLogger(__name__)

# API Views

@csrf_exempt
def extract_symptoms_view(request):
    """Extract symptoms from free-text using NER"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        
        result = logic.extract_symptoms_logic(text)
        return JsonResponse(result)
    
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Error extracting symptoms: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def start_diagnosis(request):
    """Start a new diagnostic session or update existing one"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        symptoms_text = data.get('symptoms', '')
        age_input = data.get('age', '')
        session_id = data.get('session_id')
        
        result = logic.start_diagnosis_logic(symptoms_text, age_input, session_id)
        return JsonResponse(result)
    
    except Exception as e:
        logger.error(f"Error starting diagnosis: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def diagnose(request):
    """Perform one diagnostic turn"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        
        result = logic.diagnose_logic(session_id)
        return JsonResponse(result)
    
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Error in diagnosis: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def answer_question(request):
    """Answer a diagnostic question"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        question = data.get('question', '')
        answer = data.get('answer', '')
        
        result = logic.answer_question_logic(session_id, question, answer)
        return JsonResponse(result)
    
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Error answering question: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def find_healthcare_view(request):
    """Find nearby healthcare facilities"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        illness = data.get('illness', '')
        severity = data.get('severity', '')
        confidence = data.get('confidence', 0.5)
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        location_str = data.get('location', '')
        
        result = logic.find_healthcare_logic(illness, severity, confidence, latitude, longitude, location_str)
        return JsonResponse(result)
    
    except Exception as e:
        logger.error(f"Error finding healthcare: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def health(request):
    """Health check"""
    return JsonResponse({
        'status': 'ok',
        'symptom_extractor': logic.symptom_extractor is not None,
        'sessions': len(logic.diagnostic_sessions)
    })

