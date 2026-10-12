import os
import secrets
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# ============================================================
# 应用配置类
# 集中管理数据库、第三方 AI API、邮件等核心配置项。
# 敏感信息（如 API Key）生产环境应从环境变量读取，
# 切勿将真实密钥直接提交到版本控制系统。
# ============================================================
class Config:
    # Flask Session 加密密钥，生产环境请替换为随机长字符串
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(48)
    
    # --------------------------------------------------------
    # MySQL 数据库连接配置（使用 PyMySQL 驱动）
    # 格式：mysql+pymysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4
    # --------------------------------------------------------
    # 在 .env 中设置 DATABASE_URL；未配置时使用本地 SQLite 便于开发。
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///fitness_app.db')
    # 关闭 SQLAlchemy 事件追踪，减少不必要的内存开销
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,   # 每次使用连接前 ping 检查，避免连接断开
        'pool_recycle': 300,     # 连接池中连接最长存活时间（秒），防止 MySQL 超时断连
    }
    
    # --------------------------------------------------------
    # 百度 AI 开放平台 API 配置
    # 用途：调用百度菜品识别接口，实现拍照识别食物功能。
    # 申请地址：https://ai.baidu.com/  →  图像识别 → 菜品识别
    # 需要在百度智能云创建应用，获取 API Key（AppID）和 Secret Key。
    # 接口文档：https://ai.baidu.com/ai-doc/IMAGERECOGNITION/Nk3bcxe21
    # --------------------------------------------------------
    BAIDU_API_KEY = os.environ.get('BAIDU_API_KEY', '')
    BAIDU_SECRET_KEY = os.environ.get('BAIDU_SECRET_KEY', '')
    
    # --------------------------------------------------------
    # DeepSeek API 配置，用于 AI 健康分析和智能对话。
    # 将 DEEPSEEK_API_KEY 放在本地 .env 文件或系统环境变量中。
    # --------------------------------------------------------
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
    DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash')
    DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
    
    # 用户未设置身高/体重/年龄时的默认基础代谢率（BMR），单位：kcal/天
    DEFAULT_BMR = 1800
    
    # --------------------------------------------------------
    # 文件上传配置
    # --------------------------------------------------------
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')  # 上传文件保存目录
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 单次上传文件大小限制：16 MB

    # --------------------------------------------------------
    # 邮件发送配置（用于注册验证码、修改密码等）
    # 使用 QQ 邮箱 SMTP 服务，需在 QQ 邮箱设置中开启 SMTP 并获取授权码。
    # --------------------------------------------------------
    MAIL_SERVER = 'smtp.qq.com'          # QQ 邮箱 SMTP 服务器地址
    MAIL_PORT = 465                      # SSL 加密端口
    MAIL_USE_SSL = True                  # 启用 SSL 加密
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = MAIL_USERNAME
