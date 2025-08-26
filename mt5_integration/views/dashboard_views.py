from django.shortcuts import render
from django.http import HttpResponse
import os

def developer_dashboard(request):
    """Serve the developer dashboard"""
    # Read the HTML file
    dashboard_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'developer_dashboard.html')
    
    try:
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='text/html')
    except FileNotFoundError:
        return HttpResponse("Dashboard file not found", status=404)
