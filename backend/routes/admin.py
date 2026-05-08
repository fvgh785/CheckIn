import logging
import traceback
import uuid
from datetime import date, datetime

from flask import Blueprint, request, jsonify, g

from middleware.admin_auth import admin_required, super_admin_required, _create_admin_token
from db import get_connection, init_db, check_in_by_user_id, get_stats_by_user_id, get_user_by_phone
from db_membership import (
    activate_membership, get_membership, get_pet, ensure_pet_exists,
    get_wishes, get_capsules, get_insight_history
)
from db_admin import (
    admin_login as db_admin_login, change_password, get_admin_list,
    create_admin, update_admin, delete_admin,
    write_admin_log, get_admin_logs, get_dashboard_stats,
    increment_admin_token_version, validate_password_strength,
)
from limiter import limiter

admin_bp = Blueprint('admin', __name__)
_logger = logging.getLogger(__name__)


def _is_valid_uuid(val):
    """校验字符串是否为有效的UUID格式"""
    try:
        uuid.UUID(val)
        return True
    except (ValueError, AttributeError):
        return False


def _sanitize_detail(data, fields_to_strip=('password', 'old_password', 'new_password')):
    """从日志详情中移除敏感字段"""
    if not isinstance(data, dict):
        return data
    return {k: ('***' if k in fields_to_strip else v) for k, v in data.items()}


# ======================== 登录认证 ========================

@admin_bp.route('/login', methods=['POST'])
@limiter.limit('10 per minute')
def handle_admin_login():
    """管理员登录（速率限制：10次/分钟/IP）"""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': '请输入用户名和密码'}), 400

    admin = db_admin_login(username, password)
    if not admin:
        return jsonify({'error': '用户名或密码错误'}), 401

    token = _create_admin_token(admin)
    write_admin_log(admin['id'], 'login', 'admin', admin['id'], f'管理员 {username} 登录')
    return jsonify({
        'token': token,
        'admin': {
            'id': admin['id'],
            'username': admin['username'],
            'role': admin['role'],
        }
    })


@admin_bp.route('/logout', methods=['POST'])
@admin_required
def handle_admin_logout():
    """管理员退出登录（递增 token_version 使所有Token立即失效）"""
    increment_admin_token_version(g.admin['id'])
    write_admin_log(g.admin['id'], 'logout', 'admin', g.admin['id'], f'管理员 {g.admin["username"]} 退出')
    return jsonify({'success': True, 'message': '已退出登录，所有Token已失效'})


@admin_bp.route('/me', methods=['GET'])
@admin_required
def handle_admin_me():
    """获取当前管理员信息"""
    return jsonify({
        'id': g.admin['id'],
        'username': g.admin['username'],
        'role': g.admin['role'],
    })


@admin_bp.route('/password', methods=['PUT'])
@admin_required
def handle_change_password():
    """修改密码"""
    data = request.get_json(silent=True) or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not old_password or not new_password:
        return jsonify({'error': '请输入原密码和新密码'}), 400
    # 密码强度校验
    check = validate_password_strength(new_password)
    if not check['valid']:
        return jsonify({'error': check['message']}), 400

    result = change_password(g.admin['id'], old_password, new_password)
    if result['success']:
        write_admin_log(g.admin['id'], 'update', 'admin', g.admin['id'], '修改密码')
        return jsonify(result)
    return jsonify(result), 400


# ======================== 数据看板 ========================

@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def handle_dashboard():
    """获取系统概览统计数据"""
    try:
        stats = get_dashboard_stats()
        return jsonify(stats)
    except Exception:
        _logger.error(f'dashboard failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 用户管理 ========================

@admin_bp.route('/users', methods=['GET'])
@admin_required
def handle_user_list():
    """获取用户列表（分页+搜索）"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        keyword = request.args.get('keyword', '').strip()

        conn = get_connection()
        try:
            offset = (page - 1) * page_size
            with conn.cursor() as cur:
                if keyword:
                    cur.execute(
                        'SELECT COUNT(*) as total FROM users WHERE open_id LIKE %s OR phone LIKE %s OR nickname LIKE %s OR email LIKE %s',
                        (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', f'%{keyword}%')
                    )
                    total = cur.fetchone()['total']
                    cur.execute(
                        '''SELECT u.id, u.open_id, u.phone, u.nickname, u.email, u.created_at,
                                  (SELECT COUNT(*) FROM check_ins WHERE user_id = u.id) as total_checkins,
                                  (SELECT COUNT(*) FROM memberships WHERE user_id = u.id AND status = 1 AND end_date >= %s) as is_member
                           FROM users u
                           WHERE u.open_id LIKE %s OR u.phone LIKE %s OR u.nickname LIKE %s OR u.email LIKE %s
                           ORDER BY u.created_at DESC LIMIT %s OFFSET %s''',
                        (date.today(), f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', page_size, offset)
                    )
                else:
                    cur.execute('SELECT COUNT(*) as total FROM users')
                    total = cur.fetchone()['total']
                    cur.execute(
                        '''SELECT u.id, u.open_id, u.phone, u.nickname, u.email, u.created_at,
                                  (SELECT COUNT(*) FROM check_ins WHERE user_id = u.id) as total_checkins,
                                  (SELECT COUNT(*) FROM memberships WHERE user_id = u.id AND status = 1 AND end_date >= %s) as is_member
                           FROM users u
                           ORDER BY u.created_at DESC LIMIT %s OFFSET %s''',
                        (date.today(), page_size, offset)
                    )
                rows = cur.fetchall()
                users = [{
                    'user_id': r['id'],
                    'open_id': r['open_id'][:20] + '...' if len(r['open_id']) > 20 else r['open_id'],
                    'phone': r.get('phone', ''),
                    'nickname': r.get('nickname', ''),
                    'email': r.get('email', ''),
                    'created_at': str(r['created_at']),
                    'total_checkins': r['total_checkins'],
                    'is_member': bool(r['is_member']),
                } for r in rows]
                return jsonify({'users': users, 'total': total, 'page': page, 'page_size': page_size})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'user list failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/users/<user_id>', methods=['GET'])
@admin_required
def handle_user_detail(user_id):
    """获取用户详情（含打卡统计）"""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
                user = cur.fetchone()
                if not user:
                    return jsonify({'error': '用户不存在'}), 404

                # 获取打卡统计
                stats = get_stats_by_user_id(user_id)

                # 获取会员状态
                membership = get_membership(user_id)

                # 获取最近打卡记录
                cur.execute(
                    'SELECT check_date FROM check_ins WHERE user_id = %s ORDER BY check_date DESC LIMIT 30',
                    (user_id,)
                )
                recent_checkins = [str(r['check_date']) for r in cur.fetchall()]

                return jsonify({
                    'user_id': user['id'],
                    'open_id': user['open_id'],
                    'phone': user.get('phone', ''),
                    'nickname': user.get('nickname', ''),
                    'email': user.get('email', ''),
                    'created_at': str(user['created_at']),
                    'stats': stats,
                    'membership': membership,
                    'recent_checkins': recent_checkins,
                })
        finally:
            conn.close()
    except Exception:
        _logger.error(f'user detail failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 会员管理 ========================

@admin_bp.route('/memberships', methods=['GET'])
@admin_required
def handle_membership_list():
    """获取会员列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)

        conn = get_connection()
        try:
            offset = (page - 1) * page_size
            with conn.cursor() as cur:
                today = date.today()
                cur.execute('SELECT COUNT(*) as total FROM memberships')
                total = cur.fetchone()['total']
                cur.execute(
                    '''SELECT m.*, u.open_id, u.phone, u.nickname, u.email
                       FROM memberships m
                       JOIN users u ON m.user_id = u.id
                       ORDER BY m.created_at DESC LIMIT %s OFFSET %s''',
                    (page_size, offset)
                )
                rows = cur.fetchall()
                memberships = [{
                    'id': r['id'],
                    'user_id': r['user_id'],
                    'open_id': r['open_id'][:20] + '...' if len(r['open_id']) > 20 else r['open_id'],
                    'phone': r.get('phone', ''),
                    'nickname': r.get('nickname', ''),
                    'email': r.get('email', ''),
                    'level': r['level'],
                    'start_date': str(r['start_date']),
                    'end_date': str(r['end_date']),
                    'status': r['status'],
                    'is_active': r['status'] == 1 and r['end_date'] >= today,
                    'created_at': str(r['created_at']),
                } for r in rows]
                return jsonify({'memberships': memberships, 'total': total, 'page': page, 'page_size': page_size})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'membership list failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/membership/activate', methods=['POST'])
@admin_required
def handle_activate_membership():
    """管理后台：开通/续费会员（支持 user_id 或 phone 参数）"""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id', '').strip()
    phone = data.get('phone', '').strip()
    months = data.get('months', 1)

    if not user_id and not phone:
        return jsonify({'error': '缺少用户ID或手机号'}), 400
    if not isinstance(months, int) or months < 1 or months > 36:
        return jsonify({'error': '月数需在1-36之间'}), 400

    # 如果提供了手机号，先查找用户
    if phone and not user_id:
        user = get_user_by_phone(phone)
        if not user:
            return jsonify({'error': '未找到该手机号对应的用户'}), 404
        user_id = user['id']

    try:
        result = activate_membership(user_id, months)
        if result['success']:
            write_admin_log(g.admin['id'], 'update', 'membership', user_id,
                            f'激活/续费会员 {months} 个月，到期: {result.get("end_date", "")}')
        return jsonify(result)
    except Exception:
        _logger.error(f'activate_membership failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/membership/status/<user_id>', methods=['GET'])
@admin_required
def handle_admin_membership_status(user_id):
    """管理后台：查询指定用户会员状态"""
    try:
        result = get_membership(user_id)
        return jsonify(result)
    except Exception:
        _logger.error(f'admin membership status failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/users/lookup', methods=['GET'])
@admin_required
def handle_lookup_user_by_phone():
    """按手机号查找用户"""
    phone = request.args.get('phone', '').strip()
    if not phone:
        return jsonify({'error': '缺少手机号'}), 400

    try:
        user = get_user_by_phone(phone)
        if not user:
            return jsonify({'error': '未找到该手机号对应的用户'}), 404
        return jsonify({'user': user})
    except Exception:
        _logger.error(f'lookup user by phone failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/membership/cancel', methods=['POST'])
@admin_required
def handle_cancel_membership():
    """撤销会员（设置状态为0）"""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id', '').strip()

    if not user_id:
        return jsonify({'error': '缺少用户ID'}), 400

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'UPDATE memberships SET status = 0 WHERE user_id = %s',
                    (user_id,)
                )
                affected = cur.rowcount
                conn.commit()
                if affected > 0:
                    write_admin_log(g.admin['id'], 'update', 'membership', user_id, '撤销会员')
                    return jsonify({'success': True, 'message': '会员已撤销'})
                return jsonify({'success': False, 'message': '该用户无会员记录'}), 404
        finally:
            conn.close()
    except Exception:
        _logger.error(f'cancel membership failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 打卡管理 ========================

@admin_bp.route('/checkins', methods=['GET'])
@admin_required
def handle_checkin_list():
    """获取打卡记录列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        user_id = request.args.get('user_id', '').strip()
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()

        conn = get_connection()
        try:
            offset = (page - 1) * page_size
            conditions = []
            params = []

            if user_id:
                conditions.append('ci.user_id = %s')
                params.append(user_id)
            if date_from:
                conditions.append('ci.check_date >= %s')
                params.append(date_from)
            if date_to:
                conditions.append('ci.check_date <= %s')
                params.append(date_to)

            where_clause = ' AND '.join(conditions) if conditions else '1=1'

            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT COUNT(*) as total FROM check_ins ci WHERE {where_clause}',
                    params
                )
                total = cur.fetchone()['total']

                cur.execute(
                    f'''SELECT ci.*, u.open_id
                        FROM check_ins ci
                        JOIN users u ON ci.user_id = u.id
                        WHERE {where_clause}
                        ORDER BY ci.check_date DESC, ci.created_at DESC
                        LIMIT %s OFFSET %s''',
                    params + [page_size, offset]
                )
                rows = cur.fetchall()
                checkins = [{
                    'id': r['id'],
                    'user_id': r['user_id'],
                    'open_id': r['open_id'][:20] + '...' if len(r['open_id']) > 20 else r['open_id'],
                    'check_date': str(r['check_date']),
                    'created_at': str(r['created_at']),
                } for r in rows]
                return jsonify({'checkins': checkins, 'total': total, 'page': page, 'page_size': page_size})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'checkin list failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/checkin/add', methods=['POST'])
@admin_required
def handle_admin_add_checkin():
    """管理后台：手动添加打卡"""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id', '').strip()
    check_date = data.get('check_date', '').strip()

    if not user_id:
        return jsonify({'error': '缺少用户ID'}), 400
    if not check_date:
        return jsonify({'error': '缺少打卡日期'}), 400

    # 验证日期格式
    try:
        date.fromisoformat(check_date)
    except ValueError:
        return jsonify({'error': '日期格式无效，需为YYYY-MM-DD'}), 400

    try:
        # 复用 check_in_by_user_id，保证与正常打卡一致的去重和校验逻辑
        result = check_in_by_user_id(user_id, check_date)
        if result['success']:
            write_admin_log(g.admin['id'], 'create', 'checkin', user_id,
                            f'手动添加打卡: {check_date}')
            return jsonify(result)
        return jsonify(result), 409 if '已打卡' in result['message'] else 404
    except Exception:
        _logger.error(f'admin add checkin failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/checkin/<checkin_id>', methods=['DELETE'])
@admin_required
def handle_delete_checkin(checkin_id):
    """删除打卡记录"""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM check_ins WHERE id = %s', (checkin_id,))
                record = cur.fetchone()
                if not record:
                    return jsonify({'error': '打卡记录不存在'}), 404

                cur.execute('DELETE FROM check_ins WHERE id = %s', (checkin_id,))
                conn.commit()
                write_admin_log(g.admin['id'], 'delete', 'checkin', record['user_id'],
                                f'删除打卡记录: {record["check_date"]}')
                return jsonify({'success': True, 'message': '打卡记录已删除'})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'delete checkin failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 小队管理 ========================

@admin_bp.route('/squads', methods=['GET'])
@admin_required
def handle_squad_list():
    """获取小队列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)

        conn = get_connection()
        try:
            offset = (page - 1) * page_size
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) as total FROM squads')
                total = cur.fetchone()['total']
                cur.execute(
                    '''SELECT s.*, u.open_id as owner_open_id,
                              (SELECT COUNT(*) FROM squad_members WHERE squad_id = s.id) as member_count
                       FROM squads s
                       JOIN users u ON s.owner_id = u.id
                       ORDER BY s.created_at DESC LIMIT %s OFFSET %s''',
                    (page_size, offset)
                )
                rows = cur.fetchall()
                squads = [{
                    'id': r['id'],
                    'name': r['name'],
                    'code': r['code'],
                    'owner_id': r['owner_id'],
                    'owner_open_id': r['owner_open_id'][:20] + '...' if len(r['owner_open_id']) > 20 else r['owner_open_id'],
                    'max_members': r['max_members'],
                    'member_count': r['member_count'],
                    'current_streak': r['current_streak'],
                    'max_streak': r['max_streak'],
                    'created_at': str(r['created_at']),
                } for r in rows]
                return jsonify({'squads': squads, 'total': total, 'page': page, 'page_size': page_size})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'squad list failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/squads/<squad_id>', methods=['DELETE'])
@admin_required
def handle_delete_squad(squad_id):
    """解散小队"""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM squads WHERE id = %s', (squad_id,))
                squad = cur.fetchone()
                if not squad:
                    return jsonify({'error': '小队不存在'}), 404

                cur.execute('DELETE FROM squad_members WHERE squad_id = %s', (squad_id,))
                cur.execute('DELETE FROM squads WHERE id = %s', (squad_id,))
                conn.commit()
                write_admin_log(g.admin['id'], 'delete', 'squad', squad_id,
                                f'解散小队: {squad["name"]}')
                return jsonify({'success': True, 'message': f'小队 "{squad["name"]}" 已解散'})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'delete squad failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 心愿管理 ========================

@admin_bp.route('/wishes', methods=['GET'])
@admin_required
def handle_wish_list():
    """获取心愿列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)

        conn = get_connection()
        try:
            offset = (page - 1) * page_size
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) as total FROM wishes')
                total = cur.fetchone()['total']
                cur.execute(
                    '''SELECT w.*, u.open_id
                       FROM wishes w
                       JOIN users u ON w.user_id = u.id
                       ORDER BY w.created_at DESC LIMIT %s OFFSET %s''',
                    (page_size, offset)
                )
                rows = cur.fetchall()
                wishes = [{
                    'id': r['id'],
                    'user_id': r['user_id'],
                    'open_id': r['open_id'][:20] + '...' if len(r['open_id']) > 20 else r['open_id'],
                    'content': r['content'],
                    'target_days': r['target_days'],
                    'current_days': r['current_days'],
                    'status': r['status'],
                    'created_at': str(r['created_at']),
                    'achieved_at': str(r['achieved_at']) if r['achieved_at'] else None,
                } for r in rows]
                return jsonify({'wishes': wishes, 'total': total, 'page': page, 'page_size': page_size})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'wish list failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/wishes/<wish_id>', methods=['DELETE'])
@admin_required
def handle_delete_wish(wish_id):
    """删除心愿"""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM wishes WHERE id = %s', (wish_id,))
                wish = cur.fetchone()
                if not wish:
                    return jsonify({'error': '心愿不存在'}), 404

                cur.execute('DELETE FROM wishes WHERE id = %s', (wish_id,))
                conn.commit()
                write_admin_log(g.admin['id'], 'delete', 'wish', wish['user_id'],
                                f'删除心愿: {wish["content"]}')
                return jsonify({'success': True, 'message': '心愿已删除'})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'delete wish failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 时光胶囊管理 ========================

@admin_bp.route('/capsules', methods=['GET'])
@admin_required
def handle_capsule_list():
    """获取时光胶囊列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)

        conn = get_connection()
        try:
            offset = (page - 1) * page_size
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) as total FROM time_capsules')
                total = cur.fetchone()['total']
                cur.execute(
                    '''SELECT tc.*, u.open_id
                       FROM time_capsules tc
                       JOIN users u ON tc.user_id = u.id
                       ORDER BY tc.created_at DESC LIMIT %s OFFSET %s''',
                    (page_size, offset)
                )
                rows = cur.fetchall()
                capsules = [{
                    'id': r['id'],
                    'user_id': r['user_id'],
                    'open_id': r['open_id'][:20] + '...' if len(r['open_id']) > 20 else r['open_id'],
                    'content': r['content'][:50] + '...' if len(r['content']) > 50 else r['content'],
                    'target_streak': r['target_streak'],
                    'created_streak': r['created_streak'],
                    'status': r['status'],
                    'status_text': '已开启' if r['status'] == 1 else '封印中',
                    'created_at': str(r['created_at']),
                    'opened_at': str(r['opened_at']) if r['opened_at'] else None,
                } for r in rows]
                return jsonify({'capsules': capsules, 'total': total, 'page': page, 'page_size': page_size})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'capsule list failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/capsules/<capsule_id>', methods=['DELETE'])
@admin_required
def handle_delete_capsule(capsule_id):
    """删除时光胶囊"""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM time_capsules WHERE id = %s', (capsule_id,))
                capsule = cur.fetchone()
                if not capsule:
                    return jsonify({'error': '胶囊不存在'}), 404

                cur.execute('DELETE FROM time_capsules WHERE id = %s', (capsule_id,))
                conn.commit()
                write_admin_log(g.admin['id'], 'delete', 'capsule', capsule['user_id'], '删除时光胶囊')
                return jsonify({'success': True, 'message': '胶囊已删除'})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'delete capsule failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 宠物管理 ========================

@admin_bp.route('/pets', methods=['GET'])
@admin_required
def handle_pet_list():
    """获取宠物列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)

        conn = get_connection()
        try:
            offset = (page - 1) * page_size
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) as total FROM pets')
                total = cur.fetchone()['total']
                cur.execute(
                    '''SELECT p.*, u.open_id
                       FROM pets p
                       JOIN users u ON p.user_id = u.id
                       ORDER BY p.created_at DESC LIMIT %s OFFSET %s''',
                    (page_size, offset)
                )
                rows = cur.fetchall()
                pets = [{
                    'id': r['id'],
                    'user_id': r['user_id'],
                    'open_id': r['open_id'][:20] + '...' if len(r['open_id']) > 20 else r['open_id'],
                    'pet_type': r['pet_type'],
                    'pet_name': r['pet_name'],
                    'stage': r['stage'],
                    'mood': r['mood'],
                    'hunger': r['hunger'],
                    'exp': r['exp'],
                    'last_feed_date': str(r['last_feed_date']) if r['last_feed_date'] else None,
                    'created_at': str(r['created_at']),
                } for r in rows]
                return jsonify({'pets': pets, 'total': total, 'page': page, 'page_size': page_size})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'pet list failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/pets/<pet_id>', methods=['PUT'])
@admin_required
def handle_update_pet(pet_id):
    """修改宠物属性"""
    data = request.get_json(silent=True) or {}
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM pets WHERE id = %s', (pet_id,))
            pet = cur.fetchone()
            if not pet:
                return jsonify({'error': '宠物不存在'}), 404

            updates = []
            params = []

            for field in ['pet_name', 'pet_type', 'mood', 'hunger', 'exp', 'stage']:
                if field in data:
                    updates.append(f'{field} = %s')
                    params.append(data[field])

            if not updates:
                return jsonify({'error': '无更新内容'}), 400

            params.append(pet_id)
            set_clause = ', '.join(updates)
            sql = f'UPDATE pets SET {set_clause} WHERE id = %s'
            cur.execute(sql, params)
            conn.commit()
            write_admin_log(g.admin['id'], 'update', 'pet', pet['user_id'], f'修改宠物: {_sanitize_detail(data)}')
            return jsonify({'success': True, 'message': '宠物信息已更新'})
    finally:
        conn.close()


# ======================== 补签卡管理 ========================

@admin_bp.route('/makeup-cards', methods=['GET'])
@admin_required
def handle_makeup_card_list():
    """获取补签记录列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)

        conn = get_connection()
        try:
            offset = (page - 1) * page_size
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) as total FROM makeup_cards')
                total = cur.fetchone()['total']
                cur.execute(
                    '''SELECT mc.*, u.open_id
                       FROM makeup_cards mc
                       JOIN users u ON mc.user_id = u.id
                       ORDER BY mc.used_at DESC LIMIT %s OFFSET %s''',
                    (page_size, offset)
                )
                rows = cur.fetchall()
                cards = [{
                    'id': r['id'],
                    'user_id': r['user_id'],
                    'open_id': r['open_id'][:20] + '...' if len(r['open_id']) > 20 else r['open_id'],
                    'used_date': str(r['used_date']),
                    'used_at': str(r['used_at']),
                } for r in rows]
                return jsonify({'cards': cards, 'total': total, 'page': page, 'page_size': page_size})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'makeup card list failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== AI洞察管理 ========================

@admin_bp.route('/insights', methods=['GET'])
@admin_required
def handle_insight_list():
    """获取AI洞察列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)

        conn = get_connection()
        try:
            offset = (page - 1) * page_size
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) as total FROM ai_insights')
                total = cur.fetchone()['total']
                cur.execute(
                    '''SELECT ai.*, u.open_id
                       FROM ai_insights ai
                       JOIN users u ON ai.user_id = u.id
                       ORDER BY ai.created_at DESC LIMIT %s OFFSET %s''',
                    (page_size, offset)
                )
                rows = cur.fetchall()
                insights = [{
                    'id': r['id'],
                    'user_id': r['user_id'],
                    'open_id': r['open_id'][:20] + '...' if len(r['open_id']) > 20 else r['open_id'],
                    'week_start': str(r['week_start']),
                    'content': r['content'],
                    'created_at': str(r['created_at']),
                } for r in rows]
                return jsonify({'insights': insights, 'total': total, 'page': page, 'page_size': page_size})
        finally:
            conn.close()
    except Exception:
        _logger.error(f'insight list failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 管理员管理（超管专用） ========================

@admin_bp.route('/admins', methods=['GET'])
@super_admin_required
def handle_admin_list():
    """获取管理员列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        result = get_admin_list(page, page_size)
        return jsonify(result)
    except Exception:
        _logger.error(f'admin list failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/admins', methods=['POST'])
@super_admin_required
def handle_create_admin():
    """创建新管理员"""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'admin')

    if not username or not password:
        return jsonify({'error': '请输入用户名和密码'}), 400
    if len(username) < 3:
        return jsonify({'error': '用户名至少3个字符'}), 400
    if len(password) < 6:
        return jsonify({'error': '密码至少6个字符'}), 400
    if role not in ('admin', 'super_admin'):
        return jsonify({'error': '角色无效'}), 400

    try:
        result = create_admin(username, password, role)
        if result['success']:
            write_admin_log(g.admin['id'], 'create', 'admin', result['id'],
                            f'创建管理员: {username} ({role})')
            return jsonify(result), 201
        return jsonify(result), 400
    except Exception:
        _logger.error(f'create admin failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/admins/<admin_id>', methods=['PUT'])
@super_admin_required
def handle_update_admin(admin_id):
    """更新管理员信息"""
    data = request.get_json(silent=True) or {}
    # 角色校验
    role = data.get('role')
    if role is not None and role not in ('admin', 'super_admin'):
        return jsonify({'error': '角色无效'}), 400
    try:
        result = update_admin(
            admin_id,
            username=data.get('username'),
            password=data.get('password'),
            role=role,
            status=data.get('status'),
        )
        if result['success']:
            write_admin_log(g.admin['id'], 'update', 'admin', admin_id, f'更新管理员: {_sanitize_detail(data)}')
            return jsonify(result)
        return jsonify(result), 400
    except Exception:
        _logger.error(f'update admin failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@admin_bp.route('/admins/<admin_id>', methods=['DELETE'])
@super_admin_required
def handle_delete_admin(admin_id):
    """删除管理员"""
    if admin_id == g.admin['id']:
        return jsonify({'error': '不能删除自己'}), 400
    try:
        result = delete_admin(admin_id)
        if result['success']:
            write_admin_log(g.admin['id'], 'delete', 'admin', admin_id, '删除管理员')
            return jsonify(result)
        return jsonify(result), 400
    except Exception:
        _logger.error(f'delete admin failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 操作日志 ========================

@admin_bp.route('/logs', methods=['GET'])
@admin_required
def handle_log_list():
    """获取操作日志列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 50, type=int)
        admin_id = request.args.get('admin_id', '').strip() or None
        action = request.args.get('action', '').strip() or None
        target_type = request.args.get('target_type', '').strip() or None

        result = get_admin_logs(page, page_size, admin_id, action, target_type)
        return jsonify(result)
    except Exception:
        _logger.error(f'log list failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 系统配置 ========================

@admin_bp.route('/config', methods=['GET'])
@admin_required
def handle_get_config():
    """获取系统配置"""
    return jsonify({
        'makeup_card_limit': 3,
        'membership_level': 'premium',
        'app_version': '1.0.0',
        'environment': {
            'admin_jwt_secret_set': bool(True),  # 不暴露实际密钥
        }
    })


@admin_bp.route('/config', methods=['PUT'])
@admin_required
def handle_update_config():
    """更新系统配置"""
    data = request.get_json(silent=True) or {}
    # 目前仅做记录，配置实际存储在环境变量中
    write_admin_log(g.admin['id'], 'update', 'config', None, f'更新系统配置: {_sanitize_detail(data)}')
    return jsonify({'success': False, 'message': '配置管理功能尚未实现，请通过环境变量或重启服务修改配置'}), 501
