from flask import Blueprint, session, render_template, abort, request, redirect, jsonify, flash, Response
import db, random, io, csv, pandas as pd
import re

bp = Blueprint('topics', __name__, url_prefix='', template_folder='website/templates/topics')

OBJECT_ID_PATTERN = re.compile(r"^(?=[a-f\d]{24}$)(\d+[a-f]|[a-f]+\d)", re.IGNORECASE)

@bp.route('/topics', methods=["GET", "POST"])
def topics():
    return render_template("topics/topics.html",
                           user=db.get_user(session["email"]),
                           topics=db.get_topics(session["email"]),
                           is_admin=db.get_user(session['email'])['is_admin'])

@bp.route("/flash/<tid>/<qid>")
def flashcard(tid, qid):
    if not OBJECT_ID_PATTERN.match(tid):
        abort(404)
    topic = db.get_topic(tid)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], tid):
        abort(403)
    questions = topic["questions"]
    question = [q for q in questions if str(q["id"]) == str(qid)]
    if len(question) == 0:
        abort(404)
    return render_template("topics/flash.html", t=db.get_topic(tid), question=question[0])

@bp.route("/quiz/<tid>")
def quiz(tid):
    if not OBJECT_ID_PATTERN.match(tid):
        abort(404)
    topic = db.get_topic(tid)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], tid):
        abort(403)
    questions = topic['questions']
    if request.args.get('randomize', default=False, type=bool):
        questions = random.sample(questions, len(questions))
    if request.args.get('skip-correct', default=False, type=bool):
        last = db.get_last_quiz(session['email'], tid)
        if last:
            wrong = [q['id'] for q in last['questions'] if 'correct' in q and not q['correct']]
            questions = [q for q in questions if q['id'] in wrong]
    id = db.generate_quiz(session['email'], tid, questions)
    if len(questions) == 0:
        db.finish_quiz(id)
        return redirect(f'/quiz-results/{id}')
    return redirect(f'/quizlet/{id}/{questions[0]["id"]}')

@bp.route("/quizlet/<quizid>/<qid>")
def quizlet(quizid, qid):
    if not OBJECT_ID_PATTERN.match(quizid):
        abort(404)
    if not db.has_access_to_quiz(session["email"], quizid):
        abort(403)
    quiz = db.get_quiz(quizid)
    if not quiz:
        abort(404)
    questions = quiz['questions']
    question = [q for q in questions if str(q['id']) == qid]
    quizindex = [i for i, q in enumerate(questions) if str(q['id']) == qid][0]
    if len(question) == 0:
        abort(404)
    return render_template("topics/quizlet.html",
                           t=db.get_topic(quiz["topic_id"]),
                           quizid=quizid,
                           qid=qid,
                           question=question[0],
                           streak=db.get_streak(quizid),
                           question_number=quizindex,
                           total_questions=len(questions),
                           timeStarted=quiz['time-start']
                           )

@bp.route("/answer-quizlet/<quizid>/<qid>")
def answer_quizlet(quizid, qid):
    if not db.has_access_to_quiz(session["email"], quizid):
        abort(403)
    response = request.args.get("response")
    if response not in ["yes", "no"]:
        return jsonify({
            'error': 'Bad Request',
            'message': 'The response is not yes or no.'
        }), 400
    response = response.lower()
    next = db.update_quiz_response(session["email"], quizid, qid, response == "yes")
    if next:
        return redirect(f"/quizlet/{quizid}/{next['id']}")
    db.finish_quiz(quizid)
    return redirect(f"/quiz-results/{quizid}")

@bp.route("/quiz-results/<quizid>")
def quiz_results(quizid):
    if not OBJECT_ID_PATTERN.match(quizid):
        abort(404)
    return render_template('topics/quiz-results.html', **db.get_quiz_stats(quizid))
@bp.route("/flash/<tid>")
def flash_card_infinite(tid):
    if not OBJECT_ID_PATTERN.match(tid):
        abort(404)
    topic = db.get_topic(tid)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], tid):
        abort(403)
    topic = db.get_topic(tid)
    question = random.choice(topic["questions"])
    return redirect(f"/flash/{tid}/{question['id']}")

@bp.route("/add-topic", methods=["GET", "POST"])
def add_topic():
    if request.method == "POST":
        db.add_topic(
            session["email"],
            request.form.get('title'),
            request.form.getlist('questions[]'),
            request.form.getlist('answers[]'))
        return redirect("/topics")
    else:
        return render_template("topics/add-topic.html")

@bp.route("/topic-start/<id>")
def topic_start(id):
    if not OBJECT_ID_PATTERN.match(id):
        abort(404)
    topic = db.get_topic(id)
    if topic == None:
        abort(404)
    if 'participants' in topic:
        topic['participants'] = [db.get_user_by_id(p)['email'] for p in topic['participants']]
    if not db.has_access_to_topic(session["email"], id):
        abort(403)
    return render_template("topics/topic-start.html", t=topic,
                           topic_stats=db.get_topic_stats(id, session['email']), is_owner=db.is_owner(session['email'], id))

@bp.route('/edit-topic/<id>', methods=['GET', 'POST'])
def edit_topic(id):
    if not OBJECT_ID_PATTERN.match(id):
        abort(404)
    topic = db.get_topic(id)
    if topic == None:
        abort(404)
    if not db.is_owner(session["email"], id):
        abort(403)
    
    if request.method == 'POST':
        title = request.form['title']
        questions = request.form.getlist('questions[]')
        answers = request.form.getlist('answers[]')
        
        if not title or not all(questions) or not all(answers):
            return "All fields must be filled", 400
        
        db.edit_topic(id, request.form)
        topic=db.get_topic(id)
    
    return render_template('topics/edit-topic.html', topic=topic)

@bp.route("/delete-topic/<id>")
def delete_topic(id):
    if not OBJECT_ID_PATTERN.match(id):
        abort(404)
    topic = db.get_topic(id)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], id):
        abort(403)
    db.delete_topic(id)
    return redirect("/topics")

@bp.route("/export-csv/<id>")
def export_csv(id):
    if not OBJECT_ID_PATTERN.match(id):
        abort(404)
    topic = db.get_topic(id)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], id):
        abort(403)
    questions = topic["questions"]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "question", "answer"])
    for q in questions:
        w.writerow([q["id"], q["question"], q["answer"]])
    out.seek(0)
    return Response(out, mimetype="text/csv", headers={
        "Content-Disposition": f"attachment;filename={topic['title']}.csv"
    })

@bp.route("/import-topic", methods=["GET", "POST"])
def import_topic():
    if request.method == "POST":
        title = request.form.get('title')
        file = request.files.get('csv-file')
        if not title or not file:
            flash("No title and CSV. ", "errors")
            return render_template("topics/import-menu.html")

        if not file.filename.endswith('.csv'):
            flash("Please upload a valid CSV file!", "error")
            return render_template("topics/import-menu.html")
        df = pd.read_csv(file)
        if "question" not in df.columns or "answer" not in df.columns:
            flash("No question or answer column in csv. ", "error")
            return render_template("topics/import-menu.html")
        q = db.import_topic(session["email"], title, df)
        flash(f"Successfully imported topic '{title}' with {q} questions!", "success")
    return render_template("topics/import-menu.html")

@bp.route("/update-topic-visibility/<tid>", methods=["POST"])
def update_topic_visability(tid):
    state = request.get_json().get('visibility')
    if not db.is_owner(session['email'], tid):
        return jsonify({"success": False, "error": "You don't have ownership of topic. "}), 403
    if state not in ['private', 'restricted', 'public']:
        return jsonify({"success": False, "error": "Invalid visibility value"}), 400
    res = db.update_topic_visability(tid, state)
    if res.modified_count == 0:
        return jsonify({"success": False, "error": "No changes made"}), 400
    else:
        return jsonify({
                "success": True,
                "message": f"Visibility updated to {state}",
                "new_visibility": state
            })
    
@bp.route("/add-topic-participant/<tid>", methods=["POST"])
def add_topic_participant(tid):
    if not db.is_owner(session['email'], tid):
        return jsonify({"success": False, "error": "You don't have ownership of topic. "}), 403
    participant_email = request.get_json().get('email')
    if not participant_email:
            return jsonify({"success": False, "error": "Email is required"}), 400
    if not db.email_already_exists(participant_email):
        return jsonify({"success": False, "error": "User not found"}), 400
    participant = db.get_user(participant_email)
    if participant['_id'] in db.get_participants(tid):
        return jsonify({"success": False, "error": "User is already a participant"}), 400
    db.add_participant(tid, participant['_id'])
    return jsonify({
            "success": True,
            "message": f"Added {participant_email} to topic",
            "participant": {
                "id": str(participant['_id']),
                "email": participant_email,
                "name": participant.get('name', '')
            }
        })



@bp.route('/remove-topic-participant/<topic_id>', methods=['POST'])
def remove_participant(topic_id):
    participant_email = request.get_json().get('email')
    if not db.is_owner(session['email'], topic_id):
        return jsonify({"success": False, "error": "Not owner. "}), 405
    if not db.email_already_exists(participant_email):
        return jsonify({"success": False, "error": "User not found"}), 400
    user = db.get_user(participant_email)

    db.remove_participant(topic_id, user['_id'])

    return jsonify({"success": True})

@bp.route('/analytics/<topic_id>')
def analytics(topic_id):
    if not OBJECT_ID_PATTERN.match(topic_id):
        abort(404)
    topic = db.get_topic(topic_id)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], topic_id):
        abort(403)
    data = db.get_analytics_data(topic_id, session['email'])
    return render_template("topics/analytics.html", **data)