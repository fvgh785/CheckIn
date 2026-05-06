import os
import logging
import traceback
from flask import Blueprint, request, jsonify
from db_membership import activate_membership, get_membership
from db import get_connection

admin_bp = Blueprint('admin', __name__)
_logger = logging.getLogger(__name__)

ADMIN_KEY = os.environ.get('ADMIN_KEY', '')

if not ADMIN_KEY:
    _logger.warning('ADMIN_KEY environment variable is not set! Admin API will reject all requests.')


def _check_admin():
    """验证管理后台密钥"""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False
    token = auth_header.split(' ', 1)[1]
    return token == ADMIN_KEY


@admin_bp.route('/membership/activate', methods=['POST'])
def handle_activate_membership():
    """管理后台：开通/续费会员"""
    if not _check_admin():
        return jsonify({'error': '无权限'}), 403

    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id', '').strip()
    months = data.get('months', 1)

    if not user_id:
        return jsonify({'error': '缺少用户ID'}), 400
    if not isinstance(months, int) or months < 1 or months > 36:
        return jsonify({'error': '月数需在1-36之间'}), 400

    try:
        result = activate_membership(user_id, months)
        return jsonify(result)
    except Exception:
        _logger.error(f'activate_membership failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/membership/status/<user_id>', methods=['GET'])
def handle_admin_membership_status():
    """管理后台：查询指定用户会员状态"""
    if not _check_admin():
        return jsonify({'error': '无权限'}), 403

    try:
        result = get_membership(user_id)
        return jsonify(result)
    except Exception:
        _logger.error(f'admin membership status failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/users', methods=['GET'])
def handle_user_list():
    """管理后台：获取用户列表"""
    if not _check_admin():
        return jsonify({'error': '无权限'}), 403

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT id, open_id, created_at FROM users ORDER BY created_at DESC LIMIT 100')
                rows = cur.fetchall()
                users = [{
                    'user_id': r['id'],
                    'open_id': r['open_id'][:20] + '...',
                    'created_at': str(r['created_at']),
                } for r in rows]
                return jsonify({'users': users})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'user list failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500
