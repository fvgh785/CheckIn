import os
import logging
import traceback
from functools import wraps

import jwt
from flask import request, jsonify, g

from db_admin import get_admin_by_id

_logger = logging.getLogger(__name__)

ADMIN_JWT_SECRET = os.environ.get('ADMIN_JWT_SECRET')
if not ADMIN_JWT_SECRET:
    raise RuntimeError('ADMIN_JWT_SECRET environment variable is required')
ADMIN_JWT_EXPIRY_HOURS = 4


def _create_admin_token(admin):
    """签发管理员JWT（含 token_version 用于撤销支持）"""
    import datetime as dt
    payload = {
        'admin_id': admin['id'],
        'username': admin['username'],
        'role': admin['role'],
        'token_version': admin.get('token_version', 0),
        'exp': dt.datetime.utcnow() + dt.timedelta(hours=ADMIN_JWT_EXPIRY_HOURS),
        'iat': dt.datetime.utcnow(),
    }
    return jwt.encode(payload, ADMIN_JWT_SECRET, algorithm='HS256')


def _verify_admin_token(token):
    """验证管理员JWT，返回payload或None。
    同时校验：Token签名、过期时间、管理员是否存在且启用、
    Token版本是否匹配（支持撤销）、角色以数据库为准。
    """
    try:
        payload = jwt.decode(token, ADMIN_JWT_SECRET, algorithms=['HS256'])
        # 验证管理员是否仍存在且有效，同时获取最新角色和token_version
        admin = get_admin_by_id(payload['admin_id'])
        if not admin:
            return None
        # Token版本校验：密码修改或登出后 token_version 会递增，旧Token立即失效
        if admin.get('token_version', 0) != payload.get('token_version', 0):
            return None
        # 以数据库中的角色为准，不信任JWT中的role（防止角色降级后旧Token越权）
        return {
            'admin_id': payload['admin_id'],
            'username': payload['username'],
            'role': admin['role'],
        }
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        _logger.error(f'verify_admin_token failed: {traceback.format_exc()}')
        return None


def admin_required(f):
    """管理员鉴权装饰器：要求已登录的管理员"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': '未登录'}), 401

        token = auth_header.split(' ', 1)[1]
        payload = _verify_admin_token(token)
        if not payload:
            return jsonify({'error': '登录已过期或无效'}), 401

        g.admin = {
            'id': payload['admin_id'],
            'username': payload['username'],
            'role': payload['role'],
        }
        return f(*args, **kwargs)

    return decorated


def super_admin_required(f):
    """超级管理员鉴权装饰器：要求超管角色"""
    @wraps(f)
    @admin_required
    def decorated(*args, **kwargs):
        if g.admin.get('role') != 'super_admin':
            return jsonify({'error': '需要超级管理员权限'}), 403
        return f(*args, **kwargs)

    return decorated
