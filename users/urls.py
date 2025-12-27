from django.urls import path
from . import views
#DASHBOARD
from .views import dashboard_page, dashboard_data
#profile
from .views import profile_edit_page

urlpatterns = [
    path('signup/', views.signup_step1, name='signup'),
    path('verify/', views.verify_code, name='verify_code'),
    path('resend-code/', views.resend_code, name='resend_code'),
    path('login/', views.login_user, name='login_user'),
    path('logout/', views.logout_user, name='logout_user'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('current-user/', views.get_current_user, name='get_current_user'),  # New
    #DASHBOARD
    path("dashboard/", dashboard_page, name="dashboard"),
    path("dashboard/data/", dashboard_data, name="dashboard_data"),
    #Profile
    path("profile/edit/", profile_edit_page, name="profile_edit"),
]