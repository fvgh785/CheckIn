import logging
import traceback
from functools import wraps
from flask import request, jsonify, g
from db import verify_token
from db_membership import is_member_active

_logger = logging.getLogger(__name__)


def membership_required(f):
    """会员权限校验装饰器：要求已登录且是有效会员"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # 先验证登录
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': '未登录'}), 401

        token = auth_header.split(' ', 1)[1]
        try:
            session = verify_token(token)
        except Exception:
            _logger.error(f'verify_token failed: {traceback.format_exc()}')
            return jsonify({'error': '服务器内部错误'}), 500

        if not session:
            return jsonify({'error': '登录已过期'}), 401

        g.user = session

        # 再验证会员
        try:
            if not is_member_active(session['userId']):
                return jsonify({'error': '该功能需要会员，请联系管理员开通'}), 403
        except Exception:
            _logger.error(f'membership check failed: {traceback.format_exc()}')
            return jsonify({'error': '服务器内部错误'}), 500

        return f(*args, **kwargs)

    return decorated
