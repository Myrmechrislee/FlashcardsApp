import pytest
from werkzeug.exceptions import NotFound, Forbidden, InternalServerError
from unittest.mock import patch, MagicMock, ANY
import db
from website.errors import bp as error_blueprint
@pytest.fixture
def app():
    from website import create_app
    app = create_app()
    app.config['TESTING'] = True
    
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

def test_404_handler(client):
    # Simulate a 404 error
    response = client.get('/nonexistent-route')
    
    assert response.status_code == 404
    # Assuming your 404.html template contains this text
    assert b"Page Not Found" in response.data

@patch('db.email_is_verified')
@patch('db.is_admin')
@patch('db.create_security_log')
def test_403_handler(mock_create_log, mock_is_admin, mock_email_is_verified, client):
    mock_is_admin.return_value = False
    mock_email_is_verified.return_value = True
    # mock_email_is_verified = 
    # Simulate a 403 error
    with client:
        # Set up session if needed
        with client.session_transaction() as sess:
            sess['email'] = 'test@example.com'
        
        response = client.get('/admin/', follow_redirects=True)
    
    assert response.status_code == 403
    assert b"Forbidden" in response.data
    
    # Verify security log was created
    mock_create_log.assert_called_once_with(
        'Attempted Forbidden Access',
        'test@example.com',
        '127.0.0.1',
        details='There has been an restricted attempted access to http://localhost/admin/',
        severity=db.SecurityLogSeverity.High
    )

@patch('db.email_is_verified')
@patch('mail.send_error_email')
def test_500_handler(mock_send_email, mock_email_is_verified, client, app):
    mock_email_is_verified.return_value = True
    with client:
        # Set up session
        with client.session_transaction() as sess:
            sess['email'] = 'test@example.com'
        
        # Trigger 500 by accessing a route that raises an error
        # Or test the handler directly
        response = client.get('/MakeInternalServerError')
    
    assert response.status_code == 500  # (template, status_code)
    assert b"Internal Server Error" in response.data
    
    # Verify error email was sent
    mock_send_email.assert_called_once_with('test@example.com', ANY, ANY)

def test_403_handler_without_session(client):
    """Test 403 handler when user is not logged in (no session email)"""
    with patch('db.create_security_log') as mock_create_log:
        response = client.get('/admin/', follow_redirects=True)
        
        assert response.status_code == 200
        assert b"Login" in response.data

def test_500_handler_without_session(client):
    """Test 500 handler when user is not logged in (no session email)"""
    test_error = InternalServerError()
    
    with patch('mail.send_error_email') as mock_send_email:
        response = client.get('/MakeInternalServerError')
        
        assert response.status_code == 500
        # Verify no email was sent (since no email in session)
        mock_send_email.assert_called_once_with('not signed in', ANY, ANY)