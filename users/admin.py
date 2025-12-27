from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['username', 'email', 'phone_number', 'is_verified', 'is_staff']

admin.site.register(User, CustomUserAdmin)
