from django.test import TestCase, Client
from django.urls import reverse
import json

class TriageApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_endpoint(self):
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ok')
        # Check if symptom extractor initialized (might be False if models missing, but key should exist)
        self.assertIn('symptom_extractor', data)

    def test_extract_symptoms(self):
        url = reverse('extract_symptoms')
        data = {'text': 'I have a headache and fever'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertIn('symptoms', response_data)
        # We don't assert validity of extraction as models might not be loaded in test env efficiently
        # but we check structure

    def test_start_diagnosis(self):
        url = reverse('start_diagnosis')
        data = {
            'symptoms': 'headache',
            'age': '25'
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertIn('session_id', response_data)
        self.assertIn('symptoms', response_data)

    def test_invalid_method(self):
        url = reverse('extract_symptoms')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
