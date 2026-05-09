import uuid
import logging
import traceback
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash, check_password_hash

from db import get_connection, init_db

_logger = logging.getLogger(__name__)

# 登录锁定配置
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def validate_password_strength(password):
    """验证密码强度：至少8位，包含字母和数字"""
    if len(password) < 8:
        return {'valid': False, 'message': '密码至少8位'}
    if not any(c.isalpha() for c in password):
        return {'valid': False, 'message': '密码需包含字母'}
    if not any(c.isdigit() for c in password):
        return {'valid': False, 'message': '密码需包含数字'}
    return {'valid': True}


def _increment_token_version(cur, admin_id):
    """递增管理员的 token_version，使所有旧Token失效"""
    cur.execute(
        'UPDATE admins SET token_version = token_version + 1 WHERE id = %s',
        (admin_id,)
    )


# ======================== 管理员账号管理 ========================

def admin_login(username, password):
    """管理员登录验证，成功返回管理员信息，失败返回None。
    包含账户锁定检查：连续失败 MAX_FAILED_ATTEMPTS 次后锁定 LOCKOUT_MINUTES 分钟。
    """
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT * FROM admins WHERE username = %s AND status = 1',
                (username,)
            )
            row = cur.fetchone()
            if not row:
                return None

            # 检查账户锁定
            if row.get('locked_until') and row['locked_until'] > datetime.now():
                return None  # 账户已锁定

            if not check_password_hash(row['password_hash'], password):
                # 记录失败
                new_failed = (row.get('failed_attempts') or 0) + 1
                if new_failed >= MAX_FAILED_ATTEMPTS:
                    lock_until = datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)
                    cur.execute(
                        'UPDATE admins SET failed_attempts = %s, locked_until = %s WHERE id = %s',
                        (new_failed, lock_until, row['id'])
                    )
                    _logger.warning(f'Admin {username} locked until {lock_until}')
                else:
                    cur.execute(
                        'UPDATE admins SET failed_attempts = %s WHERE id = %s',
                        (new_failed, row['id'])
                    )
                conn.commit()
                return None

            # 登录成功：清除失败计数和锁定
            cur.execute(
                'UPDATE admins SET failed_attempts = 0, locked_until = NULL WHERE id = %s',
                (row['id'],)
            )
            conn.commit()
            return {
                'id': row['id'],
                'username': row['username'],
                'role': row['role'],
                'token_version': row.get('token_version') or 0,
            }
    finally:
        conn.close()


def get_admin_by_id(admin_id):
    """根据ID获取管理员信息（含 token_version 用于Token撤销校验）"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM admins WHERE id = %s AND status = 1', (admin_id,))
            row = cur.fetchone()
            if not row:
                return None
            return {
                'id': row['id'],
                'username': row['username'],
                'role': row['role'],
                'token_version': row.get('token_version') or 0,
            }
    finally:
        conn.close()


def change_password(admin_id, old_password, new_password):
    """修改管理员密码（同时递增 token_version 使旧Token失效）"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM admins WHERE id = %s', (admin_id,))
            row = cur.fetchone()
            if not row:
                return {'success': False, 'message': '管理员不存在'}
            if not check_password_hash(row['password_hash'], old_password):
                return {'success': False, 'message': '原密码错误'}

            new_hash = generate_password_hash(new_password)
            _increment_token_version(cur, admin_id)
            cur.execute(
                'UPDATE admins SET password_hash = %s WHERE id = %s',
                (new_hash, admin_id)
            )
            conn.commit()
            return {'success': True, 'message': '密码修改成功，已有Token已失效'}
    finally:
        conn.close()


def get_admin_list(page=1, page_size=20):
    """获取管理员列表（仅超管可调用，排除已删除的管理员）"""
    init_db()
    conn = get_connection()
    try:
        offset = (page - 1) * page_size
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) as total FROM admins WHERE status = 1')
            total = cur.fetchone()['total']
            cur.execute(
                'SELECT id, username, role, status, created_at FROM admins WHERE status = 1 ORDER BY created_at ASC LIMIT %s OFFSET %s',
                (page_size, offset)
            )
            rows = cur.fetchall()
            admins = [{
                'id': r['id'],
                'username': r['username'],
                'role': r['role'],
                'status': r['status'],
                'created_at': str(r['created_at']),
            } for r in rows]
            return {'admins': admins, 'total': total, 'page': page, 'page_size': page_size}
    finally:
        conn.close()


def create_admin(username, password, role='admin'):
    """创建新管理员"""
    init_db()
    # 密码强度校验
    check = validate_password_strength(password)
    if not check['valid']:
        return {'success': False, 'message': check['message']}

    conn = get_connection()
    try:
        admin_id = str(uuid.uuid4())
        pw_hash = generate_password_hash(password)
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO admins (id, username, password_hash, role) VALUES (%s, %s, %s, %s)',
                (admin_id, username, pw_hash, role)
            )
            conn.commit()
            return {'success': True, 'id': admin_id, 'username': username, 'role': role}
    except Exception:
        _logger.error(f'create_admin failed: {traceback.format_exc()}')
        return {'success': False, 'message': '创建失败，用户名可能已存在'}
    finally:
        conn.close()


def update_admin(admin_id, username=None, password=None, role=None, status=None):
    """更新管理员信息（修改密码时递增 token_version）"""
    init_db()
    # 密码强度校验
    if password is not None:
        check = validate_password_strength(password)
        if not check['valid']:
            return {'success': False, 'message': check['message']}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM admins WHERE id = %s', (admin_id,))
            if not cur.fetchone():
                return {'success': False, 'message': '管理员不存在'}

            updates = []
            params = []
            if username is not None:
                updates.append('username = %s')
                params.append(username)
            if password is not None:
                updates.append('password_hash = %s')
                params.append(generate_password_hash(password))
                # 密码修改时递增 token_version
                _increment_token_version(cur, admin_id)
            if role is not None:
                updates.append('role = %s')
                params.append(role)
                # 角色变更时递增 token_version（强制重新登录以获取最新角色）
                _increment_token_version(cur, admin_id)
            if status is not None:
                updates.append('status = %s')
                params.append(status)
                # 禁用/删除时递增 token_version
                _increment_token_version(cur, admin_id)

            if not updates:
                return {'success': False, 'message': '无更新内容'}

            params.append(admin_id)
            sql = f'UPDATE admins SET {", ".join(updates)} WHERE id = %s'
            cur.execute(sql, params)
            conn.commit()
            return {'success': True, 'message': '更新成功'}
    except Exception:
        _logger.error(f'update_admin failed: {traceback.format_exc()}')
        return {'success': False, 'message': '更新失败'}
    finally:
        conn.close()


def delete_admin(admin_id):
    """删除管理员（软删除，status=0，同时递增 token_version 使Token失效）"""
    return update_admin(admin_id, status=0)


def increment_admin_token_version(admin_id):
    """公开接口：递增 token_version 使所有旧Token失效（用于登出）"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            _increment_token_version(cur, admin_id)
            conn.commit()
            return True
    except Exception:
        _logger.error(f'increment_token_version failed: {traceback.format_exc()}')
        return False
    finally:
        conn.close()


# ======================== 操作日志 ========================

def write_admin_log(admin_id, action, target_type, target_id=None, detail=None):
    """记录管理操作日志"""
    init_db()
    conn = get_connection()
    try:
        log_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO admin_logs (id, admin_id, action, target_type, target_id, detail) VALUES (%s, %s, %s, %s, %s, %s)',
                (log_id, admin_id, action, target_type, target_id, detail)
            )
            conn.commit()
    except Exception:
        _logger.error(f'write_admin_log failed: {traceback.format_exc()}')
    finally:
        conn.close()


def get_admin_logs(page=1, page_size=50, admin_id=None, action=None, target_type=None):
    """查询操作日志"""
    init_db()
    conn = get_connection()
    try:
        offset = (page - 1) * page_size
        conditions = []
        params = []

        if admin_id:
            conditions.append('al.admin_id = %s')
            params.append(admin_id)
        if action:
            conditions.append('al.action = %s')
            params.append(action)
        if target_type:
            conditions.append('al.target_type = %s')
            params.append(target_type)

        where_clause = ' AND '.join(conditions) if conditions else '1=1'

        with conn.cursor() as cur:
            cur.execute(
                f'SELECT COUNT(*) as total FROM admin_logs al WHERE {where_clause}',
                params
            )
            total = cur.fetchone()['total']

            cur.execute(
                f'''SELECT al.*, a.username as admin_username
                    FROM admin_logs al
                    LEFT JOIN admins a ON al.admin_id = a.id
                    WHERE {where_clause}
                    ORDER BY al.created_at DESC
                    LIMIT %s OFFSET %s''',
                params + [page_size, offset]
            )
            rows = cur.fetchall()
            logs = [{
                'id': r['id'],
                'admin_id': r['admin_id'],
                'admin_username': r.get('admin_username', ''),
                'action': r['action'],
                'target_type': r['target_type'],
                'target_id': r['target_id'],
                'detail': r['detail'],
                'created_at': str(r['created_at']),
            } for r in rows]
            return {'logs': logs, 'total': total, 'page': page, 'page_size': page_size}
    finally:
        conn.close()


# ======================== 系统配置 ========================

DEFAULT_MAKEUP_CARD_LIMIT = 3


def get_system_config():
    """读取所有系统配置，返回 dict"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT config_key, config_value FROM system_config')
            rows = cur.fetchall()
            config = {}
            for r in rows:
                config[r['config_key']] = r['config_value']
            return config
    finally:
        conn.close()


def get_config_value(key, default=None):
    """读取单个配置值"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT config_value FROM system_config WHERE config_key = %s', (key,))
            row = cur.fetchone()
            return row['config_value'] if row else default
    finally:
        conn.close()


def set_system_config(key, value):
    """设置系统配置，value 转为字符串存储"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO system_config (config_key, config_value) VALUES (%s, %s) '
                'ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)',
                (key, str(value))
            )
            conn.commit()
            return True
    except Exception:
        _logger.error(f'set_system_config failed: {traceback.format_exc()}')
        return False
    finally:
        conn.close()


# ======================== 数据看板统计 ========================

def get_dashboard_stats():
    """获取系统概览统计数据"""
    init_db()
    conn = get_connection()
    try:
        today = date.today()
        with conn.cursor() as cur:
            stats = {}

            # 用户总数
            cur.execute('SELECT COUNT(*) as cnt FROM users')
            stats['total_users'] = cur.fetchone()['cnt']

            # 今日打卡人数
            cur.execute(
                'SELECT COUNT(DISTINCT user_id) as cnt FROM check_ins WHERE check_date = %s',
                (today,)
            )
            stats['today_checkins'] = cur.fetchone()['cnt']

            # 活跃会员数
            cur.execute(
                'SELECT COUNT(*) as cnt FROM memberships WHERE status = 1 AND end_date >= %s',
                (today,)
            )
            stats['active_members'] = cur.fetchone()['cnt']

            # 总打卡次数
            cur.execute('SELECT COUNT(*) as cnt FROM check_ins')
            stats['total_checkins'] = cur.fetchone()['cnt']

            # 小队数量
            cur.execute('SELECT COUNT(*) as cnt FROM squads')
            stats['total_squads'] = cur.fetchone()['cnt']

            # 近7天打卡趋势
            trend = []
            for i in range(6, -1, -1):
                d = today.replace(day=1)  # placeholder
                from datetime import timedelta
                d = today - timedelta(days=i)
                cur.execute(
                    'SELECT COUNT(DISTINCT user_id) as cnt FROM check_ins WHERE check_date = %s',
                    (d,)
                )
                trend.append({
                    'date': str(d),
                    'count': cur.fetchone()['cnt'],
                })
            stats['checkin_trend'] = trend

            return stats
    finally:
        conn.close()
