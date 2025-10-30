from flask import Blueprint, render_template, send_from_directory, current_app
from flask_login import login_required
import os

styleguide_bp = Blueprint('styleguide', __name__)

@styleguide_bp.route('/styleguide')
@login_required
def styleguide():
    return render_template('styleguide.html')

@styleguide_bp.route('/styleguide/standalone')
@login_required
def styleguide_standalone():
    static_dir = os.path.join(current_app.root_path, 'static')
    return send_from_directory(static_dir, 'styleguide-showcase.html')
