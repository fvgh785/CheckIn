import logging
import traceback
from flask import Blueprint, request, jsonify, g
from middleware.auth import auth_required
from db import check_in_by_user_id, get_stats_by_user_id

checkin_bp = Blueprint('checkin', __name__)
_logger = logging.getLogger(__name__)


@checkin_bp.route('/checkin', methods=['POST'])
@auth_required
def handle_checkin():
    try:
        result = check_in_by_user_id(g.user['userId'])
        if result['success']:
            return jsonify(result)
        return jsonify(result), 409
    except Exception:
        _logger.error(f'checkin failed for user {g.user.get("userId")}: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@checkin_bp.route('/stats', methods=['GET'])
@auth_required
def handle_stats():
    try:
        stats = get_stats_by_user_id(g.user['userId'])
        return jsonify(stats)
    except Exception:
        _logger.error(f'get_stats failed for user {g.user.get("userId")}: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500
