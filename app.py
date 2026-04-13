import os
import json
import random
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from flask_migrate import Migrate
from sqlalchemy import create_engine, text
from config import Config
from models import db, User, DietRecord, WeightRecord, CheckInRecord, ExerciseRecord
from ai_utils import recognize_food_image, analyze_health_data, chat_with_assistant

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload folder exists
os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)

# Initialize database
db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录后再访问此页面'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def create_database_if_not_exists():
    """Create the fitness_app database if it doesn't exist"""
    try:
        engine = create_engine(
            'mysql+pymysql://fitness:PMTMmMRpYRx343kh@127.0.0.1:3306/?charset=utf8mb4',
            pool_pre_ping=True
        )
        with engine.connect() as conn:
            conn.execute(text("CREATE DATABASE IF NOT EXISTS fitness_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            conn.commit()
        print("Database 'fitness_app' is ready.")
    except Exception as e:
        print(f"Could not create database: {e}")


@app.route('/api/send-code', methods=['POST'])
def send_code():
    email = request.json.get('email')
    if not email:
        return jsonify({'success': False, 'message': '请输入邮箱地址'})
    
    # Check if email is already registered
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': '该邮箱已被注册'})
    
    # Generate 6-digit code
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    # Store in session with timestamp
    session['verification_code'] = code
    session['verification_email'] = email
    session['verification_time'] = datetime.now().timestamp()
    
    try:
        msg = Message('Fitness App 注册验证码', recipients=[email])
        msg.body = f'您的注册验证码是：{code}，请在5分钟内使用。'
        mail.send(msg)
        return jsonify({'success': True, 'message': '验证码已发送'})
    except Exception as e:
        print(f"Send mail error: {e}")
        return jsonify({'success': False, 'message': '发送验证码失败，请检查邮箱地址是否正确'})

# =====================
# AUTH ROUTES
# =====================
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('请输入用户名和密码', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        code = request.form.get('verification_code', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not username or not password or not email or not code:
            flash('请填写完整的注册信息', 'error')
            return render_template('auth/register.html')
        
        # Verify code
        session_code = session.get('verification_code')
        session_email = session.get('verification_email')
        session_time = session.get('verification_time')
        
        if not session_code or not session_email or not session_time:
            flash('请先获取验证码', 'error')
            return render_template('auth/register.html')
        
        if email != session_email:
            flash('邮箱与获取验证码时的邮箱不一致', 'error')
            return render_template('auth/register.html')
            
        if code != session_code:
            flash('验证码错误', 'error')
            return render_template('auth/register.html')
            
        if datetime.now().timestamp() - session_time > 300: # 5 minutes
            flash('验证码已过期，请重新获取', 'error')
            return render_template('auth/register.html')
        
        if len(username) < 3 or len(username) > 20:
            flash('用户名长度需在3-20个字符之间', 'error')
            return render_template('auth/register.html')
        
        if len(password) < 6:
            flash('密码长度不能少于6位', 'error')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('两次输入的密码不一致', 'error')
            return render_template('auth/register.html')
        
        if User.query.filter_by(username=username).first():
            flash('该用户名已被注册，请换一个', 'error')
            return render_template('auth/register.html')
            
        if User.query.filter_by(email=email).first():
            flash('该邮箱已被注册，请换一个', 'error')
            return render_template('auth/register.html')
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Clear session
        session.pop('verification_code', None)
        session.pop('verification_email', None)
        session.pop('verification_time', None)
        
        flash('注册成功！请登录', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已成功退出登录', 'info')
    return redirect(url_for('login'))


# =====================
# DASHBOARD
# =====================
@app.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    
    # Today's calorie summary
    today_diet = DietRecord.query.filter_by(
        user_id=current_user.id, record_date=today
    ).all()
    total_intake = sum(r.calories for r in today_diet)
    
    today_exercise = ExerciseRecord.query.filter_by(
        user_id=current_user.id, record_date=today
    ).first()
    exercise_burn = today_exercise.calories_burned if today_exercise else 0
    
    bmr = app.config['DEFAULT_BMR']
    calorie_diff = total_intake - (bmr + exercise_burn)
    
    # Latest weight
    latest_weight = WeightRecord.query.filter_by(
        user_id=current_user.id
    ).order_by(WeightRecord.record_date.desc()).first()
    
    # This month's check-ins
    first_day = today.replace(day=1)
    monthly_checkins = CheckInRecord.query.filter(
        CheckInRecord.user_id == current_user.id,
        CheckInRecord.checkin_date >= first_day
    ).count()
    
    # Today checked in?
    today_checkin = CheckInRecord.query.filter_by(
        user_id=current_user.id, checkin_date=today
    ).first()
    
    return render_template('dashboard.html',
        total_intake=total_intake,
        exercise_burn=exercise_burn,
        bmr=bmr,
        calorie_diff=calorie_diff,
        latest_weight=latest_weight.weight if latest_weight else None,
        monthly_checkins=monthly_checkins,
        today_checkin=bool(today_checkin),
        today=today
    )


# =====================
# DIET ROUTES
# =====================
@app.route('/diet')
@login_required
def diet():
    today = date.today()
    records = DietRecord.query.filter_by(
        user_id=current_user.id, record_date=today
    ).all()
    
    breakfast = [r for r in records if r.meal_type == 'breakfast']
    lunch = [r for r in records if r.meal_type == 'lunch']
    dinner = [r for r in records if r.meal_type == 'dinner']
    
    total_calories = sum(r.calories for r in records)
    
    today_exercise = ExerciseRecord.query.filter_by(
        user_id=current_user.id, record_date=today
    ).first()
    exercise_burn = today_exercise.calories_burned if today_exercise else 0
    
    bmr = app.config['DEFAULT_BMR']
    calorie_diff = total_calories - (bmr + exercise_burn)
    
    return render_template('diet.html',
        breakfast=breakfast, lunch=lunch, dinner=dinner,
        total_calories=total_calories,
        exercise_burn=exercise_burn, bmr=bmr,
        calorie_diff=calorie_diff,
        today_exercise=today_exercise,
        today=today
    )


@app.route('/diet/add', methods=['POST'])
@login_required
def diet_add():
    data = request.get_json()
    meal_type = data.get('meal_type')
    food_name = data.get('food_name', '').strip()
    calories = float(data.get('calories', 0))
    record_date_str = data.get('record_date', str(date.today()))
    
    if not food_name or meal_type not in ['breakfast', 'lunch', 'dinner']:
        return jsonify({'success': False, 'message': '信息不完整'}), 400
    
    try:
        record_date = datetime.strptime(record_date_str, '%Y-%m-%d').date()
    except:
        record_date = date.today()
    
    record = DietRecord(
        user_id=current_user.id,
        meal_type=meal_type,
        food_name=food_name,
        calories=calories,
        record_date=record_date
    )
    db.session.add(record)
    db.session.commit()
    
    return jsonify({'success': True, 'record': record.to_dict()})


@app.route('/diet/delete/<int:record_id>', methods=['DELETE'])
@login_required
def diet_delete(record_id):
    record = DietRecord.query.filter_by(id=record_id, user_id=current_user.id).first()
    if not record:
        return jsonify({'success': False, 'message': '记录不存在'}), 404
    
    db.session.delete(record)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/diet/recognize', methods=['POST'])
@login_required
def diet_recognize():
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': '未上传图片'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择图片'}), 400
    
    image_data = file.read()
    foods = recognize_food_image(image_data)
    
    if foods:
        return jsonify({'success': True, 'foods': foods})
    else:
        return jsonify({'success': False, 'message': '识别失败，请重试或手动输入'})


@app.route('/diet/exercise', methods=['POST'])
@login_required
def diet_exercise():
    data = request.get_json()
    calories_burned = float(data.get('calories_burned', 0))
    description = data.get('description', '')
    today = date.today()
    
    record = ExerciseRecord.query.filter_by(
        user_id=current_user.id, record_date=today
    ).first()
    
    if record:
        record.calories_burned = calories_burned
        record.description = description
    else:
        record = ExerciseRecord(
            user_id=current_user.id,
            record_date=today,
            calories_burned=calories_burned,
            description=description
        )
        db.session.add(record)
    
    db.session.commit()
    return jsonify({'success': True})


# =====================
# WEIGHT ROUTES
# =====================
@app.route('/weight')
@login_required
def weight():
    records = WeightRecord.query.filter_by(
        user_id=current_user.id
    ).order_by(WeightRecord.record_date.asc()).all()
    
    today = date.today()
    today_record = WeightRecord.query.filter_by(
        user_id=current_user.id, record_date=today
    ).first()
    
    chart_dates = [r.record_date.strftime("%m/%d") for r in records]
    chart_weights = [r.weight for r in records]
    
    return render_template('weight.html', records=records, today_record=today_record, today=today, chart_dates=chart_dates, chart_weights=chart_weights)


@app.route('/weight/add', methods=['POST'])
@login_required
def weight_add():
    data = request.get_json()
    weight_val = float(data.get('weight', 0))
    record_date_str = data.get('record_date', str(date.today()))
    
    if weight_val <= 0 or weight_val > 500:
        return jsonify({'success': False, 'message': '体重数据不合法'}), 400
    
    try:
        record_date = datetime.strptime(record_date_str, '%Y-%m-%d').date()
    except:
        record_date = date.today()
    
    existing = WeightRecord.query.filter_by(
        user_id=current_user.id, record_date=record_date
    ).first()
    
    if existing:
        existing.weight = weight_val
        db.session.commit()
        return jsonify({'success': True, 'record': existing.to_dict(), 'updated': True})
    else:
        record = WeightRecord(
            user_id=current_user.id,
            weight=weight_val,
            record_date=record_date
        )
        db.session.add(record)
        db.session.commit()
        return jsonify({'success': True, 'record': record.to_dict(), 'updated': False})


@app.route('/weight/analysis')
@login_required
def weight_analysis():
    today = date.today()
    seven_days_ago = today - timedelta(days=7)
    
    weight_records = WeightRecord.query.filter(
        WeightRecord.user_id == current_user.id,
        WeightRecord.record_date >= seven_days_ago
    ).order_by(WeightRecord.record_date.asc()).all()
    
    weight_data = [{'date': r.record_date.strftime('%Y-%m-%d'), 'weight': r.weight} for r in weight_records]
    
    # Get calorie diff data for each day
    calorie_data = []
    for i in range(7):
        day = seven_days_ago + timedelta(days=i)
        diet_records = DietRecord.query.filter_by(user_id=current_user.id, record_date=day).all()
        total_intake = sum(r.calories for r in diet_records)
        exercise = ExerciseRecord.query.filter_by(user_id=current_user.id, record_date=day).first()
        exercise_burn = exercise.calories_burned if exercise else 0
        bmr = app.config['DEFAULT_BMR']
        calorie_diff = total_intake - (bmr + exercise_burn)
        if total_intake > 0:  # Only include days with data
            calorie_data.append({'date': day.strftime('%Y-%m-%d'), 'calorie_diff': calorie_diff})
    
    analysis = analyze_health_data(weight_data, calorie_data)
    return jsonify({'success': True, 'analysis': analysis})


# =====================
# CHECK-IN ROUTES
# =====================
@app.route('/checkin')
@login_required
def checkin():
    today = date.today()
    first_day = today.replace(day=1)
    
    # Get all check-in dates for this user
    all_checkins = CheckInRecord.query.filter_by(user_id=current_user.id).all()
    checkin_dates = [r.checkin_date.strftime('%Y-%m-%d') for r in all_checkins]
    
    monthly_checkins = CheckInRecord.query.filter(
        CheckInRecord.user_id == current_user.id,
        CheckInRecord.checkin_date >= first_day
    ).count()
    
    today_checkin = CheckInRecord.query.filter_by(
        user_id=current_user.id, checkin_date=today
    ).first()
    
    return render_template('checkin.html',
        checkin_dates=json.dumps(checkin_dates),
        monthly_checkins=monthly_checkins,
        today_checkin=bool(today_checkin),
        today=today
    )


@app.route('/checkin/do', methods=['POST'])
@login_required
def checkin_do():
    today = date.today()
    
    existing = CheckInRecord.query.filter_by(
        user_id=current_user.id, checkin_date=today
    ).first()
    
    if existing:
        return jsonify({'success': False, 'message': '今天已经打过卡了！'})
    
    record = CheckInRecord(user_id=current_user.id, checkin_date=today)
    db.session.add(record)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '打卡成功！坚持加油 💪'})


# =====================
# CHAT ROUTES
# =====================
@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html')


@app.route('/chat/message', methods=['POST'])
@login_required
def chat_message():
    data = request.get_json()
    messages = data.get('messages', [])
    
    if not messages:
        return jsonify({'success': False, 'message': '消息不能为空'}), 400
    
    response = chat_with_assistant(messages)
    return jsonify({'success': True, 'response': response})


# =====================
# PROFILE ROUTES
# =====================
def calc_bmr(height, weight_kg, age, gender):
    """Mifflin-St Jeor BMR formula."""
    if not all([height, weight_kg, age, gender]):
        return None
    base = 10 * weight_kg + 6.25 * height - 5 * age
    return round(base + 5 if gender == 'male' else base - 161, 1)


@app.route('/profile')
@login_required
def profile():
    bmr = calc_bmr(
        current_user.height,
        current_user.weight_kg,
        current_user.age,
        current_user.gender
    )
    return render_template('profile.html', bmr=bmr)


@app.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    try:
        height = request.form.get('height', '').strip()
        weight_kg = request.form.get('weight_kg', '').strip()
        age = request.form.get('age', '').strip()
        gender = request.form.get('gender', '').strip()

        if height:
            current_user.height = float(height)
        if weight_kg:
            current_user.weight_kg = float(weight_kg)
        if age:
            current_user.age = int(age)
        if gender in ('male', 'female'):
            current_user.gender = gender

        db.session.commit()
        flash('个人信息已更新！', 'success')
    except ValueError:
        flash('请输入有效数字', 'error')
    return redirect(url_for('profile'))


@app.route('/profile/settings')
@login_required
def settings():
    return render_template('settings.html')


@app.route('/api/send-change-pwd-code', methods=['POST'])
@login_required
def send_change_pwd_code():
    """Send password-change verification code to the user's registered email."""
    email = current_user.email
    if not email:
        return jsonify({'success': False, 'message': '账户未绑定邮箱，无法发送验证码'})

    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    session['pwd_change_code'] = code
    session['pwd_change_time'] = datetime.now().timestamp()

    try:
        msg = Message('健身达人 - 修改密码验证码', recipients=[email])
        msg.body = (
            f'您正在修改密码，验证码为：{code}\n'
            f'请在5分钟内使用，如非本人操作请忽略此邮件。'
        )
        mail.send(msg)
        return jsonify({'success': True, 'message': f'验证码已发送至 {email}'})
    except Exception as e:
        print(f"Send change-pwd mail error: {e}")
        return jsonify({'success': False, 'message': '发送失败，请稍后重试'})


@app.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    code = data.get('code', '').strip()
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    session_code = session.get('pwd_change_code')
    session_time = session.get('pwd_change_time')

    if not session_code or not session_time:
        return jsonify({'success': False, 'message': '请先获取验证码'})

    if datetime.now().timestamp() - session_time > 300:
        session.pop('pwd_change_code', None)
        session.pop('pwd_change_time', None)
        return jsonify({'success': False, 'message': '验证码已过期，请重新获取'})

    if code != session_code:
        return jsonify({'success': False, 'message': '验证码错误'})

    if len(new_password) < 6:
        return jsonify({'success': False, 'message': '密码长度不能少于6位'})

    if new_password != confirm_password:
        return jsonify({'success': False, 'message': '两次密码不一致'})

    current_user.set_password(new_password)
    db.session.commit()
    session.pop('pwd_change_code', None)
    session.pop('pwd_change_time', None)
    return jsonify({'success': True, 'message': '密码修改成功！请重新登录'})


# =====================
# STARTUP
# =====================
if __name__ == '__main__':
    create_database_if_not_exists()
    
    with app.app_context():
        db.create_all()
        print("Database tables created successfully.")
    
    app.run(debug=True, host='0.0.0.0', port=5002)
