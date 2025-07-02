from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'family-social-media-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///family_social.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 허용된 파일 확장자
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

# 업로드 폴더 생성
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 데이터베이스 모델
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(50), nullable=False)  # 작성자
    content = db.Column(db.Text, nullable=True)
    media_type = db.Column(db.String(10), nullable=True)  # 'image', 'audio', 'text'
    media_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    date = db.Column(db.Date, default=date.today)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    # 오늘 날짜의 포스트들 가져오기
    today = date.today()
    posts = Post.query.filter_by(date=today).order_by(Post.created_at.desc()).all()
    return render_template('index.html', posts=posts, today=today)

@app.route('/date/<date_str>')
def date_view(date_str):
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        posts = Post.query.filter_by(date=selected_date).order_by(Post.created_at.desc()).all()
        return render_template('index.html', posts=posts, today=selected_date)
    except ValueError:
        return redirect(url_for('index'))

@app.route('/post', methods=['POST'])
def create_post():
    author = request.form.get('author', '').strip()
    content = request.form.get('content', '').strip()
    media_file = request.files.get('media')
    
    if not author:
        flash('이름을 반드시 입력해 주세요!', 'error')
        return redirect(url_for('index'))
    if not media_file or not media_file.filename:
        flash('사진을 반드시 올려주세요!', 'error')
        return redirect(url_for('index'))
    if not allowed_file(media_file.filename):
        flash('허용되지 않은 파일 형식입니다. PNG, JPG, GIF만 가능합니다.', 'error')
        return redirect(url_for('index'))
    
    post = Post()
    post.author = author
    ext = media_file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    media_file.save(filepath)
    post.media_type = 'image'
    post.media_path = filename
    if content:
        post.content = content
    db.session.add(post)
    db.session.commit()
    flash('포스트가 성공적으로 올라갔어요!', 'success')
    return redirect(url_for('index'))

@app.route('/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.media_path:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], post.media_path))
        except:
            pass
    db.session.delete(post)
    db.session.commit()
    flash('포스트가 삭제되었어요!', 'success')
    return redirect(url_for('index'))

from datetime import timedelta  # 이미 import 되어 있을 수도 있음

@app.route('/calendar')
def calendar():
    from datetime import timedelta
    thirty_days_ago = date.today() - timedelta(days=30)
    dates_with_posts = db.session.query(Post.date).filter(
        Post.date >= thirty_days_ago
    ).distinct().all()
    dates_with_posts = [d[0] for d in dates_with_posts]
    today = date.today()
    # timedelta를 템플릿에 넘겨줌
    return render_template('calendar.html', dates_with_posts=dates_with_posts, today=today, timedelta=timedelta)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 8888))
    app.run(debug=False, host='0.0.0.0', port=port) 