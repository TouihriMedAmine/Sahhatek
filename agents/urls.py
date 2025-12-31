from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat, name='chat'),
        path('api/conversations/', views.get_conversations, name='get_conversations'),
    path('api/conversations/create/', views.create_conversation, name='create_conversation'),
    path('api/conversations/<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),
    path('api/conversations/<int:conversation_id>/update/', views.update_conversation, name='update_conversation'),
    path('api/conversations/<int:conversation_id>/messages/', views.get_messages, name='get_messages'),
    path('api/conversations/<int:conversation_id>/messages/add/', views.add_message, name='add_message'),
    path('api/conversations/new/messages/add/', views.add_message, name='add_message_new'),  # For new conversations
    path('api/messages/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('api/conversations/<int:conversation_id>/process-audio/', views.process_audio_input, name='process_audio'),
    path('api/conversations/new/process-audio/', views.process_audio_input, name='process_audio_new'),  # For new conversations
    path('api/user-profile/', views.get_user_profile, name='get_user_profile'),
    path('dashboard/langsmith/', views.langsmith_dashboard, name='langsmith_dashboard'),
    path('dashboard/langsmith/agent/<str:agent_name>/', views.langsmith_dashboard_agent, name='langsmith_dashboard_agent'),
    path('api/langsmith/stats/', views.langsmith_stats, name='langsmith_stats'),
    path('api/langsmith/agent/<str:agent_name>/stats/', views.langsmith_agent_stats, name='langsmith_agent_stats'),
    path('api/langsmith/runs/', views.langsmith_runs, name='langsmith_runs'),
    path('api/langsmith/runs/<str:run_id>/', views.langsmith_run_detail, name='langsmith_run_detail'),
#mentalhealth
    path("mental/", views.mental_health_chat, name="mental_health_chat"),
    path("mental/api/send/", views.mental_health_send, name="mental_health_send"),

]