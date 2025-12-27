from django.urls import path
from . import views

urlpatterns = [
    path('api/extract-symptoms', views.extract_symptoms_view, name='extract_symptoms'),
    path('api/start-diagnosis', views.start_diagnosis, name='start_diagnosis'),
    path('api/diagnose', views.diagnose, name='diagnose'),
    path('api/answer-question', views.answer_question, name='answer_question'),
    path('api/find-healthcare', views.find_healthcare_view, name='find_healthcare'),
    path('health', views.health, name='health'),
]
