import pytest
from flask import Flask, session, url_for
from werkzeug.exceptions import Forbidden
from unittest.mock import patch, MagicMock
from website import create_app  # Replace with your actual import path

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    app.config['TESTING'] = True
    yield app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app."""
    return app.test_cli_runner()

def test_cache_headers_for_images(client):
    """Test that cache headers are added for image files."""
    # Mock a response for an image file
    with client.get('/static/test.png') as response:
        assert response.status_code == 404  # File doesn't exist, but we can check headers
        assert response.cache_control.max_age == 604800
        assert response.cache_control.no_cache is None
        assert 'ETag' in response.headers

def test_no_cache_headers_for_non_images(client):
    """Test that cache headers are not added for non-image files."""
    with client.get('/') as response:
        assert 'Cache-Control' not in response.headers or 'max-age' not in response.headers.get('Cache-Control', '')

def test_authentication_redirect_for_protected_routes(client):
    """Test that unauthenticated users are redirected to login."""
    # Try to access a protected route without logging in
    response = client.get('/topics', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.location

def test_authentication_skip_for_static_files(client):
    """Test that authentication is skipped for static files."""
    # Mock a static file request
    response = client.get('/static/test.css', follow_redirects=False)
    assert response.status_code != 302  # Not redirected

def test_admin_access_denied_for_non_admins(client):
    with client.session_transaction() as sess:
        sess['email'] = 'user@example.com'  # Regular user
    with patch('db.email_is_verified') as mock_verified:
        mock_verified.return_value = True
        with patch('db.is_admin', return_value=False):
            response = client.get('/admin', follow_redirects=True)
            assert response.status_code == 403

def test_admin_access_allowed_for_admins(client):
    """Test that admin users can access admin routes."""
    with client.session_transaction() as sess:
        sess['email'] = 'admin@example.com'  # Admin user
    
    with patch('db.is_admin', return_value=True):
        response = client.get('/admin', follow_redirects=False)
        assert response.status_code != 403  # Not forbidden (may be 404 if route doesn't exist)

def test_email_verification_redirect(client):
    """Test that unverified users are redirected to email verification."""
    with client.session_transaction() as sess:
        sess['email'] = 'user@example.com'  # Unverified user
    
    with patch('db.email_is_verified', return_value=False):
        response = client.get('/topics', follow_redirects=False)
        assert response.status_code == 302
        assert '/validate-email-message' in response.location

def test_email_verification_skip_for_verification_routes(client):
    with client.session_transaction() as sess:
        sess['email'] = 'user@example.com'  # Unverified user
    
    with patch('db.email_is_verified', return_value=False):
        # These routes should be accessible even for unverified users
        for route in ["validate_email_message", "send_verification_email"]:
            response = client.get('/' + route, follow_redirects=False)
            assert response.status_code != 302  # Not redirected

def test_no_authentication_decorator_works(client):
    """Test that routes with no_authentication decorator skip auth check."""
    # Create a test route with no_authentication decorator
    @client.application.route('/no-auth-test')
    def no_auth_test():
        return "OK"
    
    no_auth_test.no_authentication = True
    
    # Access without session
    response = client.get('/no-auth-test')
    assert response.status_code == 200
    assert response.data == b"OK"