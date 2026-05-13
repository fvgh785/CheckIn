import logging
import traceback
from datetime import date
from flask import Blueprint, request, jsonify, g
from middleware.auth import auth_required
from middleware.membership import membership_required
from db_membership import (
    get_membership, get_pet, ensure_pet_exists, feed_pet, update_pet_name,
    create_squad, join_squad, get_my_squad,
    create_wish, get_wishes, update_wish_progress,
    create_capsule, get_capsules, open_capsule,
    get_insight, get_insight_history,
    use_makeup_card, get_makeup_card_used_count, get_makeup_card_limit,
    get_monthly_checkin_status,
    is_member_active, activate_membership,
    check_insight_quota, use_insight_quota,
)
from ai_insight import generate_insight_for_user
from db_admin import get_config_value

membership_bp = Blueprint('membership', __name__)
_logger = logging.getLogger(__name__)


# ======================== 会员状态 ========================

@membership_bp.route('/membership/status', methods=['GET'])
@auth_required
def handle_membership_status():
    try:
        result = get_membership(g.user['userId'])
        return jsonify(result)
    except Exception:
        _logger.error(f'membership status failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 虚拟宠物 ========================

@membership_bp.route('/membership/pet', methods=['GET'])
@auth_required
def handle_get_pet():
    try:
        ensure_pet_exists(g.user['userId'])
        pet = get_pet(g.user['userId'])
        if not pet:
            return jsonify({'error': '宠物不存在，请先开通会员'}), 404
        return jsonify(pet)
    except Exception:
        _logger.error(f'get_pet failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@membership_bp.route('/membership/pet/feed', methods=['POST'])
@auth_required
def handle_feed_pet():
    """独立喂食接口（打卡时由checkin联动调用，也可单独调用）"""
    try:
        result = feed_pet(g.user['userId'])
        return jsonify(result)
    except Exception:
        _logger.error(f'feed_pet failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@membership_bp.route('/membership/pet/name', methods=['PUT'])
@membership_required
def handle_rename_pet():
    data = request.get_json(silent=True) or {}
    pet_name = data.get('pet_name', '').strip()
    if not pet_name or len(pet_name) > 20:
        return jsonify({'error': '宠物名需在1-20个字符之间'}), 400
    try:
        result = update_pet_name(g.user['userId'], pet_name)
        return jsonify(result)
    except Exception:
        _logger.error(f'rename_pet failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 打卡小队 ========================

@membership_bp.route('/squad/create', methods=['POST'])
@membership_required
def handle_create_squad():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name or len(name) > 20:
        return jsonify({'error': '小队名称需在1-20个字符之间'}), 400
    try:
        result = create_squad(g.user['userId'], name)
        if result['success']:
            return jsonify(result)
        return jsonify(result), 400
    except Exception:
        _logger.error(f'create_squad failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@membership_bp.route('/squad/join', methods=['POST'])
@auth_required
def handle_join_squad():
    """加入小队不需要会员，但创建小队需要会员"""
    data = request.get_json(silent=True) or {}
    code = data.get('code', '').strip().upper()
    if not code:
        return jsonify({'error': '请输入邀请码'}), 400
    try:
        result = join_squad(g.user['userId'], code)
        if result['success']:
            return jsonify(result)
        return jsonify(result), 400
    except Exception:
        _logger.error(f'join_squad failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@membership_bp.route('/squad/my', methods=['GET'])
@auth_required
def handle_my_squad():
    try:
        squad = get_my_squad(g.user['userId'])
        if not squad:
            return jsonify({'has_squad': False})
        return jsonify({'has_squad': True, 'squad': squad})
    except Exception:
        _logger.error(f'get_my_squad failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 心愿清单 ========================

@membership_bp.route('/wish/create', methods=['POST'])
@membership_required
def handle_create_wish():
    data = request.get_json(silent=True) or {}
    content = data.get('content', '').strip()
    target_days = data.get('target_days', 0)

    if not content or len(content) > 150:
        return jsonify({'error': '心愿内容需在1-150个字符之间'}), 400
    if not isinstance(target_days, int) or target_days < 7 or target_days > 365:
        return jsonify({'error': '目标天数需在7-365之间'}), 400

    try:
        result = create_wish(g.user['userId'], content, target_days)
        return jsonify(result)
    except Exception:
        _logger.error(f'create_wish failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@membership_bp.route('/wish/list', methods=['GET'])
@membership_required
def handle_get_wishes():
    try:
        wishes = get_wishes(g.user['userId'])
        return jsonify({'wishes': wishes})
    except Exception:
        _logger.error(f'get_wishes failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 时光胶囊 ========================

@membership_bp.route('/capsule/create', methods=['POST'])
@membership_required
def handle_create_capsule():
    data = request.get_json(silent=True) or {}
    content = data.get('content', '').strip()
    target_streak = data.get('target_streak', 0)
    current_streak = data.get('current_streak', 0)

    if not content or len(content) > 500:
        return jsonify({'error': '内容需在1-500个字符之间'}), 400
    if not isinstance(target_streak, int) or target_streak < 7 or target_streak > 365:
        return jsonify({'error': '目标连续天数需在7-365之间'}), 400

    try:
        result = create_capsule(g.user['userId'], content, target_streak, current_streak)
        return jsonify(result)
    except Exception:
        _logger.error(f'create_capsule failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@membership_bp.route('/capsule/list', methods=['GET'])
@membership_required
def handle_get_capsules():
    try:
        capsules = get_capsules(g.user['userId'])
        return jsonify({'capsules': capsules})
    except Exception:
        _logger.error(f'get_capsules failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@membership_bp.route('/capsule/open/<capsule_id>', methods=['POST'])
@membership_required
def handle_open_capsule(capsule_id):
    data = request.get_json(silent=True) or {}
    current_streak = data.get('current_streak', 0)
    try:
        result = open_capsule(capsule_id, g.user['userId'], current_streak)
        if result['success']:
            return jsonify(result)
        return jsonify(result), 400
    except Exception:
        _logger.error(f'open_capsule failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== AI洞察 ========================

@membership_bp.route('/insight/weekly', methods=['GET'])
@membership_required
def handle_get_insight():
    try:
        insight = get_insight(g.user['userId'])
        return jsonify(insight if insight else {'has_insight': False})
    except Exception:
        _logger.error(f'get_insight failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@membership_bp.route('/insight/history', methods=['GET'])
@membership_required
def handle_get_insight_history():
    try:
        history = get_insight_history(g.user['userId'])
        return jsonify({'insights': history})
    except Exception:
        _logger.error(f'get_insight_history failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@membership_bp.route('/insight/generate', methods=['POST'])
@membership_required
def handle_generate_insight():
    """手动触发生成本周AI洞察，每日上限3次"""
    try:
        user_id = g.user['userId']

        # 检查配额
        quota = check_insight_quota(user_id)
        if quota['remaining'] <= 0:
            return jsonify({
                'success': False,
                'message': f'今日已达上限（{quota["limit"]}次/天），请明天再来',
                'quota': quota,
            }), 429

        # 消耗配额
        use_result = use_insight_quota(user_id)
        if not use_result['success']:
            return jsonify({'success': False, 'message': use_result['message']}), 429

        # 强制生成本周洞察
        result = generate_insight_for_user(user_id, force=True)
        if not result:
            return jsonify({'success': False, 'message': '本周暂无打卡数据，无法生成洞察'}), 400

        return jsonify({
            'success': True,
            'insight': result,
            'quota': {'remaining': use_result['remaining'], 'limit': quota['limit']},
        })
    except Exception:
        _logger.error(f'generate_insight failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@membership_bp.route('/insight/generate/quota', methods=['GET'])
@membership_required
def handle_get_insight_quota():
    """查询今日手动生成洞察剩余次数"""
    try:
        quota = check_insight_quota(g.user['userId'])
        return jsonify(quota)
    except Exception:
        _logger.error(f'get_insight_quota failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 补签卡 ========================

@membership_bp.route('/checkin/makeup', methods=['POST'])
@membership_required
def handle_makeup():
    data = request.get_json(silent=True) or {}
    target_date = data.get('date', '').strip()

    if not target_date:
        return jsonify({'error': '请指定补签日期'}), 400

    try:
        # 验证日期格式
        date.fromisoformat(target_date)
    except ValueError:
        return jsonify({'error': '日期格式无效，需为YYYY-MM-DD'}), 400

    try:
        result = use_makeup_card(g.user['userId'], target_date)
        if result['success']:
            return jsonify(result)
        return jsonify(result), 400
    except Exception:
        _logger.error(f'makeup failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@membership_bp.route('/checkin/makeup/info', methods=['GET'])
@membership_required
def handle_makeup_info():
    try:
        used = get_makeup_card_used_count(g.user['userId'])
        limit = get_makeup_card_limit()
        return jsonify({
            'used': used,
            'limit': limit,
            'remaining': max(0, limit - used),
        })
    except Exception:
        _logger.error(f'makeup_info failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@membership_bp.route('/checkin/makeup/calendar', methods=['GET'])
@membership_required
def handle_makeup_calendar():
    """获取月度打卡日历数据，用于补签卡可视化"""
    try:
        today = date.today()
        year = request.args.get('year', today.year, type=int)
        month = request.args.get('month', today.month, type=int)

        # 参数校验
        if month < 1 or month > 12:
            return jsonify({'error': '月份需在 1-12 之间'}), 400
        if year < 2020 or year > today.year + 1:
            return jsonify({'error': '年份无效'}), 400

        status = get_monthly_checkin_status(g.user['userId'], year, month)
        used = get_makeup_card_used_count(g.user['userId'])
        limit_val = get_makeup_card_limit()

        return jsonify({
            'year': status['year'],
            'month': status['month'],
            'checked_dates': status['checked_dates'],
            'makeup_dates': status['makeup_dates'],
            'makeup_info': {
                'used': used,
                'limit': limit_val,
                'remaining': max(0, limit_val - used),
            }
        })
    except Exception:
        _logger.error(f'makeup_calendar failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 免费赠送会员 ========================

@membership_bp.route('/membership/free-trial', methods=['POST'])
@auth_required
def handle_free_trial():
    """检查用户是否符合免费赠送会员条件（注册日期在截止日期之前）"""
    try:
        cutoff_date_str = get_config_value('free_membership_cutoff_date')
        if not cutoff_date_str:
            return jsonify({'success': False, 'message': '当前暂无免费会员活动'}), 400

        try:
            cutoff_date = date.fromisoformat(cutoff_date_str)
        except ValueError:
            return jsonify({'error': '截止日期配置错误'}), 500

        # 检查是否已经是会员
        if is_member_active(g.user['userId']):
            return jsonify({'success': False, 'message': '您已是会员，无需重复领取'}), 400

        # 检查是否曾经领取过（已有过会员记录）
        from db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT COUNT(*) as cnt FROM memberships WHERE user_id = %s',
                    (g.user['userId'],)
                )
                if cur.fetchone()['cnt'] > 0:
                    return jsonify({'success': False, 'message': '您已领取过免费会员'}), 400
        finally:
            conn.close()

        # 获取用户注册时间
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT created_at FROM users WHERE id = %s', (g.user['userId'],))
                row = cur.fetchone()
                if not row:
                    return jsonify({'error': '用户不存在'}), 404
                user_created = row['created_at']
        finally:
            conn.close()

        # 判断注册时间是否在截止日期之前
        if isinstance(user_created, datetime):
            user_created_date = user_created.date()
        else:
            user_created_date = user_created

        if user_created_date >= cutoff_date:
            return jsonify({'success': False, 'message': f'仅限{cutoff_date_str}之前注册的用户参与'}), 400

        # 开通一个月会员
        result = activate_membership(g.user['userId'], 1)
        if result['success']:
            return jsonify({'success': True, 'message': '恭喜！已免费赠送您一个月会员'})
        return jsonify(result), 400

    except Exception:
        _logger.error(f'free_trial failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500
