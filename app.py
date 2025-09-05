from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import os
import uuid

from functools import wraps
from sqlalchemy.exc import IntegrityError

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            flash('관리자 인증이 필요해요.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        pin = request.form.get('pin', '')
        if pin == app.config['ADMIN_PIN']:
            session['is_admin'] = True
            flash('관리자 모드로 들어왔어요.', 'success')
            return redirect(url_for('manage_members'))
        else:
            flash('PIN이 틀렸어요.', 'error')
    return render_template('admin_login.html')

@app.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    flash('관리자 모드에서 나왔어요.', 'success')
    return redirect(url_for('login'))

@app.route('/members', methods=['GET'])
@admin_required
def manage_members():
    members = FamilyMember.query.order_by(FamilyMember.created_at.asc()).all()
    return render_template('members.html', members=members)

@app.route('/members/add', methods=['POST'])
@admin_required
def add_member():
    name = (request.form.get('name') or '').strip()
    if not name:
        flash('이름을 입력해주세요.', 'error')
        return redirect(url_for('manage_members'))
    try:
        db.session.add(FamilyMember(name=name))
        db.session.commit()
        flash(f'"{name}"가 추가되었어요.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('이미 존재하는 이름이에요. 다른 이름을 사용해주세요.', 'error')
    return redirect(url_for('manage_members'))

@app.route('/members/<int:member_id>/rename', methods=['POST'])
@admin_required
def rename_member(member_id):
    new_name = (request.form.get('new_name') or '').strip()
    if not new_name:
        flash('새 이름을 입력해주세요.', 'error')
        return redirect(url_for('manage_members'))
    m = FamilyMember.query.get_or_404(member_id)
    old = m.name
    try:
        m.name = new_name
        db.session.commit()
        # 이름 변경 시, 해당 사용자가 쓴 게시물의 author도 함께 바꿔줍니다.
        Post.query.filter_by(author=old).update({Post.author: new_name})
        db.session.commit()
        flash(f'"{old}" → "{new_name}"로 변경되었어요.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('이미 존재하는 이름이에요. 다른 이름을 사용해주세요.', 'error')
    return redirect(url_for('manage_members'))

@app.route('/members/<int:member_id>/delete', methods=['POST'])
@admin_required
def delete_member(member_id):
    m = FamilyMember.query.get_or_404(member_id)
    name = m.name
    # 해당 사용자가 작성한 포스트가 있더라도, 먼저 사용자만 삭제할지 여부는 정책에 따라 달라요.
    # 여기서는 사용자 삭제만 수행합니다. (포스트는 유지)
    db.session.delete(m)
    try:
        db.session.commit()
        flash(f'"{name}"가 삭제되었어요.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'삭제 중 오류: {e}', 'error')
    return redirect(url_for('manage_members'))

# Flask 앱 생성
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'family-social-media-secret-key')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['ADMIN_PIN'] = os.getenv('ADMIN_PIN', '0000')  # 관리자 PIN (기본 0000)


# --- 데이터 저장 경로 선택: /var/data(디스크가 있으면) 아니면 /tmp ---
def pick_data_dir():
    p = "/var/data"
    # 디스크가 실제로 붙었고, 쓰기가 가능할 때만 사용
    if os.path.isdir(p) and os.access(p, os.W_OK):
        return p
    # 폴백: 임시 디렉토리 (재시작 시 사라짐)
    return "/tmp/appdata"

DATA_DIR = pick_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)

# DB 경로
db_path = os.path.join(DATA_DIR, "family_social.db")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path

# 업로드 경로
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR

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

import json, os

@app.route("/healthz")
def healthz():
    # 기본 헬스체크
    return "ok"

@app.route("/debug_fs")
def debug_fs():
    info = {
        "DATA_DIR": DATA_DIR,
        "UPLOAD_FOLDER": app.config.get("UPLOAD_FOLDER"),
        "db_path": app.config.get("SQLALCHEMY_DATABASE_URI"),
        "/var/data_exists": os.path.isdir("/var/data"),
        "/var/data_writable": os.access("/var/data", os.W_OK),
        "uploads_exists": os.path.isdir(app.config["UPLOAD_FOLDER"]),
        "uploads_list": [],
        "whoami": os.getuid(),
        "cwd": os.getcwd(),
    }
    try:
        info["uploads_list"] = os.listdir(app.config["UPLOAD_FOLDER"])
    except Exception as e:
        info["uploads_list"] = [f"error: {e.__class__.__name__}: {e}"]
    return json.dumps(info, ensure_ascii=False, indent=2), 200, {"Content-Type": "application/json"}


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
def create_post():
    if 'author' not in session:
        return redirect(url_for('login'))

    author = session['author']
    content = request.form.get('content', '').strip()
    media_file = request.files.get('media')

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
    if 'author' not in session:
        return redirect(url_for('login'))

    post = Post.query.get_or_404(post_id)
    # 현재 로그인한 사용자와 포스트 작성자가 같아야만 삭제 가능
    if post.author != session['author']:
        flash('포스트를 삭제할 권한이 없어요!', 'error')
        return redirect(url_for('index'))

    if post.media_path:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], post.media_path))
        except:
            pass
    db.session.delete(post)
    db.session.commit()
    flash('포스트가 삭제되었어요!', 'success')
    return redirect(url_for('index'))


@app.route('/calendar')
def calendar():
    if 'author' not in session:
        return redirect(url_for('login'))

    thirty_days_ago = date.today() - timedelta(days=30)
    dates_with_posts = db.session.query(Post.date).filter(
        Post.date >= thirty_days_ago
    ).distinct().all()
    dates_with_posts = [d[0] for d in dates_with_posts]
    today = date.today()
    return render_template('calendar.html', dates_with_posts=dates_with_posts, today=today, timedelta=timedelta)


# ========================
# 앱 실행
# ========================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8888))
    app.run(debug=False, host='0.0.0.0', port=port)
