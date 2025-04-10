import pytest
from unittest.mock import MagicMock, patch
from flask import template_rendered, Flask

# Setup Flask test app
@pytest.fixture
def app():
    from website import create_app
    app = create_app()
    app.config['TESTING'] = True
    
    yield app

# Fixture to create a test client
@pytest.fixture
def client(app):
    return app.test_client()

# Fixture to capture rendered templates
@pytest.fixture
def captured_templates(app):
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)

# Test routes that should return 200 OK
@pytest.mark.parametrize('route, template', [
    ('/', 'visitors/index.html'),
    ('/about', 'visitors/about.html'),
    ('/privacy', 'visitors/privacy.html'),
    ('/terms', 'visitors/terms.html'),
    ('/contact', 'visitors/contact-us.html'),
])
def test_visitor_routes(client, captured_templates, route, template):
    response = client.get(route)
    assert response.status_code == 200
    assert len(captured_templates) == 1
    assert captured_templates[0][0].name == template

# Test contact form submission
def test_contact_form_submission(client, captured_templates):
    with patch('mail.send_contact_email') as mock_send:
        # Test successful submission
        response = client.post('/contact', data={
            'name': 'Test User',
            'email': 'test@example.com',
            'subject': 'Test Subject',
            'message': 'Test message content'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Thank you for your message' in response.data
        mock_send.assert_called_once_with(
            'Test Subject',
            'From: Test User\nEmail: test@example.com\nMessage: Test message content'
        )
        
        # Verify the correct template was rendered
        assert len(captured_templates) == 1
        assert captured_templates[0][0].name == 'visitors/contact-us.html'

# Test GET request to contact page
def test_contact_page_get(client, captured_templates):
    response = client.get('/contact')
    assert response.status_code == 200
    assert len(captured_templates) == 1
    assert captured_templates[0][0].name == 'visitors/contact-us.html'