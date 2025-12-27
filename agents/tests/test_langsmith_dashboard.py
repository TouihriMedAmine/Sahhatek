from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

class LangsmithDashboardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="pass12345")
        self.client.force_login(self.user)

    def test_dashboard_view_access(self):
        url = reverse('langsmith_dashboard')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'LangSmith', resp.content)

    def test_stats_endpoint_basic(self):
        url = reverse('langsmith_stats')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('available', data)
        self.assertIn('project', data)

    def test_agent_stats_endpoint_basic(self):
        url = reverse('langsmith_agent_stats', args=['rumor'])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('available', data)
        self.assertIn('agent', data)

    def test_runs_list_endpoint(self):
        url = reverse('langsmith_runs')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('available', data)
        self.assertIn('project', data)
        self.assertIn('runs', data)

    def test_agent_dashboard_view(self):
        url = reverse('langsmith_dashboard_agent', args=['rumor'])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Agent:', resp.content)