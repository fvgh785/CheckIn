import os
import logging
import traceback
from flask import Blueprint, request, jsonify
import requests
from db import login

auth_bp = Blueprint('auth', __name__)

_logger = logging.getLogger(__name__)
APP_ID = os.environ.get('WX_APP_ID', '')
APP_SECRET = os.environ.get('WX_APP_SECRET', '')


@auth_bp.route('/login', methods=['POST'])
def handle_login():
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')

    if not code:
        return jsonify({'error': '缺少登录凭证'}), 400

    if not APP_ID or not APP_SECRET:
        return jsonify({'error': '服务器未配置微信小程序 AppID 和 AppSecret'}), 500

    url = (
        'https://api.weixin.qq.com/sns/jscode2session'
        f'?appid={APP_ID}&secret={APP_SECRET}&js_code={code}'
        '&grant_type=authorization_code'
    )

    try:
        resp = requests.get(url, timeout=10)
        result = resp.json()
    except Exception:
        _logger.error(f'WeChat API request failed: {traceback.format_exc()}')
        return jsonify({'error': '请求微信服务器失败'}), 500

    if result.get('errcode'):
        return jsonify({'error': '微信登录失败', 'detail': result.get('errmsg', '')}), 400

    try:
        session = login(result['openid'])
    except Exception:
        _logger.error(f'login failed for openid={result.get("openid")}: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500

    return jsonify({'token': session['token'], 'user_id': session['user_id']})
