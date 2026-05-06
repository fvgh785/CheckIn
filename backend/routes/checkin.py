import logging
import traceback
from flask import Blueprint, request, jsonify, g
from middleware.auth import auth_required
from db import check_in_by_user_id, get_stats_by_user_id
from db_membership import feed_pet, update_wish_progress

checkin_bp = Blueprint('checkin', __name__)
_logger = logging.getLogger(__name__)


@checkin_bp.route('/checkin', methods=['POST'])
@auth_required
def handle_checkin():
    try:
        result = check_in_by_user_id(g.user['userId'])
        if result['success']:
            # 打卡成功后联动：喂食宠物 + 更新心愿进度（静默处理，不影响打卡返回）
            pet_result = None
            try:
                pet_result = feed_pet(g.user['userId'])
            except Exception:
                _logger.debug(f'feed_pet skipped for user {g.user["userId"]} (not a member or pet error)')

            try:
                update_wish_progress(g.user['userId'])
            except Exception:
                _logger.debug(f'update_wish_progress skipped for user {g.user["userId"]}')

            response_data = dict(result)
            if pet_result:
                response_data['pet'] = pet_result
            return jsonify(response_data)
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
