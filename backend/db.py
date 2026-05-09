import os
import uuid
import secrets
import logging
import traceback
from datetime import date, timedelta, datetime
from time import time

import pymysql
import pymysql.cursors
from dbutils.pooled_db import PooledDB

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'mysql'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'checkin'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME', 'checkin'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}

if not DB_CONFIG['password']:
    raise RuntimeError('DB_PASSWORD environment variable is required')

_logger = logging.getLogger(__name__)
_initialized = False
_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=10,
            mincached=2,
            maxcached=5,
            blocking=True,
            **DB_CONFIG
        )
    return _pool


def get_connection():
    return _get_pool().connection()


def init_db():
    global _initialized
    if _initialized:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(36) PRIMARY KEY,
                    open_id VARCHAR(128) NOT NULL UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS check_ins (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    check_date DATE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE KEY unique_user_date (user_id, check_date)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    token VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    open_id VARCHAR(128) NOT NULL,
                    created_at BIGINT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            # === 会员体系新增表 ===
            cur.execute('''
                CREATE TABLE IF NOT EXISTS memberships (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL UNIQUE,
                    level VARCHAR(20) DEFAULT 'premium',
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    status TINYINT DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS pets (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL UNIQUE,
                    pet_type VARCHAR(20) DEFAULT 'cat',
                    pet_name VARCHAR(30) DEFAULT '小打卡',
                    stage TINYINT DEFAULT 1,
                    mood TINYINT DEFAULT 80,
                    hunger TINYINT DEFAULT 80,
                    exp INT DEFAULT 0,
                    last_feed_date DATE,
                    accessory VARCHAR(200) DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS squads (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(50) NOT NULL,
                    owner_id VARCHAR(36) NOT NULL,
                    code VARCHAR(8) NOT NULL UNIQUE,
                    max_members TINYINT DEFAULT 5,
                    current_streak INT DEFAULT 0,
                    max_streak INT DEFAULT 0,
                    last_streak_date DATE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES users(id)
                )
            ''')
            # 兼容旧表：添加 last_streak_date 字段
            try:
                cur.execute('ALTER TABLE squads ADD COLUMN last_streak_date DATE')
            except Exception:
                pass  # 字段已存在
            # 兼容旧表：添加 phone / nickname / email 字段
            try:
                cur.execute('ALTER TABLE users ADD COLUMN phone VARCHAR(20) DEFAULT \'\'')
            except Exception:
                pass
            try:
                cur.execute('ALTER TABLE users ADD COLUMN nickname VARCHAR(50) DEFAULT \'\'')
            except Exception:
                pass
            try:
                cur.execute('ALTER TABLE users ADD COLUMN email VARCHAR(100) DEFAULT \'\'')
            except Exception:
                pass
            cur.execute('''
                CREATE TABLE IF NOT EXISTS email_verification_codes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(100) NOT NULL,
                    code VARCHAR(6) NOT NULL,
                    expires_at DATETIME NOT NULL,
                    used TINYINT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS squad_members (
                    id VARCHAR(36) PRIMARY KEY,
                    squad_id VARCHAR(36) NOT NULL,
                    user_id VARCHAR(36) NOT NULL,
                    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (squad_id) REFERENCES squads(id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE KEY unique_squad_user (squad_id, user_id)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS wishes (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    content VARCHAR(200) NOT NULL,
                    target_days INT NOT NULL,
                    current_days INT DEFAULT 0,
                    status TINYINT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    achieved_at DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS time_capsules (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    content TEXT NOT NULL,
                    target_streak INT NOT NULL,
                    created_streak INT NOT NULL,
                    status TINYINT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    opened_at DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS ai_insights (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    week_start DATE NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE KEY unique_user_week (user_id, week_start)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS makeup_cards (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    used_date DATE NOT NULL,
                    used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE KEY unique_user_makeup_date (user_id, used_date)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id VARCHAR(36) PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(20) DEFAULT 'admin',
                    status TINYINT DEFAULT 1,
                    token_version INT DEFAULT 0,
                    locked_until DATETIME,
                    failed_attempts INT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 兼容旧表：添加 token_version / locked_until / failed_attempts 字段
            for col in ['token_version', 'locked_until', 'failed_attempts']:
                try:
                    if col == 'token_version':
                        cur.execute(f'ALTER TABLE admins ADD COLUMN {col} INT DEFAULT 0')
                    elif col == 'locked_until':
                        cur.execute(f'ALTER TABLE admins ADD COLUMN {col} DATETIME')
                    else:
                        cur.execute(f'ALTER TABLE admins ADD COLUMN {col} INT DEFAULT 0')
                except Exception:
                    pass  # 字段已存在
            cur.execute('''
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id VARCHAR(36) PRIMARY KEY,
                    admin_id VARCHAR(36) NOT NULL,
                    action VARCHAR(50) NOT NULL,
                    target_type VARCHAR(50) NOT NULL,
                    target_id VARCHAR(36),
                    detail TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES admins(id)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS system_config (
                    config_key VARCHAR(64) PRIMARY KEY,
                    config_value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            ''')
            # 初始化默认配置（仅在表为空时插入）
            cur.execute('SELECT COUNT(*) as cnt FROM system_config')
            if cur.fetchone()['cnt'] == 0:
                cur.execute(
                    'INSERT INTO system_config (config_key, config_value) VALUES (%s, %s)',
                    ('makeup_card_limit', '3')
                )
                cur.execute(
                    'INSERT INTO system_config (config_key, config_value) VALUES (%s, %s)',
                    ('free_membership_cutoff_date', '')
                )
            # 初始化默认超级管理员（必须通过环境变量设置凭据）
            try:
                from werkzeug.security import generate_password_hash
                default_username = os.environ.get('ADMIN_DEFAULT_USERNAME')
                default_password = os.environ.get('ADMIN_DEFAULT_PASSWORD')
                if not default_username or not default_password:
                    _logger.warning(
                        'ADMIN_DEFAULT_USERNAME and ADMIN_DEFAULT_PASSWORD env vars not set. '
                        'Default super admin will NOT be created. Use admin management API to create admins.'
                    )
                else:
                    cur.execute('SELECT id FROM admins WHERE username = %s', (default_username,))
                    if not cur.fetchone():
                        admin_id = str(uuid.uuid4())
                        pw_hash = generate_password_hash(default_password)
                        cur.execute(
                            'INSERT INTO admins (id, username, password_hash, role) VALUES (%s, %s, %s, %s)',
                            (admin_id, default_username, pw_hash, 'super_admin')
                        )
                        _logger.info(f'Default super admin created: {default_username}')
            except Exception as e:
                _logger.warning(f'Failed to create default admin: {e}')
        conn.commit()
        _initialized = True
        _logger.info('MySQL tables initialized')
    finally:
        conn.close()


def get_or_create_user(open_id):
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE open_id = %s', (open_id,))
            row = cur.fetchone()
            if row:
                return row
            user_id = str(uuid.uuid4())
            try:
                cur.execute(
                    'INSERT INTO users (id, open_id) VALUES (%s, %s)',
                    (user_id, open_id)
                )
                conn.commit()
                return {'id': user_id, 'open_id': open_id, 'phone': '', 'nickname': '', 'email': ''}
            except pymysql.err.IntegrityError:
                # Race condition: another request created this user concurrently
                cur.execute('SELECT * FROM users WHERE open_id = %s', (open_id,))
                return cur.fetchone()
    finally:
        conn.close()


def update_user_profile(open_id, phone=None, nickname=None, email=None):
    """更新用户资料（手机号、昵称、邮箱）"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE open_id = %s', (open_id,))
            user = cur.fetchone()
            if not user:
                return {'success': False, 'message': '用户不存在'}

            updates = []
            params = []
            if phone is not None and phone:
                updates.append('phone = %s')
                params.append(phone)
            if nickname is not None and nickname:
                updates.append('nickname = %s')
                params.append(nickname)
            if email is not None and email:
                updates.append('email = %s')
                params.append(email)

            if not updates:
                return {'success': False, 'message': '无更新内容'}

            params.append(open_id)
            set_clause = ', '.join(updates)
            sql = f'UPDATE users SET {set_clause} WHERE open_id = %s'
            cur.execute(sql, params)
            conn.commit()
            return {'success': True, 'message': '资料更新成功'}
    finally:
        conn.close()


def get_user_profile(open_id):
    """获取用户资料（昵称、邮箱）"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT nickname, email FROM users WHERE open_id = %s', (open_id,))
            row = cur.fetchone()
            if row:
                return {
                    'nickname': row.get('nickname', ''),
                    'email': row.get('email', ''),
                }
            return {'nickname': '', 'email': ''}
    finally:
        conn.close()


def get_user_by_phone(phone):
    """按手机号查找用户"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE phone = %s', (phone,))
            row = cur.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'open_id': row['open_id'],
                    'phone': row.get('phone', ''),
                    'nickname': row.get('nickname', ''),
                    'created_at': str(row['created_at']),
                }
            return None
    finally:
        conn.close()


def generate_token():
    return secrets.token_hex(32)


def login(open_id):
    user = get_or_create_user(open_id)
    token = generate_token()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO sessions (token, user_id, open_id, created_at) VALUES (%s, %s, %s, %s)',
                (token, user['id'], user['open_id'], int(datetime.now().timestamp() * 1000))
            )
            conn.commit()
    finally:
        conn.close()
    return {
        'token': token,
        'user_id': user['id'],
        'phone': user.get('phone', ''),
        'nickname': user.get('nickname', ''),
        'email': user.get('email', ''),
    }


def verify_token(token):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM sessions WHERE token = %s', (token,))
            row = cur.fetchone()
            if not row:
                return None
            if time() * 1000 - row['created_at'] > 7 * 24 * 60 * 60 * 1000:
                cur.execute('DELETE FROM sessions WHERE token = %s', (token,))
                conn.commit()
                return None
            return {
                'userId': row['user_id'],
                'openId': row['open_id'],
                'createdAt': row['created_at'],
            }
    finally:
        conn.close()


def logout(token):
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM sessions WHERE token = %s', (token,))
            conn.commit()
    finally:
        conn.close()


# ======================== 邮箱验证码 ========================

import random


def save_email_verification_code(email, code):
    """保存邮箱验证码，有效期5分钟"""
    init_db()
    conn = get_connection()
    try:
        from datetime import timedelta
        expires_at = datetime.now() + timedelta(minutes=5)
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO email_verification_codes (email, code, expires_at) VALUES (%s, %s, %s)',
                (email, code, expires_at)
            )
            conn.commit()
        return True
    except Exception:
        _logger.error(f'save_email_verification_code failed: {traceback.format_exc()}')
        return False
    finally:
        conn.close()


def verify_email_code(email, code):
    """验证邮箱验证码，成功返回True并标记已使用"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                '''SELECT * FROM email_verification_codes
                   WHERE email = %s AND code = %s AND used = 0 AND expires_at > %s
                   ORDER BY created_at DESC LIMIT 1''',
                (email, code, datetime.now())
            )
            row = cur.fetchone()
            if not row:
                return False
            # 标记为已使用
            cur.execute(
                'UPDATE email_verification_codes SET used = 1 WHERE id = %s',
                (row['id'],)
            )
            conn.commit()
            return True
    except Exception:
        _logger.error(f'verify_email_code failed: {traceback.format_exc()}')
        return False
    finally:
        conn.close()


def bind_email_to_user(open_id, email):
    """将邮箱绑定到用户"""
    init_db()
    conn = get_connection()
    try:
        # 检查邮箱是否已被其他用户绑定
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id FROM users WHERE email = %s AND open_id != %s',
                (email, open_id)
            )
            if cur.fetchone():
                return {'success': False, 'message': '该邮箱已被其他账号绑定'}

            cur.execute(
                'UPDATE users SET email = %s WHERE open_id = %s',
                (email, open_id)
            )
            conn.commit()
            return {'success': True, 'message': '邮箱绑定成功'}
    except Exception:
        _logger.error(f'bind_email_to_user failed: {traceback.format_exc()}')
        return {'success': False, 'message': '绑定失败，请稍后重试'}
    finally:
        conn.close()


def generate_email_code():
    """生成6位数字验证码"""
    return ''.join(str(random.randint(0, 9)) for _ in range(6))


def send_verification_email(email, code):
    """
    发送验证码邮件
    支持网易系(163/126/yeah)、QQ邮箱等国内主流邮箱
    网易邮箱SMTP配置：
      - SMTP服务器: smtp.163.com (126: smtp.126.com, yeah: smtp.yeah.net, QQ: smtp.qq.com)
      - 端口: 465 (SSL) 或 25
      - 需在邮箱设置中开启SMTP服务并获取授权码
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = os.environ.get('SMTP_HOST', 'smtp.163.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '465'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_password = os.environ.get('SMTP_PASSWORD', '')
    smtp_from_name = os.environ.get('SMTP_FROM_NAME', '每日打卡')

    if not smtp_user or not smtp_password:
        _logger.error('SMTP_USER or SMTP_PASSWORD not configured')
        return False

    msg = MIMEMultipart()
    msg['From'] = f'{smtp_from_name} <{smtp_user}>'
    msg['To'] = email
    msg['Subject'] = '每日打卡 - 邮箱验证码'

    html_body = f'''
    <div style="max-width:500px;margin:0 auto;padding:30px;font-family:Arial,sans-serif;">
        <div style="text-align:center;margin-bottom:30px;">
            <h1 style="color:#3b82f6;margin:0;">📅 每日打卡</h1>
        </div>
        <div style="background:#f8f9fa;border-radius:12px;padding:30px;text-align:center;">
            <p style="color:#6b7280;font-size:14px;margin:0 0 20px;">您的邮箱验证码为：</p>
            <div style="font-size:36px;font-weight:bold;color:#1a1a2e;letter-spacing:8px;margin-bottom:20px;">{code}</div>
            <p style="color:#9ca3af;font-size:12px;margin:0;">验证码5分钟内有效，请勿泄露</p>
        </div>
        <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:20px;">
            如非本人操作，请忽略此邮件
        </p>
    </div>
    '''
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, email, msg.as_string())
        server.quit()
        _logger.info(f'Verification email sent to {email}')
        return True
    except Exception:
        _logger.error(f'Send email to {email} failed: {traceback.format_exc()}')
        return False


def check_in_by_user_id(user_id, check_date_str=None):
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM users WHERE id = %s', (user_id,))
            if not cur.fetchone():
                return {'success': False, 'message': '用户不存在'}
        today_str = check_date_str or date.today().isoformat()
        check_id = str(uuid.uuid4())
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO check_ins (id, user_id, check_date) VALUES (%s, %s, %s)',
                    (check_id, user_id, today_str)
                )
                conn.commit()
            return {'success': True, 'message': '打卡成功'}
        except pymysql.err.IntegrityError:
            return {'success': False, 'message': '今日已打卡'}
    finally:
        conn.close()


def get_stats_by_user_id(user_id):
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT check_date FROM check_ins WHERE user_id = %s ORDER BY check_date ASC',
                (user_id,)
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    today_str = date.today().isoformat()
    all_check_ins = [{'check_date': str(r['check_date'])} for r in rows]
    has_checked_today = any(c['check_date'] == today_str for c in all_check_ins)

    max_streak = 0
    temp_streak = 0
    prev_date = None

    for record in all_check_ins:
        curr_date = date.fromisoformat(record['check_date'])
        if prev_date:
            diff_days = (curr_date - prev_date).days
            temp_streak = temp_streak + 1 if diff_days == 1 else 1
        else:
            temp_streak = 1
        max_streak = max(max_streak, temp_streak)
        prev_date = curr_date

    current_streak = 0
    if all_check_ins:
        last_record = all_check_ins[-1]
        last_date = date.fromisoformat(last_record['check_date'])
        today_date = date.today()
        diff_days = (today_date - last_date).days

        if diff_days <= 1:
            streak = 0
            check_date = last_date
            date_set = {c['check_date'] for c in all_check_ins}
            while True:
                date_str = check_date.isoformat()
                if date_str in date_set:
                    streak += 1
                    check_date = check_date - timedelta(days=1)
                else:
                    break
            current_streak = streak

    return {
        'has_checked_today': has_checked_today,
        'current_streak': current_streak,
        'max_streak': max_streak,
        'total_days': len(all_check_ins),
    }
