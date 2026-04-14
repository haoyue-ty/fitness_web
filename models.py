from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Profile fields
    height = db.Column(db.Float, nullable=True)       # cm
    weight_kg = db.Column(db.Float, nullable=True)    # kg
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)  # 'male' or 'female'
    avatar = db.Column(db.String(200), nullable=True) # avatar filename

    
    diet_records = db.relationship('DietRecord', backref='user', lazy=True)
    weight_records = db.relationship('WeightRecord', backref='user', lazy=True)
    checkin_records = db.relationship('CheckInRecord', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class DietRecord(db.Model):
    __tablename__ = 'diet_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    record_date = db.Column(db.Date, default=date.today, nullable=False)
    meal_type = db.Column(db.String(20), nullable=False)  # breakfast, lunch, dinner
    food_name = db.Column(db.String(200), nullable=False)
    calories = db.Column(db.Float, default=0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'meal_type': self.meal_type,
            'food_name': self.food_name,
            'calories': self.calories,
            'notes': self.notes,
            'record_date': self.record_date.strftime('%Y-%m-%d')
        }


class WeightRecord(db.Model):
    __tablename__ = 'weight_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    record_date = db.Column(db.Date, default=date.today, nullable=False)
    weight = db.Column(db.Float, nullable=False)  # kg
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'record_date': self.record_date.strftime('%Y-%m-%d'),
            'weight': self.weight
        }


class CheckInRecord(db.Model):
    __tablename__ = 'checkin_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    checkin_date = db.Column(db.Date, default=date.today, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'checkin_date', name='unique_user_checkin'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'checkin_date': self.checkin_date.strftime('%Y-%m-%d')
        }


class ExerciseRecord(db.Model):
    __tablename__ = 'exercise_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    record_date = db.Column(db.Date, default=date.today, nullable=False)
    calories_burned = db.Column(db.Float, default=0)
    description = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'record_date': self.record_date.strftime('%Y-%m-%d'),
            'calories_burned': self.calories_burned,
            'description': self.description
        }
