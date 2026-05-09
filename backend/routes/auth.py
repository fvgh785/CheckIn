import os
import logging
import traceback
from flask import Blueprint, request, jsonify, g
import requests
from db import login, update_user_profile, get_user_profile, save_email_verification_code, verify_email_code, bind_email_to_user, generate_email_code, send_verification_email
from middleware.auth import auth_required

auth_bp = Blueprint('auth', __name__)

_logger = logging.getLogger(__name__)
APP_ID = os.environ.get('WX_APP_ID', '')
APP_SECRET = os.environ.get('WX_APP_SECRET', '')


@auth_bp.route('/login', methods=['POST'])
def handle_login():
    """微信一键登录（无需手机号）"""
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

    return jsonify({
        'token': session['token'],
        'user_id': session['user_id'],
        'nickname': session.get('nickname', ''),
        'email': session.get('email', ''),
    })


@auth_bp.route('/profile', methods=['GET'])
@auth_required
def handle_get_profile():
    """获取当前用户资料（昵称、邮箱）"""
    try:
        profile = get_user_profile(g.user['openId'])
        return jsonify(profile)
    except Exception:
        _logger.error(f'get profile failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@auth_bp.route('/send-email-code', methods=['POST'])
@auth_required
def handle_send_email_code():
    """发送邮箱验证码（绑定/换绑通用）"""
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()

    if not email:
        return jsonify({'error': '请输入邮箱地址'}), 400

    # 邮箱格式校验
    import re
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        return jsonify({'error': '邮箱格式不正确'}), 400

    # 获取当前用户已绑定的邮箱
    current_profile = get_user_profile(g.user['openId'])
    current_email = (current_profile.get('email') or '').strip()

    # 若新邮箱与当前已绑定邮箱一致，无需换绑
    if current_email and email == current_email:
        return jsonify({'error': '新邮箱与当前邮箱一致，无需换绑', 'code': 'SAME_EMAIL'}), 400

    # 校验该邮箱是否已被其他账号绑定
    from db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id FROM users WHERE email = %s AND open_id != %s',
                (email, g.user['openId'])
            )
            if cur.fetchone():
                return jsonify({'error': '该邮箱已被其他账号绑定', 'code': 'EMAIL_TAKEN'}), 400
    finally:
        conn.close()

    # 生成并保存验证码
    code = generate_email_code()
    if not save_email_verification_code(email, code):
        return jsonify({'error': '验证码生成失败，请稍后重试'}), 500

    # 发送邮件
    if not send_verification_email(email, code):
        _logger.warning(f'Failed to send verification email to {email}')
        return jsonify({'error': '邮件发送失败，请检查邮箱地址或稍后重试'}), 500

    return jsonify({'success': True, 'message': '验证码已发送'})


@auth_bp.route('/bind-email', methods=['POST'])
@auth_required
def handle_bind_email():
    """验证邮箱验证码并绑定"""
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    code = data.get('code', '').strip()

    if not email or not code:
        return jsonify({'error': '缺少邮箱或验证码'}), 400

    # 验证码校验
    if not verify_email_code(email, code):
        return jsonify({'error': '验证码错误或已过期'}), 400

    # 绑定邮箱
    result = bind_email_to_user(g.user['openId'], email)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 400


@auth_bp.route('/update-profile', methods=['POST'])
@auth_required
def handle_update_profile():
    """更新用户昵称"""
    data = request.get_json(silent=True) or {}
    nickname = data.get('nickname', '').strip()

    if not nickname:
        return jsonify({'error': '缺少昵称'}), 400
    if len(nickname) > 50:
        return jsonify({'error': '昵称最长50个字符'}), 400

    try:
        result = update_user_profile(g.user['openId'], nickname=nickname)
        if result['success']:
            return jsonify({'success': True, 'nickname': nickname})
        return jsonify(result), 400
    except Exception:
        _logger.error(f'Update profile failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500
