import requests
import base64
import json
from flask import current_app
from zhipuai import ZhipuAI


def get_baidu_access_token():
    """Get Baidu AI access token"""
    api_key = current_app.config['BAIDU_API_KEY']
    secret_key = current_app.config['BAIDU_SECRET_KEY']
    
    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
    
    try:
        response = requests.post(url, timeout=10)
        result = response.json()
        return result.get('access_token')
    except Exception as e:
        print(f"Error getting Baidu access token: {e}")
        return None


def recognize_food_image(image_data):
    """
    Recognize food from image using Baidu AI dish recognition API.
    image_data: bytes of the image
    Returns: list of dicts with 'name' and 'calorie' keys
    """
    access_token = get_baidu_access_token()
    if not access_token:
        return None
    
    url = f"https://aip.baidubce.com/rest/2.0/image-classify/v2/dish?access_token={access_token}"
    
    # Encode image to base64
    image_b64 = base64.b64encode(image_data).decode('utf-8')
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {'image': image_b64, 'top_num': 3}
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=15)
        result = response.json()
        
        if 'result' in result:
            foods = []
            has_non_food = False
            for item in result['result']:
                name = item.get('name', '未知食物')
                if name == '非菜':
                    has_non_food = True
                    continue
                calorie = item.get('calorie', 0)
                try:
                    calorie = float(calorie)
                except:
                    calorie = 0
                foods.append({'name': name, 'calorie': calorie})
            
            if not foods and has_non_food:
                return [{'name': '未识别出具体食物，请手动输入', 'calorie': 0}]
            elif not foods:
                return [{'name': '无法识别', 'calorie': 0}]
            return foods
        else:
            print(f"Baidu API error: {result}")
            return None
    except Exception as e:
        print(f"Error calling Baidu dish API: {e}")
        return None


def get_zhipu_client():
    """Get ZhipuAI client"""
    api_key = current_app.config['ZHIPU_API_KEY']
    return ZhipuAI(api_key=api_key)


def analyze_health_data(weight_data, calorie_data):
    """
    Call ZhipuAI to analyze health data and provide advice.
    weight_data: list of dicts with 'date' and 'weight'
    calorie_data: list of dicts with 'date' and 'calorie_diff'
    Returns: analysis text string
    """
    client = get_zhipu_client()
    model = current_app.config['ZHIPU_MODEL']
    
    # Build data description string
    weight_str = "\n".join([f"  {d['date']}: {d['weight']} kg" for d in weight_data[-7:]])
    calorie_str = "\n".join([f"  {d['date']}: 热量差 {d['calorie_diff']:+.0f} kcal" for d in calorie_data[-7:]])
    
    prompt = f"""作为专业营养师，请根据以下近7天的健康数据，给出简洁的健康建议（100字左右）：

近期体重数据：
{weight_str if weight_str else '  暂无数据'}

近期热量差数据（正数表示过剩，负数表示亏缺）：
{calorie_str if calorie_str else '  暂无数据'}

请分析体重变化趋势和热量摄入情况，给出专业且有鼓励性的健康建议。"""
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一位专业的营养师和健康顾问，请用温暖专业的语气给出健康建议。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling ZhipuAI for health analysis: {e}")
        return "暂时无法获取AI健康分析，请稍后重试。"


def chat_with_assistant(messages):
    """
    Chat with ZhipuAI health assistant.
    messages: list of dicts with 'role' and 'content'
    Returns: response text string
    """
    client = get_zhipu_client()
    model = current_app.config['ZHIPU_MODEL']
    
    # Build messages list with system prompt
    full_messages = [
        {
            "role": "system",
            "content": "你是一个贴心的健康与健身助手，回答应当简短、专业、有鼓励性。"
        }
    ] + messages
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=full_messages,
            max_tokens=500,
            temperature=0.8,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling ZhipuAI for chat: {e}")
        return "抱歉，助手暂时无法回应，请稍后重试。"
