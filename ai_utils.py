"""
ai_utils.py —— AI 接口工具模块

本模块封装了两个第三方 AI 平台的调用逻辑：

1. 百度 AI 开放平台（文心）- 菜品识别
   ├── 官网：https://ai.baidu.com/
   ├── 产品：图像识别 → 菜品识别 API
   ├── 所用接口：POST https://aip.baidubce.com/rest/2.0/image-classify/v2/dish
   ├── 鉴权方式：OAuth 2.0，先用 API Key + Secret Key 换取 access_token，
   │           再携带 token 调用业务接口。
   └── 安装依赖：pip install requests

2. DeepSeek - 健康分析 & 智能对话
   ├── 官网：https://api-docs.deepseek.com/
   ├── 所用接口：POST https://api.deepseek.com/chat/completions
   └── 鉴权方式：Authorization: Bearer <API Key>

配置项（在 config.py 中设置）：
  BAIDU_API_KEY       百度应用的 API Key（Client ID）
  BAIDU_SECRET_KEY    百度应用的 Secret Key（Client Secret）
  DEEPSEEK_API_KEY    DeepSeek 的 API Key
  DEEPSEEK_MODEL      DeepSeek 使用的模型名称
"""

import requests   # HTTP 请求库，用于调用百度 REST API
import base64     # Base64 编码，将图片字节流转换为 API 所需格式
from flask import current_app   # 在应用上下文中访问 Flask 配置


# ============================================================
# 百度 AI 相关函数
# ============================================================

def get_baidu_access_token():
    """
    获取百度 AI 平台的 OAuth 2.0 访问令牌（access_token）。

    百度 AI 接口采用 Client Credentials 模式鉴权：
      - 每次调用业务接口前，需先通过 API Key + Secret Key 向
        https://aip.baidubce.com/oauth/2.0/token 换取 access_token。
      - access_token 有效期约 30 天，实际使用时可考虑缓存以减少请求次数。
      - 本函数每次调用均重新请求，适合低频调用场景。

    Returns:
        str | None: 成功返回 access_token 字符串，失败返回 None。
    """
    # 从 Flask 应用配置中读取百度 API 密钥
    api_key = current_app.config['BAIDU_API_KEY']
    secret_key = current_app.config['BAIDU_SECRET_KEY']

    # 构造 token 请求 URL（grant_type 固定为 client_credentials）
    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"

    try:
        response = requests.post(url, timeout=10)  # POST 请求，超时 10 秒
        result = response.json()
        return result.get('access_token')          # 提取并返回 access_token
    except Exception as e:
        print(f"Error getting Baidu access token: {e}")
        return None


def recognize_food_image(image_data):
    """
    调用百度 AI 菜品识别接口，从图片中识别食物名称和热量。

    接口信息：
      - URL：https://aip.baidubce.com/rest/2.0/image-classify/v2/dish
      - 方法：POST（application/x-www-form-urlencoded）
      - 参数：image（Base64 编码的图片）、top_num（返回结果数量）
      - 响应：result 列表，每项含 name（菜名）和 calorie（每百克热量 kcal）

    Args:
        image_data (bytes): 图片的原始字节数据（从上传文件读取）。

    Returns:
        list[dict] | None:
          成功返回食物列表，每项包含 'name'（食物名）和 'calorie'（热量）；
          识别失败或接口异常返回 None。
    """
    # 第一步：获取 access_token（百度 API 鉴权必须）
    access_token = get_baidu_access_token()
    if not access_token:
        return None

    # 构造菜品识别接口的请求 URL，将 access_token 作为查询参数
    url = f"https://aip.baidubce.com/rest/2.0/image-classify/v2/dish?access_token={access_token}"

    # 将图片字节数据编码为 Base64 字符串（百度 API 要求图片以 Base64 形式传递）
    image_b64 = base64.b64encode(image_data).decode('utf-8')

    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'image': image_b64,  # Base64 编码的图片数据
        'top_num': 3          # 返回置信度最高的前 3 个识别结果
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=15)
        result = response.json()

        if 'result' in result:
            foods = []
            has_non_food = False  # 标记是否出现了"非菜"（API 返回的非食物标识）

            for item in result['result']:
                name = item.get('name', '未知食物')

                # 百度 API 有时会返回"非菜"表示图片中没有食物，跳过此项
                if name == '非菜':
                    has_non_food = True
                    continue

                # 解析每百克热量（部分情况 API 返回字符串，统一转为浮点数）
                calorie = item.get('calorie', 0)
                try:
                    calorie = float(calorie)
                except:
                    calorie = 0

                foods.append({'name': name, 'calorie': calorie})

            # 若所有结果均为非食物，返回友好提示
            if not foods and has_non_food:
                return [{'name': '未识别出具体食物，请手动输入', 'calorie': 0}]
            elif not foods:
                return [{'name': '无法识别', 'calorie': 0}]

            return foods
        else:
            # API 返回了错误信息（如 error_code、error_msg）
            print(f"Baidu API error: {result}")
            return None
    except Exception as e:
        print(f"Error calling Baidu dish API: {e}")
        return None


# ============================================================
# DeepSeek 相关函数
# ============================================================

def _create_deepseek_completion(messages, max_tokens, temperature):
    """调用 DeepSeek Chat Completions 接口并返回回复文本。"""
    api_key = current_app.config['DEEPSEEK_API_KEY']
    if not api_key:
        raise RuntimeError('DEEPSEEK_API_KEY 未配置')

    response = requests.post(
        f"{current_app.config['DEEPSEEK_BASE_URL']}/chat/completions",
        headers={'Authorization': f'Bearer {api_key}'},
        json={
            'model': current_app.config['DEEPSEEK_MODEL'],
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'thinking': {'type': 'disabled'},
            'stream': False,
        },
        timeout=60,
    )
    response.raise_for_status()
    content = response.json()['choices'][0]['message']['content']
    if not content:
        raise RuntimeError('DeepSeek 返回了空回复')
    return content


def analyze_health_data(weight_data, calorie_data):
    """
    调用 DeepSeek 分析用户近 7 天的健康数据，生成专业建议。

    接口信息：
      - 使用 DeepSeek Chat Completions API
      - 模型：由 config.py 中的 DEEPSEEK_MODEL 指定
      - 接口文档：https://api-docs.deepseek.com/api/create-chat-completion/

    Args:
        weight_data (list[dict]): 体重数据列表，每项含 'date' 和 'weight'（kg）。
        calorie_data (list[dict]): 热量差数据列表，每项含 'date' 和 'calorie_diff'（kcal）。
                                   正值表示热量过剩，负值表示热量亏缺。

    Returns:
        str: AI 生成的健康建议文本；调用失败时返回错误提示字符串。
    """
    # 将近 7 天的体重数据格式化为易读字符串，传入 Prompt
    weight_str = "\n".join([f"  {d['date']}: {d['weight']} kg" for d in weight_data[-7:]])
    # 将近 7 天的热量差数据格式化，正数带 + 号
    calorie_str = "\n".join([f"  {d['date']}: 热量差 {d['calorie_diff']:+.0f} kcal" for d in calorie_data[-7:]])

    # 构造提示词（Prompt），角色扮演为专业营养师，要求给出简洁建议
    prompt = f"""作为专业营养师，请根据以下近7天的健康数据，给出简洁的健康建议（100字左右）：

近期体重数据：
{weight_str if weight_str else '  暂无数据'}

近期热量差数据（正数表示过剩，负数表示亏缺）：
{calorie_str if calorie_str else '  暂无数据'}

请分析体重变化趋势和热量摄入情况，给出专业且有鼓励性的健康建议。"""

    try:
        return _create_deepseek_completion(
            messages=[
                # system 角色设定 AI 的行为风格
                {"role": "system", "content": "你是一位专业的营养师和健康顾问，请用温暖专业的语气给出健康建议。"},
                # user 角色传入健康数据和分析请求
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7,
        )
    except Exception as e:
        print(f"Error calling DeepSeek for health analysis: {e}")
        return "暂时无法获取AI健康分析，请稍后重试。"


def chat_with_assistant(messages):
    """
    调用 DeepSeek 进行多轮健康问答对话。

    接口信息：
      - 使用 DeepSeek Chat Completions API
      - 模型：由 config.py 中的 DEEPSEEK_MODEL 指定
      - 接口文档：https://api-docs.deepseek.com/api/create-chat-completion/
      - 支持多轮对话：前端将完整的消息历史一次性发送，模型根据上下文回复。

    Args:
        messages (list[dict]): 对话消息列表，每项含 'role'（'user'/'assistant'）
                               和 'content'（消息内容）。

    Returns:
        str: AI 助手的回复文本；调用失败时返回错误提示字符串。
    """
    # 在消息列表头部插入 system 角色，设定助手人设（健康健身顾问）
    full_messages = [
        {
            "role": "system",
            "content": "你是一个贴心的健康与健身助手，回答应当简短、专业、有鼓励性。"
        }
    ] + messages  # 拼接前端传入的多轮对话历史

    try:
        return _create_deepseek_completion(
            messages=full_messages,
            max_tokens=500,
            temperature=0.8,
        )
    except Exception as e:
        print(f"Error calling DeepSeek for chat: {e}")
        return "抱歉，助手暂时无法回应，请稍后重试。"
