import logging
import traceback
from functools import wraps
from flask import request, jsonify, g
from db import verify_token

_logger = logging.getLogger(__name__)


def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
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
        return f(*args, **kwargs)

    return decorated
