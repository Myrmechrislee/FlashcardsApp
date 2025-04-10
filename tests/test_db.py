import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from bson import ObjectId
from werkzeug.datastructures import FileStorage
from io import BytesIO
import db as db
from db import SecurityLogSeverity

@pytest.fixture
def mock_db():
    """Fixture to mock MongoDB operations."""
    with patch('db.db') as mock_db:
        yield mock_db

@pytest.fixture
def mock_fs():
    """Fixture to mock GridFS operations."""
    with patch('db.fs') as mock_fs:
        yield mock_fs

@pytest.fixture
def mock_user():
    """Fixture for a sample user document."""
    return {
        "_id": ObjectId(),
        "email": "test@example.com",
        "password_hash": "hashed_password",
        "name": "Test User",
        "topics": [ObjectId(), ObjectId()],
        "profile_pic": "",
        "quizes": [ObjectId(), ObjectId()],
        "email_confirmed": False,
        "is_admin": False
    }

@pytest.fixture
def mock_topic():
    """Fixture for a sample topic document."""
    return {
        "_id": ObjectId(),
        "title": "Sample Topic",
        "questions": [
            {"id": 0, "question": "Q1", "answer": "A1", "confidence": 0},
            {"id": 1, "question": "Q2", "answer": "A2", "confidence": 1}
        ]
    }

@pytest.fixture
def mock_quiz():
    """Fixture for a sample quiz document."""
    return {
        "_id": ObjectId(),
        "topic_id": ObjectId(),
        "questions": [
            {"id": 0, "correct": True},
            {"id": 1, "correct": False},
            {"id": 2, "correct": True}
        ],
        "time-start": datetime.now(),
        "time-end": datetime.now() + timedelta(minutes=10)
    }

def test_hash_password():
    """Test that password hashing produces consistent results."""
    password = "testpassword"
    hashed = db.hash_password(password)
    assert isinstance(hashed, str)
    assert len(hashed) == 32  # MD5 hash length
    # Should produce same output for same input
    assert db.hash_password(password) == hashed

def test_get_user(mock_db, mock_user):
    """Test retrieving a user by email."""
    mock_db.users.find_one.return_value = mock_user
    result = db.get_user("test@example.com")
    assert result == mock_user
    mock_db.users.find_one.assert_called_once_with({"email": "test@example.com"})

def test_email_already_exists(mock_db):
    """Test checking if email exists."""
    # Test when email exists
    mock_db.users.find_one.return_value = {"email": "exists@example.com"}
    assert db.email_already_exists("exists@example.com") is True
    
    # Test when email doesn't exist
    mock_db.users.find_one.return_value = None
    assert db.email_already_exists("nonexistent@example.com") is False

def test_test_login_success(mock_db, mock_user):
    """Test successful login."""
    mock_db.users.find_one.return_value = mock_user
    success, user = db.test_login("test@example.com", "127.0.0.1", "password")
    assert success is True
    assert user == mock_user
    # Should have created a security log
    assert mock_db.security_logs.insert_one.called

def test_test_login_failure(mock_db):
    """Test failed login."""
    mock_db.users.find_one.return_value = None
    success, user = db.test_login("wrong@example.com", "127.0.0.1", "wrong")
    assert success is False
    assert user == ""
    # Should have created a security log
    assert mock_db.security_logs.insert_one.called

def test_add_user(mock_db):
    """Test adding a new user."""
    db.add_user("New User", "new@example.com", "password", "127.0.0.1")
    mock_db.users.insert_one.assert_called_once()
    # Should have created a security log
    assert mock_db.security_logs.insert_one.called

def test_update_profile_picture(mock_db, mock_fs):
    """Test updating profile picture."""
    mock_file = FileStorage(
        stream=BytesIO(b"fake image data"),
        filename="profile.jpg",
        content_type="image/jpeg"
    )
    mock_fs.put.return_value = "file_id_123"
    
    db.update_profile_picture("test@example.com", mock_file)
    mock_fs.put.assert_called_once()
    mock_db.users.update_one.assert_called_once_with(
        {"email": "test@example.com"},
        {"$set": {"profile_pic": "file_id_123"}}
    )

def test_get_topics(mock_db, mock_user, mock_topic):
    """Test retrieving topics for a user."""
    mock_db.users.find_one.return_value = mock_user
    mock_db.topics.find.return_value.to_list.return_value = [mock_topic]
    
    topics = db.get_topics("test@example.com")
    assert len(topics) == 1
    assert topics[0]["title"] == "Sample Topic"

def test_has_access_to_topic(mock_db, mock_user):
    """Test checking topic access."""
    topic_id = ObjectId()
    mock_user["topics"].append(topic_id)
    mock_db.users.find_one.return_value = mock_user
    
    assert db.has_access_to_topic("test@example.com", str(topic_id)) is True
    assert db.has_access_to_topic("test@example.com", str(ObjectId())) is False

def test_add_topic(mock_db, mock_user):
    """Test adding a new topic."""
    mock_db.users.find_one.return_value = mock_user
    mock_db.topics.insert_one.return_value.inserted_id = ObjectId()
    
    db.add_topic(
        "test@example.com",
        "New Topic",
        ["Q1", "Q2"],
        ["A1", "A2"]
    )
    
    assert mock_db.topics.insert_one.called
    assert mock_db.users.update_one.called

def test_edit_topic(mock_db, mock_topic):
    """Test editing a topic."""
    mock_db.topics.find_one.return_value = mock_topic
    
    # Mock form data (simulating Flask request.form)
    class MockForm:
        def getlist(self, field):
            if field == 'questions[]':
                return ["Edited Q1", "Edited Q2"]
            elif field == 'answers[]':
                return ["Edited A1", "Edited A2"]
            elif field == 'confidence[]':
                return ["1", "2"]
            return None
        def __getitem__(self, key):
            return "Edited Title"
    
    db.edit_topic(str(mock_topic["_id"]), MockForm())
    assert mock_db.topics.update_one.called

def test_delete_topic(mock_db, mock_topic):
    """Test deleting a topic."""
    mock_db.topics.find_one.return_value = mock_topic
    db.delete_topic(str(mock_topic["_id"]))
    assert mock_db.backupTopics.insert_one.called
    assert mock_db.topics.delete_one.called

def test_email_is_verified(mock_db, mock_user):
    """Test checking email verification status."""
    # Test verified
    mock_user["email_confirmed"] = True
    mock_db.users.find_one.return_value = mock_user
    assert db.email_is_verified("test@example.com") is True
    
    # Test unverified
    mock_user["email_confirmed"] = False
    mock_db.users.find_one.return_value = mock_user
    assert db.email_is_verified("test@example.com") is False

def test_set_verification_code(mock_db):
    """Test setting verification code."""
    code = db.set_verification_code("test@example.com")
    assert len(code) == 32  # 16 bytes hex encoded
    mock_db.users.update_one.assert_called_once()

def test_validate_code(mock_db, mock_user):
    """Test validating verification code."""
    # Test valid code
    mock_db.users.find_one.return_value = mock_user
    assert db.validate_code("valid_code") is True
    assert mock_db.users.update_one.called
    
    # Test invalid code
    mock_db.users.find_one.return_value = None
    assert db.validate_code("invalid_code") is False

def test_generate_quiz(mock_db, mock_user):
    """Test generating a quiz."""
    mock_db.users.find_one.return_value = mock_user
    mock_db.quizes.insert_one.return_value.inserted_id = ObjectId()
    
    quiz_id = db.generate_quiz("test@example.com", str(ObjectId()), [1, 2, 3])
    assert isinstance(quiz_id, ObjectId)
    assert mock_db.quizes.insert_one.called
    assert mock_db.users.update_one.called

def test_get_quiz_stats(mock_db, mock_quiz):
    """Test getting quiz statistics."""
    mock_db.quizes.find_one.return_value = mock_quiz
    stats = db.get_quiz_stats(str(mock_quiz["_id"]))
    
    assert stats["total_questions"] == 3
    assert stats["correct_answers"] == 2
    assert 66.66 < stats["accuracy"] < 66.67  # 2/3 ≈ 66.666...

def test_get_streak(mock_db, mock_quiz):
    """Test getting correct answer streak."""
    mock_db.quizes.find_one.return_value = mock_quiz
    streak = db.get_streak(str(mock_quiz["_id"]))
    assert streak == 1  # Last answer was correct, previous was wrong

def test_create_security_log(mock_db):
    """Test creating a security log."""
    db.create_security_log(
        "Test Event",
        "test@example.com",
        "127.0.0.1",
        "Test details",
        SecurityLogSeverity.High
    )
    mock_db.security_logs.insert_one.assert_called_once()

def test_search_security_logs(mock_db):
    """Test searching security logs."""
    mock_db.security_logs.find.return_value.sort.return_value.to_list.return_value = [
        {"event": "Login", "severity": 0, "timestamp": datetime.now()}
    ]
    
    # Test search with severity filter
    logs = db.search_security_logs(search="login", severity="info")
    assert len(logs) == 1
    assert logs[0]["severity"] == "Info"

def test_is_admin(mock_db, mock_user):
    """Test checking admin status."""
    # Test non-admin
    mock_db.users.find_one.return_value = mock_user
    assert db.is_admin("test@example.com") is False
    
    # Test admin
    mock_user["is_admin"] = True
    mock_db.users.find_one.return_value = mock_user
    assert db.is_admin("test@example.com") is True

def test_update_user(mock_db, mock_user):
    """Test updating user information."""
    mock_db.users.find_one.return_value = mock_user
    
    # Mock request object
    class MockRequest:
        form = {
            'name': 'Updated Name',
            'email': 'updated@example.com',
            'password': 'newpassword',
            'is_admin': 'on',
            'email_confirmed': 'on'
        }
        files = {'profile_pic': FileStorage(
            stream=BytesIO(b"fake image data"),
            filename="profile.jpg"
        )}
    
    db.edit_user(str(mock_user["_id"]), MockRequest())
    assert mock_db.users.update_one.called
    # Should have updated password if provided
    assert "password_hash" in mock_db.users.update_one.call_args[0][1]["$set"]

def test_reset_password_flow(mock_db, mock_user):
    """Test the reset password flow."""
    # Test setting reset link
    code = db.set_reset_password_link("test@example.com")
    assert "/reset-password?tokens=" in code
    assert mock_db.users.update_one.called
    
    # Test checking code exists
    mock_db.users.find_one.return_value = mock_user
    assert db.reset_password_code_exists("testcode") is True
    mock_db.users.find_one.return_value = None
    assert db.reset_password_code_exists("badcode") is False
    
    # Test resetting password
    db.reset_password("testcode", "newpassword")
    assert mock_db.users.update_one.called
    assert "password_hash" in mock_db.users.update_one.call_args[0][1]["$set"]