import pytest
from unittest.mock import MagicMock, patch

# Setup Flask test app
@pytest.fixture
def app():
    from website import create_app
    app = create_app()
    app.config['TESTING'] = True
    
    yield app
    
@pytest.fixture(autouse=True)
def mock_email_verification():
    with patch('db.email_is_verified', return_value=True):
        yield

@pytest.fixture
def client(app):
    return app.test_client()

# Tests for each route
def test_login_get(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b'login' in response.data

@patch('db.test_login')
def test_login_post_success(test_login, client):
    test_login.return_value = (True, {
        "email": "test@example.com",
        "name": "Test Account"
    })

    response = client.post('/login', data={
        'email': 'test@example.com',
        'password': 'random-password'
    })
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session['email'] == 'test@example.com'

def test_login_post_failure(client):
    response = client.post('/login', data={
        'email': 'test@example.com',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Incorrect email or password.' in response.data
    with client.session_transaction() as session:
        assert 'email' not in session

def test_signout(client):
    with client.session_transaction() as session:
        session['email'] = 'christophelee2004@icloud.com'
    
    response = client.get('/signout', follow_redirects=True)
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert 'email' not in session

def test_create_account_get(client):
    response = client.get('/create-account')
    assert response.status_code == 200
    assert b'Create Account' in response.data

@patch('mail.send_verification_email')
@patch('db.add_user')
@patch('db.email_already_exists')
def test_create_account_post_success(mock_exists, mock_add, mock_send, client):
    mock_exists.return_value = False
    mock_add.return_value = None
    mock_send.return_value = None
    
    response = client.post('/create-account', data={
        'name': 'New User',
        'email': 'new@example.com',
        'password': 'newpassword'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    mock_exists.assert_called_once_with('new@example.com')
    mock_add.assert_called_once()
    mock_send.assert_called_once_with('new@example.com')
    assert b'Account successfully added' in response.data

@patch('db.email_already_exists')
def test_create_account_post_email_exists(mock_exists, client):
    mock_exists.return_value = True
    response = client.post('/create-account', data={
        'name': 'New User',
        'email': 'existing@example.com',
        'password': 'newpassword'
    })
    assert response.status_code == 200
    assert b'Email already exists' in response.data

def test_change_password_get(client):
    with client.session_transaction() as session:
        session['email'] = 'test@example.com'
    
    response = client.get('/change-password')
    assert response.status_code == 200
    assert b'<label for="new-password">New Password</label>' in response.data

@patch('db.update_password')
def test_change_password_post_success(mock_update, client):
    with client.session_transaction() as session:
        session['email'] = 'test@example.com'
    
    response = client.post('/change-password', data={
        'new-password': 'newpass',
        'confirm-password': 'newpass'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Password changed successfully' in response.data
    mock_update.assert_called_once_with('test@example.com', 'newpass')

def test_change_password_post_mismatch(client):
    with client.session_transaction() as sess:
        sess['email'] = 'test@example.com'
    
    response = client.post('/change-password', data={
        'new-password': 'newpass',
        'confirm-password': 'different'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Passwords do not match' in response.data

def test_validate_email_message(monkeypatch, client):
    with client.session_transaction() as sess:
        sess['email'] = 'test@example.com'
    response = client.get('/validate-email-message')
    assert response.status_code == 200
    assert b'Please Validate Your Email' in response.data

@patch('mail.send_verification_email')
def test_send_verification_email(mock_send, client):
    with client.session_transaction() as sess:
        sess['email'] = 'test@example.com'
    
    mock_send.return_value = None
    response = client.get('/send-verification-email')
    assert response.status_code == 200
    mock_send.assert_called_once_with('test@example.com')
    assert b'Email Sent' in response.data

@patch('db.validate_code')
def test_verify_email_valid(mock_validate, client):
    mock_validate.return_value = True
    response = client.get('/verify-email?token=validtoken')
    assert response.status_code == 200
    assert b'Thank You' in response.data
    mock_validate.assert_called_once_with('validtoken')

@patch('db.validate_code')
def test_verify_email_invalid(mock_validate, client):
    mock_validate.return_value = False
    response = client.get('/verify-email?token=invalidtoken')
    assert response.status_code == 200
    assert b'out of date' in response.data
    mock_validate.assert_called_once_with('invalidtoken')

def test_forgot_password_get(client):
    response = client.get('/forgot-password')
    assert response.status_code == 200
    assert b'forgot-password' in response.data

@patch('db.email_already_exists')
@patch('mail.send_password_reset_link')
def test_forgot_password_post_success(mock_send, mock_exists, client):
    mock_exists.return_value = True
    mock_send.return_value = None
    response = client.post('/forgot-password', data={
        'email': 'test@example.com'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Password Reset' in response.data
    mock_exists.assert_called_once_with('test@example.com')
    mock_send.assert_called_once_with('test@example.com')

@patch('db.email_already_exists')
def test_forgot_password_post_email_not_exists(mock_exists, client):
    mock_exists.return_value = False
    response = client.post('/forgot-password', data={
        'email': 'nonexistent@example.com'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Email isn&#39;t registered. " in response.data

@patch('db.reset_password_code_exists')
@patch('db.reset_password_upto_date')
def test_reset_password_get_valid(mock_upto_date, mock_exists, client):
    mock_exists.return_value = True
    mock_upto_date.return_value = True
    response = client.get('/reset-password?tokens=validtoken')
    assert response.status_code == 200
    assert b'reset-password' in response.data

@patch('db.reset_password_code_exists')
def test_reset_password_get_invalid_token(mock_exists, client):
    mock_exists.return_value = False
    response = client.get('/reset-password?tokens=invalidtoken')
    assert response.status_code == 200
    assert b'Invalid tokens' in response.data

@patch('db.reset_password_code_exists')
@patch('db.reset_password_upto_date')
def test_reset_password_get_expired_token(mock_upto_date, mock_exists, client):
    mock_exists.return_value = True
    mock_upto_date.return_value = False
    response = client.get('/reset-password?tokens=expiredtoken')
    assert response.status_code == 200
    assert b'no longer valid' in response.data

@patch('db.reset_password')
def test_reset_password_post_success(mock_reset, client):
    with patch('db.reset_password_code_exists', return_value=True), \
         patch('db.reset_password_upto_date', return_value=True):
        response = client.post('/reset-password?tokens=validtoken', data={
            'new-password': 'newpass',
            'confirm-password': 'newpass'
        }, follow_redirects=True)
        assert response.status_code == 200
        mock_reset.assert_called_once_with('validtoken', 'newpass')
        assert b'Password updated' in response.data

def test_reset_password_post_mismatch(client):
    with patch('db.reset_password_code_exists', return_value=True), patch('db.reset_password_upto_date', return_value=True):
        response = client.post('/reset-password?tokens=validtoken', data={
            'new-password': 'newpass',
            'confirm-password': 'different'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Passwords do not match' in response.data

@patch('db.get_user')
def test_edit_profile_get(mock_get, client):
    with client.session_transaction() as sess:
        sess['email'] = 'test@example.com'
    mock_get.return_value = {'email': 'test@example.com', 'name': 'Test User'}
    response = client.get('/edit-profile')
    assert response.status_code == 200
    assert b'edit-profile' in response.data
    mock_get.assert_called_once_with('test@example.com')

@patch('db.update_name')
@patch('db.update_email')
@patch('db.email_already_exists')
def test_edit_profile_post_success(mock_exists, mock_update_email, mock_update_name, client):
    with client.session_transaction() as sess:
        sess['email'] = 'old@example.com'
    
    mock_exists.return_value = False
    
    response = client.post('/edit-profile', data={
        'name': 'New Name',
        'email': 'new@example.com'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    mock_exists.assert_called_once_with('new@example.com')
    mock_update_email.assert_called_once_with('old@example.com', 'new@example.com')
    mock_update_name.assert_called_once_with('new@example.com', 'New Name')
    with client.session_transaction() as session:
        assert session['email'] == 'new@example.com'
    assert b'Account successfully updated' in response.data

@patch('db.email_already_exists')
def test_edit_profile_post_email_exists(mock_exists, client):
    with client.session_transaction() as sess:
        sess['email'] = 'old@example.com'
    
    mock_exists.return_value = True
    response = client.post('/edit-profile', data={
        'name': 'New Name',
        'email': 'existing@example.com'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Email already exists' in response.data

@patch('db.get_upload')
def test_uploads(mock_get, client):
    with client.session_transaction() as sess:
        sess['email'] = 'old@example.com'
    mock_file = MagicMock()
    mock_file.read.return_value = b'test content'
    mock_file.content_type = 'image/png'
    mock_get.return_value = mock_file
    
    response = client.get('/uploads/testfile')
    assert response.status_code == 200
    assert response.data == b'test content'
    assert response.mimetype == 'image/png'
    assert 604800 == response.cache_control.max_age
    assert response.cache_control.no_cache == None
    mock_get.assert_called_once_with('testfile')