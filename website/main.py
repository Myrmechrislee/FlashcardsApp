from flask import Blueprint, render_template, request, flash
import security, mail, os

bp = Blueprint('main', __name__, url_prefix='', template_folder='visitors')

@bp.route('/')
@security.no_authentication
def home():
    return render_template('visitors/index.html')

@bp.route('/about')
@security.no_authentication
def about():
    return render_template('visitors/about.html')

@bp.route('/privacy')
@security.no_authentication
def privacy():
    return render_template('visitors/privacy.html')

@bp.route('/terms')
@security.no_authentication
def terms():
    return render_template('visitors/terms.html')

@bp.route('/contact', methods=["GET", "POST"])
@security.no_authentication
def contact():
    if request.method == "POST":
        mail.send_contact_email(request.form['subject'], f"From: {request.form['name']}\nEmail: {request.form['email']}\nMessage: {request.form['message']}")
        flash('Thank you for your message! We will get back to you soon.', 'success')
    return render_template('visitors/contact-us.html')



