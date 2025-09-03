from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import os
import uuid

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'family-social-media-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'family_social.db')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 허용된 파일 확장자
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

# Create instance and upload folders before the app context is pushed
instance_path = os.path.join(basedir, 'instance')
upload_path = os.path.join(basedir, 'static', 'uploads')

os.makedirs(instance_path, exist_ok=True)
os.makedirs(upload_path, exist_ok=True)

# 데이터베이스 모델
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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 앱 시작 시 설정 확인
with app.app_context():
    db.create_all()
    if not Settings.query.first():
        db.session.add(Settings(is_setup_done=False))
        db.session.commit()

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8888))
    app.run(debug=False, host='0.0.0.0', port=port)
