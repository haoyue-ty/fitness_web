import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'fitness-app-secret-key-2024'
    
    # MySQL Database (port 3306 for Baota)
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://fitness:PMTMmMRpYRx343kh@127.0.0.1:3306/fitness?charset=utf8mb4'
    #SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:123456@127.0.0.1:3308/fitness_app?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Baidu AI API
    BAIDU_API_KEY = 'azpYF3xTeYg2HU8GQc9avyMI'
    BAIDU_SECRET_KEY = 'ro3w0ImdkNIzZUPzUftMDRigjiP8R5Jh'
    
    # ZhipuAI API
    ZHIPU_API_KEY = '1298a8e6745843e3bb2fa3de964cc2b8.hLfhANnzCGHg3b4A'
    ZHIPU_MODEL = 'glm-4-air'
    
    # Default BMR (kcal)
    DEFAULT_BMR = 1800
    
    # Upload folder
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # Email Config
    MAIL_SERVER = 'smtp.qq.com'
    MAIL_PORT = 465
    MAIL_USE_SSL = True
    MAIL_USERNAME = '2992383060@qq.com'
    MAIL_PASSWORD = 'ggqpurvzrqfndfje'
    MAIL_DEFAULT_SENDER = '2992383060@qq.com'
