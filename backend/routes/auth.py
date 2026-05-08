import os
import logging
import traceback
from flask import Blueprint, request, jsonify, g
import requests
from db import login, update_user_profile
from middleware.auth import auth_required

auth_bp = Blueprint('auth', __name__)

_logger = logging.getLogger(__name__)
APP_ID = os.environ.get('WX_APP_ID', '')
APP_SECRET = os.environ.get('WX_APP_SECRET', '')


@auth_bp.route('/login', methods=['POST'])
def handle_login():
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')
    phone_code = data.get('phone_code', '').strip()

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

    # 如果提供了 phone_code，在登录同时完成手机号获取
    phone = session.get('phone', '')
    if phone_code and not phone:
        try:
            token_resp = requests.get(
                'https://api.weixin.qq.com/cgi-bin/token'
                f'?grant_type=client_credential&appid={APP_ID}&secret={APP_SECRET}',
                timeout=10
            )
            token_data = token_resp.json()
            access_token = token_data.get('access_token')
            if access_token:
                phone_resp = requests.post(
                    f'https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}',
                    json={'code': phone_code},
                    timeout=10
                )
                phone_data = phone_resp.json()
                if phone_data.get('errcode') == 0:
                    phone_info = phone_data.get('phone_info', {})
                    phone_number = phone_info.get('purePhoneNumber', '')
                    if phone_number:
                        update_user_profile(result['openid'], phone=phone_number)
                        phone = phone_number
        except Exception:
            _logger.warning(f'Phone exchange during login failed: {traceback.format_exc()}')

    return jsonify({
        'token': session['token'],
        'user_id': session['user_id'],
        'phone': phone,
        'nickname': session.get('nickname', ''),
    })


@auth_bp.route('/exchange-phone', methods=['POST'])
@auth_required
def handle_exchange_phone():
    """微信小程序手机号换号接口"""
    data = request.get_json(silent=True) or {}
    phone_code = data.get('phone_code', '').strip()

    if not phone_code:
        return jsonify({'error': '缺少手机号凭证'}), 400

    # 获取 access_token
    try:
        token_resp = requests.get(
            'https://api.weixin.qq.com/cgi-bin/token'
            f'?grant_type=client_credential&appid={APP_ID}&secret={APP_SECRET}',
            timeout=10
        )
        token_data = token_resp.json()
        access_token = token_data.get('access_token')
        if not access_token:
            _logger.error(f'Failed to get access_token: {token_data}')
            return jsonify({'error': '获取微信凭证失败'}), 500
    except Exception:
        _logger.error(f'WeChat token API request failed: {traceback.format_exc()}')
        return jsonify({'error': '请求微信服务器失败'}), 500

    # 换取手机号
    try:
        phone_resp = requests.post(
            f'https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}',
            json={'code': phone_code},
            timeout=10
        )
        phone_data = phone_resp.json()
        if phone_data.get('errcode') != 0:
            _logger.error(f'Failed to get phone: {phone_data}')
            return jsonify({'error': '获取手机号失败', 'detail': phone_data.get('errmsg', '')}), 400

        phone_info = phone_data.get('phone_info', {})
        phone = phone_info.get('purePhoneNumber', '')
        if not phone:
            return jsonify({'error': '未获取到手机号'}), 400

        # 更新用户手机号
        result = update_user_profile(g.user['openId'], phone=phone)
        if result['success']:
            return jsonify({'success': True, 'phone': phone})
        return jsonify(result), 400
    except Exception:
        _logger.error(f'Phone exchange failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@auth_bp.route('/update-profile', methods=['POST'])
@auth_required
def handle_update_profile():
    """更新用户昵称和/或手机号"""
    data = request.get_json(silent=True) or {}
    nickname = data.get('nickname', '').strip()
    phone = data.get('phone', '').strip()

    if not nickname and not phone:
        return jsonify({'error': '缺少更新内容'}), 400
    if nickname and len(nickname) > 50:
        return jsonify({'error': '昵称最长50个字符'}), 400

    # 校验手机号格式
    import re
    if phone and not re.match(r'^1[3-9]\d{9}$', phone):
        return jsonify({'error': '手机号格式不正确'}), 400

    try:
        result = update_user_profile(g.user['openId'], nickname=nickname or None, phone=phone or None)
        if result['success']:
            resp = {'success': True}
            if nickname:
                resp['nickname'] = nickname
            if phone:
                resp['phone'] = phone
            return jsonify(resp)
        return jsonify(result), 400
    except Exception:
        _logger.error(f'Update profile failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500
