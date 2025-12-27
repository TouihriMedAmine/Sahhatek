from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

class User(AbstractUser):
    email = models.EmailField(unique=True, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    is_verified = models.BooleanField(default=False)  # for email/SMS verification
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    verification_code_created_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.username

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    gender = models.CharField(max_length=20, null=True, blank=True, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ])
    age = models.IntegerField(null=True, blank=True)
    chronic_diseases = models.JSONField(default=list, blank=True)  # Store as list
    blood_type = models.CharField(max_length=7, null=True, blank=True, choices=[
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('unknown', 'Unknown')
    ])
    allergies = models.JSONField(default=list, blank=True)
    medications = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s profile"
    
    @property
    def is_complete(self):
        """Check if profile has basic medical info"""
        return bool(self.gender and self.age)

# Signal to create profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()