import os, hashlib, secrets
from pymongo import MongoClient
import gridfs
from bson import ObjectId
from datetime import datetime, timedelta

client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/flashcards"))
db = client.get_database()
salt = "558f455d7315ce54148b6f0628ae6f3f"
fs = gridfs.GridFS(db)

def hash_password(password):
    return hashlib.md5((salt + password).encode()).hexdigest()
def get_user(email):
    return db.users.find_one({"email": email})

def get_upload(file_id):
    return fs.get(ObjectId(file_id))
def update_confidence(tid, qid, c):
    return db.topics.update_one({
        "_id": ObjectId(tid),
        "questions.id": qid
        }, 
        {
            "$set": {"questions.$.confidence": c}
        })
def get_topics(email):
    user = get_user(email)
    topic_ids = user["topics"]
    topics = db.topics.find({"_id": {"$in": topic_ids}})
    return topics.to_list()

def has_access_to_topic(email, tid):
    return ObjectId(tid) in get_user(email)["topics"]
def get_topic(id):
    topics = db.topics.find_one({"_id": ObjectId(id)})
    return topics

def add_topic(email, title, questions, answers):
    questions_data = []
    for i, (q, a) in enumerate(zip(questions, answers)):
        questions_data.append(
            {
                "id": i,
                "question": q, 
                "answer": a,
                "confidence": 0
            }
        )
    data = {
        "title": title,
        "questions": questions_data
    }
    res = db.topics.insert_one(data)
    
    db.users.update_one({"email": email}, {"$push": {"topics": res.inserted_id}})
def edit_topic(id, form_data):
    data = get_topic(id)
    data['title'] = form_data['title']
    
    questions = []
    for q_id, (question, answer, confidence) in enumerate(zip( 
                                       form_data.getlist('questions[]'), 
                                       form_data.getlist('answers[]'), form_data.getlist('confidence[]'))):
        questions.append({
            "id": q_id,
            "question": question,
            "answer": answer,
            "confidence": int(confidence)
        })
    data["questions"] = questions
    db.topics.update_one({"_id": data["_id"]}, {"$set": data})

def delete_topic(id):
    topic = get_topic(id)
    db.backupTopics.insert_one(topic)
    db.topics.delete_one(topic)

def import_topic(email, title, df):
    if "id" not in df.columns:
        df["id"] = range(len(df))
    df["confidence"] = df.get("confidence", 0)
    df = df[["id", "question", "answer", "confidence"]]
    questions = df.to_dict(orient="records")
    data = {
        "title": title,
        "questions": questions
    }
    res = db.topics.insert_one(data)
    db.users.update_one({"email": email}, {"$push": {"topics": res.inserted_id}})
    return len(questions)

def test_login(email, password):
    password_hash = hash_password(password)
    user = db.users.find_one({"email": email, "password_hash": password_hash})
    if user == None: 
        return False, "" 
    else: 
        return True, user

def add_user(name, email, password):
    password_hash = hash_password(password)
    db.users.insert_one({
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "topics": [],
        "profile_pic": "",
        "quizes": [],
        'email_confirmed': False,
        'is_admin': False
    })

def update_profile_picture(email, profile_pic):
    file_id = fs.put(profile_pic, filename=profile_pic.filename, content_type=profile_pic.content_type)
    db.users.update_one({"email": email}, {"$set": {"profile_pic": file_id}})

def email_already_exists(email):
    return db.users.find_one({"email": email}) != None

def update_email(email_old, email_new):
    return db.users.update_one({"email": email_old}, {"$set": {"email": email_new}})

def update_name(email, name):
    return db.users.update_one({"email": email}, {"$set": {"name": name}})

def update_password(email, password):
    password_hash = hash_password(password)
    return db.users.update_one({"email": email}, {"$set": {"password_hash": password_hash}})

def has_access_to_quiz(email, quizid):
    return ObjectId(quizid) in db.users.find_one({"email": email})["quizes"]
def generate_quiz(email, tid, questions):
    id = db.quizes.insert_one({
        'topic_id': ObjectId(tid),
        'questions': questions,
        'time-start': datetime.now(),
        'expiresAt': datetime.utcnow() + timedelta(days=1)
    }).inserted_id
    db.users.update_one({'email': email}, {'$push': {'quizes': id}})
    return id

def get_quiz(quizid):
    return db.quizes.find_one({'_id': ObjectId(quizid)})

def update_quiz_response(quizid, questionid, is_correct):
    db.quizes.update_one({'_id': ObjectId(quizid), "questions.id": int(questionid)}, {"$set": {'questions.$.correct': is_correct}})
    remaining = [q for q in get_quiz(quizid)['questions'] if 'correct' not in q.keys()]
    if len(remaining) > 0:
        return remaining[0]
    return None

def finish_quiz(quizid):
    db.quizes.update_one({'_id': ObjectId(quizid)}, {"$set": {"time-end": datetime.now()}})
def get_quiz_stats(quizid):
    quiz = get_quiz(quizid)
    questions = quiz['questions']
    correct = len([q for q in questions if q['correct']])
    total_questions = len(questions)
    return {
        'tid': quiz['topic_id'],
        'time_taken': format_timedelta(quiz['time-end'] - quiz['time-start']),
        'total_questions': total_questions,
        'correct_answers': correct,
        'accuracy': correct / float(total_questions) * 100
    }

def format_timedelta(td):
    """Convert a timedelta object into a human-readable string."""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours} hours, {minutes} minutes, and {seconds} seconds"
    elif minutes > 0:
        return f"{minutes} minutes and {seconds} seconds"
    else:
        return f"{seconds} seconds"

def email_is_verified(email):
    return db.users.find_one({'email': email})['email_confirmed']

def set_verification_code(email):
    code = secrets.token_hex(16)
    db.users.update_one({'email': email}, {'$set': {'verification_code': code}})
    return code

def validate_code(code):
    user = db.users.find_one({'verification_code': code})
    if not user:
        return False
    db.users.update_one({'email': user['email']}, {'$set': {'email_confirmed': True}})
    return True

def set_reset_password_link(email):
    code = secrets.token_hex(16)
    db.users.update_one({'email': email}, {'$set': {
        'reset_password_code': code,
        'reset_password_code_time': datetime.now()
    }})
    return '/reset-password?tokens=' + code

def reset_password_code_exists(code):
    user = db.users.find_one({'reset_password_code': code})
    return user != None

def reset_password_upto_date(code):
    user = db.users.find_one({'reset_password_code': code})
    return (datetime.now() - user['reset_password_code_time']) < timedelta(minutes=5)

def reset_password(code, new_password):
    password_hash = hash_password(new_password)
    db.users.update_one({'reset_password_code': code}, {'$set': {'password_hash':password_hash}})

def get_streak(quizid):
    quiz = get_quiz(quizid)
    questions = quiz['questions']
    questions_answered = [q for q in questions if 'correct' in q]
    streak = 0
    for question in reversed(questions_answered):
        if question['correct']:
            streak += 1
        else:
            break  # Stop when we hit an incorrect answer
    return streak

def get_user_count():
    return db.users.count_documents({})

def get_topics_count():
    return db.topics.count_documents({})

def get_users():
    return db.users.find()

def search_users(search_query=""):
    if search_query != "":
        query = {
                '$or': [
                    {'name': {'$regex': search_query, '$options': 'i'}},
                    {'email': {'$regex': search_query, '$options': 'i'}}
                ]
            }
        
        return db.users.find(query).to_list()
    else:
        return db.users.find().to_list()

def get_user_by_id(user_id):
    return db.users.find_one({'_id': ObjectId(user_id)})
def edit_user(user_id, request):
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = 'is_admin' in request.form
    email_confirmed = 'email_confirmed' in request.form
        
    update_data = {
        'name': name,
        'email': email,
        'is_admin': is_admin,
        'email_confirmed': email_confirmed
    }
    
    if password:
        # Hash the new password (you'll need your password hashing function)
        update_data['password_hash'] = hash_password(password)
    
    # Handle profile picture upload
    if 'profile_pic' in request.files and request.files['profile_pic'].filename != '':
        file = request.files['profile_pic']
        update_profile_picture(email, file)
    
    # Handle profile picture removal
    if 'remove_profile_pic' in request.form:
        update_data['profile_pic'] = ''
    
    # Update user in MongoDB
    db.users.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': update_data}
    )
def verify_user(user_id):
    db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {'email_confirmed': True}})

def delete_user(user_id):
    db.users.delete_one({'_id': ObjectId(user_id)})