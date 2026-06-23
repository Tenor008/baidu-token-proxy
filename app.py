from flask import Flask, request, jsonify
import requests
import logging
import os

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ========== 环境变量读取，不写死敏感信息 ==========
BAIDU_APP_KEY = os.environ.get("BAIDU_APP_KEY", "")
BAIDU_APP_SECRET = os.environ.get("BAIDU_APP_SECRET", "")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "")
MUSIC_FOLDER = os.environ.get("MUSIC_FOLDER", "/我的音乐")
ALLOWED_EXT_STR = os.environ.get("ALLOWED_EXT", "mp3,flac,wav,m4a,aac")
ALLOWED_EXT = set(ALLOWED_EXT_STR.split(","))
# ==============================================

# 存储你的个人 Token
token_store = {
    "access_token": None,
    "refresh_token": None
}

TOKEN_URL = "https://openapi.baidu.com/oauth/2.0/token"
FILE_LIST_URL = "https://pan.baidu.com/rest/2.0/xpan/file"

def get_all_files(dir_path, access_token):
    """递归遍历所有子文件夹，获取所有音频文件"""
    all_files = []
    params = {
        "method": "list",
        "dir": dir_path,
        "access_token": access_token
    }
    resp = requests.get(FILE_LIST_URL, params=params)
    resp.raise_for_status()
    items = resp.json().get("list", [])
    
    for item in items:
        if item.get("isdir") == 1:
            # 递归遍历子文件夹
            sub_files = get_all_files(item["path"], access_token)
            all_files.extend(sub_files)
        else:
            # 检查文件后缀
            ext = item["path"].split(".")[-1].lower()
            if ext in ALLOWED_EXT:
                all_files.append(item)
    return all_files

@app.route('/callback')
def callback():
    """百度授权回调，拿到 code 后换 token 并保存"""
    code = request.args.get('code')
    if not code:
        return "缺少 code 参数", 400

    params = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": BAIDU_APP_KEY,
        "client_secret": BAIDU_APP_SECRET,
        "redirect_uri": REDIRECT_URI
    }

    try:
        resp = requests.get(TOKEN_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        token_store["access_token"] = data["access_token"]
        token_store["refresh_token"] = data["refresh_token"]
        return "授权成功！可以关闭此页面了", 200
    except Exception as e:
        logging.error(f"授权失败: {str(e)}")
        return "授权失败", 500

@app.route('/refresh')
def refresh_token():
    """自动刷新 access_token"""
    if not token_store["refresh_token"]:
        return jsonify({"error": "未授权"}), 401

    params = {
        "grant_type": "refresh_token",
        "refresh_token": token_store["refresh_token"],
        "client_id": BAIDU_APP_KEY,
        "client_secret": BAIDU_APP_SECRET
    }

    try:
        resp = requests.get(TOKEN_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        token_store["access_token"] = data["access_token"]
        return jsonify({"access_token": token_store["access_token"]}), 200
    except Exception as e:
        logging.error(f"刷新失败: {str(e)}")
        return jsonify({"error": "刷新失败"}), 500

@app.route('/list')
def list_music():
    """获取所有子文件夹里的音频文件"""
    if not token_store["access_token"]:
        return jsonify({"error": "未授权"}), 401
    try:
        all_audio = get_all_files(MUSIC_FOLDER, token_store["access_token"])
        return jsonify(all_audio)
    except Exception as e:
        logging.error(f"获取列表失败: {str(e)}")
        return jsonify({"error": "获取列表失败"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
