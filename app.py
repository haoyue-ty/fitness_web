"""
app.py —— Flask 应用主入口

负责创建 Flask 应用实例、注册所有路由（蓝图方式的平铺写法）、
初始化数据库 / 登录管理 / 邮件等扩展。

主要功能模块：
  - 用户认证（注册、登录、登出、邮箱验证码）
  - 仪表盘（今日热量总览）
  - 饮食管理（三餐记录、AI 拍照识别）
  - 体重管理（记录、趋势图、AI 分析）
  - 每日打卡
  - AI 智能对话（DeepSeek 驱动）
  - 个人资料与设置
"""

import os
import json
import random
import uuid
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message        # Flask-Mail：邮件发送扩展
from flask_migrate import Migrate           # Flask-Migrate：数据库迁移工具
from sqlalchemy import create_engine, text  # SQLAlchemy 核心引擎，用于初始化时建库
from sqlalchemy.engine import URL, make_url
from config import Config                   # 应用配置类（数据库、API Key 等）
from models import db, User, DietRecord, WeightRecord, CheckInRecord, ExerciseRecord  # 数据库模型
# 引入 AI 工具函数：
#   recognize_food_image  - 调用百度文心菜品识别 API
#   analyze_health_data   - 调用 DeepSeek 分析健康数据
#   chat_with_assistant   - 调用 DeepSeek 进行智能对话
from ai_utils import recognize_food_image, analyze_health_data, chat_with_assistant

# 创建 Flask 应用实例
app = Flask(__name__)
# 从 Config 类加载所有配置（数据库、API Key、邮件等）
app.config.from_object(Config)

# ---- 文件上传目录初始化 ----
UPLOAD_FOLDER = os.path.join('static', 'uploads')          # 通用上传根目录
AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, 'avatars')     # 用户头像子目录
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # 目录不存在时自动创建
os.makedirs(AVATAR_FOLDER, exist_ok=True)
ALLOWED_IMAGE_EXTS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}  # 允许上传的图片格式

# ---- 扩展初始化 ----
db.init_app(app)            # 将 SQLAlchemy 与 Flask 应用绑定
migrate = Migrate(app, db)  # 初始化数据库迁移工具（flask db init/migrate/upgrade）
mail = Mail(app)            # 初始化邮件发送扩展

# ---- 登录管理器初始化 ----
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'                      # 未登录时重定向到登录页
login_manager.login_message = '请先登录后再访问此页面'  # 未登录提示信息
login_manager.login_message_category = 'warning'        # 提示信息的样式类别


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login 回调：根据用户 ID 从数据库加载用户对象，用于维护登录会话。"""
    return User.query.get(int(user_id))


def create_database_if_not_exists():
    """若配置了 MySQL，则在直接运行应用时创建尚不存在的数据库。"""
    try:
        database_url = make_url(app.config['SQLALCHEMY_DATABASE_URI'])
        if not database_url.drivername.startswith('mysql') or not database_url.database:
            return

        server_url = URL.create(
            drivername=database_url.drivername,
            username=database_url.username,
            password=database_url.password,
            host=database_url.host,
            port=database_url.port,
            query=database_url.query,
        )
        engine = create_engine(server_url, pool_pre_ping=True)
        with engine.begin() as conn:
            database_name = conn.dialect.identifier_preparer.quote(database_url.database)
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {database_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        engine.dispose()
        print(f"Database '{database_url.database}' is ready.")
    except Exception as e:
        print(f"Could not create database: {e}")


@app.route('/api/send-code', methods=['POST'])
def send_code():
    """发送注册邮箱验证码接口。生成 6 位随机数字验证码并通过 QQ 邮件发送给用户。"""
    email = request.json.get('email')
    if not email:
        return jsonify({'success': False, 'message': '请输入邮箱地址'})
    
    # 检查邮箱是否已被注册，避免重复注册
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': '该邮箱已被注册'})
    
    # 生成 6 位数字验证码
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    # 将验证码、对应邮箱和发送时间戳存入 Flask Session，注册时校验用
    session['verification_code'] = code
    session['verification_email'] = email
    session['verification_time'] = datetime.now().timestamp()
    
    try:
        msg = Message('Fitness App 注册验证码', recipients=[email])
        msg.body = f'您的注册验证码是：{code}，请在5分钟内使用。'
        mail.send(msg)  # 通过 Flask-Mail 发送邮件（配置见 config.py 的 MAIL_* 字段）
        return jsonify({'success': True, 'message': '验证码已发送'})
    except Exception as e:
        print(f"Send mail error: {e}")
        return jsonify({'success': False, 'message': '发送验证码失败，请检查邮箱地址是否正确'})

# =====================
# 认证相关路由
# =====================
@app.route('/')
def index():
    """根路由：已登录用户跳转仪表盘，未登录跳转登录页。"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录页。GET 显示登录表单，POST 处理登录逻辑。"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('请输入用户名和密码', 'error')
            return render_template('auth/login.html')
        
        # 根据用户名查询用户记录
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            # 验证成功，登录用户（remember=True 保持会话）
            login_user(user, remember=True)
            # 支持 next 参数，登录后跳转到原本想访问的页面
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册页。GET 显示注册表单，POST 校验表单并创建账号。"""
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
        
        # 从 Session 读取之前发送的验证码信息
        session_code = session.get('verification_code')
        session_email = session.get('verification_email')
        session_time = session.get('verification_time')
        
        if not session_code or not session_email or not session_time:
            flash('请先获取验证码', 'error')
            return render_template('auth/register.html')
        
        # 校验提交的邮箱与申请验证码时的邮箱一致
        if email != session_email:
            flash('邮箱与获取验证码时的邮箱不一致', 'error')
            return render_template('auth/register.html')
            
        if code != session_code:
            flash('验证码错误', 'error')
            return render_template('auth/register.html')
            
        # 验证码有效期 5 分钟（300 秒）
        if datetime.now().timestamp() - session_time > 300:
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
        
        # 创建新用户，密码哈希后存储（明文不入库）
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # 注册完成后清除 Session 中的验证码信息
        session.pop('verification_code', None)
        session.pop('verification_email', None)
        session.pop('verification_time', None)
        
        flash('注册成功！请登录', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')


@app.route('/logout')
@login_required
def logout():
    """用户登出，清除会话后跳转登录页。"""
    logout_user()
    flash('已成功退出登录', 'info')
    return redirect(url_for('login'))


# =====================
# 仪表盘
# =====================
@app.route('/dashboard')
@login_required
def dashboard():
    """主仪表盘：展示今日热量摄入/消耗、最新体重、本月打卡次数等概览信息。"""
    today = date.today()
    
    # 计算今日饮食总热量（汇汇三餐所有记录）
    today_diet = DietRecord.query.filter_by(
        user_id=current_user.id, record_date=today
    ).all()
    total_intake = sum(r.calories for r in today_diet)
    
    # 获取今日运动消耗热量
    today_exercise = ExerciseRecord.query.filter_by(
        user_id=current_user.id, record_date=today
    ).first()
    exercise_burn = today_exercise.calories_burned if today_exercise else 0
    
    # 计算用户基础代谢率（BMR）
    bmr = get_user_bmr(current_user)
    # 热量差 = 摄入 - （BMR + 运动消耗），正数表示过剩，负数表示亏缺
    calorie_diff = total_intake - (bmr + exercise_burn)
    
    # 获取最近一次体重记录
    latest_weight = WeightRecord.query.filter_by(
        user_id=current_user.id
    ).order_by(WeightRecord.record_date.desc()).first()
    
    # 统计本月打卡次数
    first_day = today.replace(day=1)
    monthly_checkins = CheckInRecord.query.filter(
        CheckInRecord.user_id == current_user.id,
        CheckInRecord.checkin_date >= first_day
    ).count()
    
    # 判断今日是否已打卡
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
# 饮食管理路由
# =====================
@app.route('/diet')
@login_required
def diet():
    """饮食记录页：展示今日三餐内容、总热量摄入及热量差。"""
    today = date.today()
    records = DietRecord.query.filter_by(
        user_id=current_user.id, record_date=today
    ).all()
    
    # 按餐次分类
    breakfast = [r for r in records if r.meal_type == 'breakfast']
    lunch = [r for r in records if r.meal_type == 'lunch']
    dinner = [r for r in records if r.meal_type == 'dinner']
    
    # 今日总热量摄入
    total_calories = sum(r.calories for r in records)
    
    today_exercise = ExerciseRecord.query.filter_by(
        user_id=current_user.id, record_date=today
    ).first()
    exercise_burn = today_exercise.calories_burned if today_exercise else 0
    
    bmr = get_user_bmr(current_user)
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
    """添加饮食记录接口（JSON POST）。接收餐次、食物名、热量、日期并入库。"""
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
    """删除指定饮食记录（仅允许删除当前用户自己的记录）。"""
    record = DietRecord.query.filter_by(id=record_id, user_id=current_user.id).first()
    if not record:
        return jsonify({'success': False, 'message': '记录不存在'}), 404
    
    db.session.delete(record)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/diet/recognize', methods=['POST'])
@login_required
def diet_recognize():
    """
    食物图片 AI 识别接口。
    接收上传的食物图片，调用百度文心菜品识别 API（recognize_food_image）
    识别出食物名称和热量，返回给前端供用户确认。
    """
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': '未上传图片'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择图片'}), 400
    
    # 读取图片字节流，传入百度 AI 菜品识别函数
    image_data = file.read()
    foods = recognize_food_image(image_data)  # 调用 ai_utils.py 中的百度文心接口
    
    if foods:
        return jsonify({'success': True, 'foods': foods})
    else:
        return jsonify({'success': False, 'message': '识别失败，请重试或手动输入'})


@app.route('/diet/exercise', methods=['POST'])
@login_required
def diet_exercise():
    """更新今日运动消耗记录。若当天已有记录则更新，否则新建。"""
    data = request.get_json()
    calories_burned = float(data.get('calories_burned', 0))
    description = data.get('description', '')
    today = date.today()
    
    # 查询今日是否已有运动记录
    record = ExerciseRecord.query.filter_by(
        user_id=current_user.id, record_date=today
    ).first()
    
    if record:
        # 已存在则直接更新（每天仅保留一条运动记录）
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
# 体重管理路由
# =====================
@app.route('/weight')
@login_required
def weight():
    """体重记录页：展示历史体重记录列表和趋势折线图。"""
    # 按日期升序获取用户全部体重记录（用于绘制趋势图）
    records = WeightRecord.query.filter_by(
        user_id=current_user.id
    ).order_by(WeightRecord.record_date.asc()).all()
    
    today = date.today()
    today_record = WeightRecord.query.filter_by(
        user_id=current_user.id, record_date=today
    ).first()
    
    # 为前端图表准备日期标签和体重数据数组
    chart_dates = [r.record_date.strftime("%m/%d") for r in records]
    chart_weights = [r.weight for r in records]
    
    return render_template('weight.html', records=records, today_record=today_record, today=today, chart_dates=chart_dates, chart_weights=chart_weights)


@app.route('/weight/add', methods=['POST'])
@login_required
def weight_add():
    """添加/更新体重记录接口（JSON POST）。同一天的记录重复提交则自动更新。"""
    data = request.get_json()
    weight_val = float(data.get('weight', 0))
    record_date_str = data.get('record_date', str(date.today()))
    
    # 验证体重数值合法性
    if weight_val <= 0 or weight_val > 500:
        return jsonify({'success': False, 'message': '体重数据不合法'}), 400
    
    try:
        record_date = datetime.strptime(record_date_str, '%Y-%m-%d').date()
    except:
        record_date = date.today()
    
    # 查询该日期是否已有记录
    existing = WeightRecord.query.filter_by(
        user_id=current_user.id, record_date=record_date
    ).first()
    
    if existing:
        # 已有记录则直接更新体重数值
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


@app.route('/weight/clear', methods=['POST'])
@login_required
def weight_clear():
    """清空当前用户的全部体重记录。"""
    WeightRecord.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({'success': True, 'message': '体重记录已清空'})

@app.route('/weight/analysis')
@login_required
def weight_analysis():
    """
    AI 健康分析接口。
    收集用户近7天的体重数据和热量差数据，
    调用 DeepSeek（analyze_health_data）生成个性化健康建议并返回。
    """
    today = date.today()
    seven_days_ago = today - timedelta(days=7)
    
    # 获取迗去 7 天的体重记录
    weight_records = WeightRecord.query.filter(
        WeightRecord.user_id == current_user.id,
        WeightRecord.record_date >= seven_days_ago
    ).order_by(WeightRecord.record_date.asc()).all()
    
    weight_data = [{'date': r.record_date.strftime('%Y-%m-%d'), 'weight': r.weight} for r in weight_records]
    
    # 计算迗去 7 天每天的热量差
    calorie_data = []
    for i in range(7):
        day = seven_days_ago + timedelta(days=i)
        diet_records = DietRecord.query.filter_by(user_id=current_user.id, record_date=day).all()
        total_intake = sum(r.calories for r in diet_records)
        exercise = ExerciseRecord.query.filter_by(user_id=current_user.id, record_date=day).first()
        exercise_burn = exercise.calories_burned if exercise else 0
        bmr = get_user_bmr(current_user)
        calorie_diff = total_intake - (bmr + exercise_burn)
        if total_intake > 0:  # 只统计有饮食记录的天数
            calorie_data.append({'date': day.strftime('%Y-%m-%d'), 'calorie_diff': calorie_diff})
    
    # 调用 DeepSeek 接口分析健康数据，生成个性化建议
    analysis = analyze_health_data(weight_data, calorie_data)  # 见 ai_utils.py
    return jsonify({'success': True, 'analysis': analysis})


# =====================
# 打卡路由
# =====================
@app.route('/checkin')
@login_required
def checkin():
    """每日打卡页：展示打卡日历和本月打卡次数。"""
    today = date.today()
    first_day = today.replace(day=1)
    
    # 获取该用户所有打卡日期（用于前端日历高亮显示）
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
        checkin_dates=json.dumps(checkin_dates),  # 传入 JSON 字符串供前端 JS 解析
        monthly_checkins=monthly_checkins,
        today_checkin=bool(today_checkin),
        today=today
    )


@app.route('/checkin/do', methods=['POST'])
@login_required
def checkin_do():
    """执行打卡接口。当天已打卡则返回提示，否则入库并返回成功。"""
    today = date.today()
    
    # 判断今日是否已打卡（数据库层已有唯一约束保障）
    existing = CheckInRecord.query.filter_by(
        user_id=current_user.id, checkin_date=today
    ).first()
    
    if existing:
        return jsonify({'success': False, 'message': '今天已经打过卡了！'})
    
    record = CheckInRecord(user_id=current_user.id, checkin_date=today)
    db.session.add(record)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '打卡成功！坚持加油 💪'})


@app.route('/checkin/day/<date_str>')
@login_required
def checkin_day_detail(date_str):
    """返回指定日期（YYYY-MM-DD）的热量摄入与消耗详情，用于打卡日历弹框展示。"""
    try:
        day = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': '日期格式错误'}), 400

    # 获取当日饮食记录
    diet_records = DietRecord.query.filter_by(
        user_id=current_user.id, record_date=day
    ).all()
    total_intake = sum(r.calories for r in diet_records)

    breakfast = [r.to_dict() for r in diet_records if r.meal_type == 'breakfast']
    lunch     = [r.to_dict() for r in diet_records if r.meal_type == 'lunch']
    dinner    = [r.to_dict() for r in diet_records if r.meal_type == 'dinner']

    # 获取当日运动消耗
    exercise = ExerciseRecord.query.filter_by(
        user_id=current_user.id, record_date=day
    ).first()
    exercise_burn = exercise.calories_burned if exercise else 0
    exercise_desc = exercise.description if exercise else ''

    # 计算 BMR 和净热量
    bmr = get_user_bmr(current_user)
    total_burn = bmr + exercise_burn
    net = total_intake - total_burn  # 净热量差：正数过剩，负数亏缺

    # 判断该日是否已打卡
    checked = CheckInRecord.query.filter_by(
        user_id=current_user.id, checkin_date=day
    ).first() is not None

    return jsonify({
        'success': True,
        'date': date_str,
        'checked': checked,
        'total_intake': round(total_intake, 1),
        'bmr': round(bmr, 1),
        'exercise_burn': round(exercise_burn, 1),
        'total_burn': round(total_burn, 1),
        'net': round(net, 1),
        'exercise_desc': exercise_desc,
        'breakfast': breakfast,
        'lunch': lunch,
        'dinner': dinner,
    })




# =====================
# AI 对话路由
# =====================
@app.route('/chat')
@login_required
def chat():
    """智能健康助手对话页。"""
    return render_template('chat.html')


@app.route('/chat/message', methods=['POST'])
@login_required
def chat_message():
    """
    AI 对话消息接口。
    接收前端传入的对话历史（messages 列表），
    调用 DeepSeek（chat_with_assistant）返回助手回复。
    """
    data = request.get_json()
    messages = data.get('messages', [])
    
    if not messages:
        return jsonify({'success': False, 'message': '消息不能为空'}), 400
    
    # 调用 ai_utils.py 中的 DeepSeek 对话接口
    response = chat_with_assistant(messages)
    return jsonify({'success': True, 'response': response})


# =====================
# 个人资料 & BMR 辅助函数
# =====================
def calc_bmr(height, weight_kg, age, gender):
    """
    使用 Mifflin-St Jeor 公式计算基础代谢率（BMR）。

    公式：
      男性 BMR = 10 * 体重(kg) + 6.25 * 身高(cm) - 5 * 年龄 + 5
      女性 BMR = 10 * 体重(kg) + 6.25 * 身高(cm) - 5 * 年龄 - 161

    Args:
        height (float): 身高，单位 cm。
        weight_kg (float): 体重，单位 kg。
        age (int): 年龄。
        gender (str): '男性'/'male' 或 '女性'/'female'。

    Returns:
        float | None: BMR 值（kcal/天），参数不完整时返回 None。
    """
    if not all([height, weight_kg, age, gender]):
        return None
    base = 10 * weight_kg + 6.25 * height - 5 * age
    return round(base + 5 if gender == 'male' else base - 161, 1)

def get_user_bmr(user):
    """获取用户 BMR，若个人资料不完整则返回配置文件中的默认值。"""
    bmr = calc_bmr(user.height, user.weight_kg, user.age, user.gender)
    return bmr if bmr is not None else app.config.get('DEFAULT_BMR', 1800)


@app.route('/profile')
@login_required
def profile():
    """个人资料页：展示用户基本信息与当前 BMR。"""
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
    """更新个人资料表单。若更新了体重，同时自动同步一条体重记录到体重表。"""
    try:
        height = request.form.get('height', '').strip()
        weight_kg = request.form.get('weight_kg', '').strip()
        age = request.form.get('age', '').strip()
        gender = request.form.get('gender', '').strip()

        # 重新查询 User 对象，确保 SQLAlchemy 能跟踪字段变更
        user = User.query.get(current_user.id)

        if height:
            user.height = float(height)
        if weight_kg:
            weight_val = float(weight_kg)
            user.weight_kg = weight_val
            # 更新体重资料时，同步创建/更新今日体重记录
            today = date.today()
            existing_weight = WeightRecord.query.filter_by(
                user_id=user.id, record_date=today
            ).first()
            if existing_weight:
                existing_weight.weight = weight_val
            else:
                new_weight = WeightRecord(
                    user_id=user.id,
                    weight=weight_val,
                    record_date=today
                )
                db.session.add(new_weight)
        if age:
            user.age = int(age)
        if gender in ('male', 'female'):
            user.gender = gender

        db.session.commit()
        flash('个人信息已更新！', 'success')
    except ValueError:
        flash('请输入有效数字', 'error')
    return redirect(url_for('profile'))


@app.route('/profile/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    """上传并保存用户头像图片。输入验证格式和大小，旧头像文件会被删除。"""
    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': '未选择文件'}), 400

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'message': '文件名为空'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_IMAGE_EXTS:
        return jsonify({'success': False, 'message': '仅支持 JPG / PNG / GIF / WebP 格式'}), 400

    # 限制上传大小：不超过 5 MB
    file.seek(0, 2)    # 移到文件末尾
    size = file.tell() # 读取文件字节数
    file.seek(0)       # 重置到文件头部
    if size > 5 * 1024 * 1024:
        return jsonify({'success': False, 'message': '图片不能超过 5 MB'}), 400

    # 删除旧头像文件（若存在）
    user = User.query.get(current_user.id)
    if user.avatar:
        old_path = os.path.join(AVATAR_FOLDER, user.avatar)
        if os.path.exists(old_path):
            os.remove(old_path)

    # 生成 UUID 文件名，避免重名
    filename = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(AVATAR_FOLDER, filename)
    file.save(save_path)

    # 更新数据库中的头像文件名
    user.avatar = filename
    db.session.commit()

    avatar_url = url_for('static', filename=f'uploads/avatars/{filename}')
    return jsonify({'success': True, 'avatar_url': avatar_url})


@app.route('/profile/settings')
@login_required
def settings():
    """设置页（包含修改密码等功能）。"""
    return render_template('settings.html')


@app.route('/api/send-change-pwd-code', methods=['POST'])
@login_required
def send_change_pwd_code():
    """向用户已绑定的邮箱发送修改密码的验证码。"""
    email = current_user.email
    if not email:
        return jsonify({'success': False, 'message': '账户未绑定邮箱，无法发送验证码'})

    # 生成 6 位数字验证码，存入 Session
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    session['pwd_change_code'] = code
    session['pwd_change_time'] = datetime.now().timestamp()

    try:
        msg = Message('健身达人 - 修改密码验证码', recipients=[email])
        msg.body = (
            f'您正在修改密码，验证码为：{code}\n'
            f'请在5分钟内使用，如非本人操作请忽略此邮件。'
        )
        mail.send(msg)  # 通过 Flask-Mail 发送密码修改验证码
        return jsonify({'success': True, 'message': f'验证码已发送至 {email}'})
    except Exception as e:
        print(f"Send change-pwd mail error: {e}")
        return jsonify({'success': False, 'message': '发送失败，请稍后重试'})


@app.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    """修改密码接口。校验验证码有效性和新密码合法性后完成密码更新。"""
    data = request.get_json()
    code = data.get('code', '').strip()
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    # 从 Session 获取验证码和发送时间
    session_code = session.get('pwd_change_code')
    session_time = session.get('pwd_change_time')

    if not session_code or not session_time:
        return jsonify({'success': False, 'message': '请先获取验证码'})

    # 验证码 5 分钟有效期检查
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

    # 更新密码哈希并清除 Session
    current_user.set_password(new_password)
    db.session.commit()
    session.pop('pwd_change_code', None)
    session.pop('pwd_change_time', None)
    return jsonify({'success': True, 'message': '密码修改成功！请重新登录'})


# =====================
# 应用启动入口
# =====================
if __name__ == '__main__':
    # 尝试创建数据库（若不存在）
    create_database_if_not_exists()
    
    with app.app_context():
        # 根据模型定义自动创建尚未存在的表（已存在的表不会被修改）
        db.create_all()
        print("Database tables created successfully.")
    
    # debug=True 开启调试模式（生产环境应关闭）
    app.run(debug=True, host='0.0.0.0', port=5002)
