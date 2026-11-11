from flask import Blueprint, render_template

workers_bp = Blueprint('workers', __name__)

@workers_bp.route('/workers')
def workers():
    return render_template('workers.html')
