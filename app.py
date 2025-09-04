from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import os
import uuid

# Flask 앱 생성
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'family-social-media-secret-key')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# --- Render Persistent Disk 경로 ---
DATA_DIR = "/var/data"  # Persistent Disk mount path
os.makedirs(DATA_DIR, exist_ok=True)

# DB 저장 경로
db_path = os.path.join(DATA_DIR, 'family_social.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path

# 업로드(사진) 저장 경로
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR

# 허용된 파일 확장자
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# DB 초기화
db = SQLAlchemy(app)


# ========================
# 데이터베이스 모델
# ========================
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=True)
    media_type = db.Column(db.String(10), nullable=True)
    media_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    date = db.Column(db.Date, default=date.today)


class FamilyMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_setup_done = db.Column(db.Boolean, default=False)


# ========================
# 헬퍼 함수
# ========================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ========================
# DB 초기화
# ========================
with app.app_context():
    db.create_all()
    if not Settings.query.first():
        db.session.add(Settings(is_setup_done=False))
        db.session.commit()


# ========================
# 라우트
# ========================

# 업로드된 파일 불러오기
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/')
def index():
    settings = Settings.query.first()
    if not settings or not settings.is_setup_done:
        return redirect(url_for('setup'))
    if 'author' not in session:
        return redirect(url_for('login'))

    today = date.today()
    posts = Post.query.filter_by(date=today).order_by(Post.created_at.desc()).all()
    return render_template('index.html', posts=posts, today=today, current_author=session['author'])


@app.route('/login')
def login():
    members = FamilyMember.query.all()
    if not members:
        return redirect(url_for('setup'))
    return render_template('login.html', members=members)


@app.route('/select_member/<member_name>')
def select_member(member_name):
    member = FamilyMember.query.filter_by(name=member_name).first()
    if member:
        session['author'] = member_name
        flash(f'{member_name}님, 환영합니다!', 'success')
        return redirect(url_for('index'))
    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.pop('author', None)
    flash('로그아웃되었습니다.', 'success')
    return redirect(url_for('login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    settings = Settings.query.first()
    if settings.is_setup_done and request.method == 'GET':
        return redirect(url_for('login'))

    if request.method == 'POST':
        members_str = request.form.get('members', '')
        if not members_str:
            flash('가족 구성원을 한 명 이상 입력해 주세요!', 'error')
            return render_template('setup.html')

        members = [name.strip() for name in members_str.split(',') if name.strip()]

        try:
            for name in members:
                db.session.add(FamilyMember(name=name))
            settings.is_setup_done = True
            db.session.commit()
            flash('가족 구성원 등록이 완료되었습니다. 이제 로그인하세요!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'오류가 발생했습니다: {e}', 'error')
            return render_template('setup.html')

    return render_template('setup.html')


@app.route('/date/<date_str>')
def date_view(date_str):
    if 'author' not in session:
        return redirect(url_for('login'))
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        posts = Post.query.filter_by(date=selected_date).order_by(Post.created_at.desc()).all()
        return render_template('index.html', posts=posts, today=selected_date, current_author=session['author'])
    except ValueError:
        return redirect(url_for('index'))


@app.route('/post', methods=['POST'])
d
