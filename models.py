"""
models.py —— 数据库模型定义

使用 Flask-SQLAlchemy ORM 定义所有数据表结构。
包含以下数据模型：
  - User            用户信息（账号、资料、密码）
  - DietRecord      饮食记录（三餐食物与热量）
  - WeightRecord    体重记录
  - CheckInRecord   每日打卡记录
  - ExerciseRecord  运动消耗记录
"""

from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# 创建 SQLAlchemy 实例，后续在 app.py 中通过 db.init_app(app) 与 Flask 应用绑定
db = SQLAlchemy()


class User(UserMixin, db.Model):
    """
    用户模型
    继承 UserMixin 以支持 Flask-Login 的登录状态管理。
    对应数据库表：users
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)                        # 用户主键 ID（自增）
    username = db.Column(db.String(80), unique=True, nullable=False)    # 用户名（唯一，不可为空）
    email = db.Column(db.String(120), unique=True, nullable=True)       # 邮箱（唯一，可选，用于验证码）
    password_hash = db.Column(db.String(256), nullable=False)           # 密码哈希值（不存明文）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)        # 注册时间（UTC）

    # ---- 个人资料字段 ----
    height = db.Column(db.Float, nullable=True)       # 身高，单位：cm
    weight_kg = db.Column(db.Float, nullable=True)    # 体重，单位：kg（用于 BMR 计算初始值）
    age = db.Column(db.Integer, nullable=True)         # 年龄
    gender = db.Column(db.String(10), nullable=True)  # 性别：'male'（男）或 'female'（女）
    avatar = db.Column(db.String(200), nullable=True) # 头像文件名，存储在 static/uploads/avatars/ 下

    # ---- 关联关系（一对多）----
    # backref 允许通过 record.user 反向访问所属用户
    diet_records = db.relationship('DietRecord', backref='user', lazy=True)       # 饮食记录
    weight_records = db.relationship('WeightRecord', backref='user', lazy=True)   # 体重记录
    checkin_records = db.relationship('CheckInRecord', backref='user', lazy=True) # 打卡记录
    
    def set_password(self, password):
        """将明文密码加密后存储为哈希值"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """验证输入的明文密码是否与数据库中的哈希值匹配"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class DietRecord(db.Model):
    """
    饮食记录模型
    记录用户每日三餐（早餐/午餐/晚餐）的食物名称与热量。
    对应数据库表：diet_records
    """
    __tablename__ = 'diet_records'
    
    id = db.Column(db.Integer, primary_key=True)                                              # 记录主键 ID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)               # 关联用户 ID
    record_date = db.Column(db.Date, default=date.today, nullable=False)                      # 记录日期
    meal_type = db.Column(db.String(20), nullable=False)   # 餐次类型：breakfast / lunch / dinner
    food_name = db.Column(db.String(200), nullable=False)  # 食物名称（支持逗号分隔多种食物）
    calories = db.Column(db.Float, default=0)              # 该食物的热量，单位：kcal
    notes = db.Column(db.Text, nullable=True)              # 备注信息（可选）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    
    def to_dict(self):
        """将记录转换为字典格式，方便 JSON 序列化返回给前端"""
        return {
            'id': self.id,
            'meal_type': self.meal_type,
            'food_name': self.food_name,
            'calories': self.calories,
            'notes': self.notes,
            'record_date': self.record_date.strftime('%Y-%m-%d')
        }


class WeightRecord(db.Model):
    """
    体重记录模型
    每日记录用户体重，用于绘制体重趋势折线图和 AI 健康分析。
    对应数据库表：weight_records
    """
    __tablename__ = 'weight_records'
    
    id = db.Column(db.Integer, primary_key=True)                                     # 记录主键 ID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)      # 关联用户 ID
    record_date = db.Column(db.Date, default=date.today, nullable=False)             # 记录日期
    weight = db.Column(db.Float, nullable=False)   # 体重数值，单位：kg
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    
    def to_dict(self):
        """将记录转换为字典格式，方便 JSON 序列化返回给前端"""
        return {
            'id': self.id,
            'record_date': self.record_date.strftime('%Y-%m-%d'),
            'weight': self.weight
        }


class CheckInRecord(db.Model):
    """
    每日打卡记录模型
    记录用户每天是否完成打卡，同一用户同一天只能打卡一次（唯一约束）。
    对应数据库表：checkin_records
    """
    __tablename__ = 'checkin_records'
    
    id = db.Column(db.Integer, primary_key=True)                                      # 记录主键 ID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)       # 关联用户 ID
    checkin_date = db.Column(db.Date, default=date.today, nullable=False)             # 打卡日期
    created_at = db.Column(db.DateTime, default=datetime.utcnow)                      # 打卡时间
    
    # 联合唯一约束：同一用户同一天只允许一条打卡记录
    __table_args__ = (db.UniqueConstraint('user_id', 'checkin_date', name='unique_user_checkin'),)
    
    def to_dict(self):
        """将记录转换为字典格式，方便 JSON 序列化返回给前端"""
        return {
            'id': self.id,
            'checkin_date': self.checkin_date.strftime('%Y-%m-%d')
        }


class ExerciseRecord(db.Model):
    """
    运动消耗记录模型
    记录用户每日运动消耗的热量及运动描述，每日仅保留一条记录（更新覆盖）。
    对应数据库表：exercise_records
    """
    __tablename__ = 'exercise_records'
    
    id = db.Column(db.Integer, primary_key=True)                                      # 记录主键 ID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)       # 关联用户 ID
    record_date = db.Column(db.Date, default=date.today, nullable=False)              # 记录日期
    calories_burned = db.Column(db.Float, default=0)            # 运动消耗热量，单位：kcal
    description = db.Column(db.String(200), nullable=True)      # 运动描述（如"跑步30分钟"）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    
    def to_dict(self):
        """将记录转换为字典格式，方便 JSON 序列化返回给前端"""
        return {
            'id': self.id,
            'record_date': self.record_date.strftime('%Y-%m-%d'),
            'calories_burned': self.calories_burned,
            'description': self.description
        }
