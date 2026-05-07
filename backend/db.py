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
    'password': os.environ.get('DB_PASSWORD', 'checkin123'),
    'database': os.environ.get('DB_NAME', 'checkin'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}

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
                return {'id': user_id, 'open_id': open_id}
            except pymysql.err.IntegrityError:
                # Race condition: another request created this user concurrently
                cur.execute('SELECT * FROM users WHERE open_id = %s', (open_id,))
                return cur.fetchone()
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
    return {'token': token, 'user_id': user['id']}


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


def check_in_by_user_id(user_id):
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM users WHERE id = %s', (user_id,))
            if not cur.fetchone():
                return {'success': False, 'message': '用户不存在'}
        today_str = date.today().isoformat()
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
