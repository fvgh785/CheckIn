import uuid
import logging
import traceback
from datetime import date, datetime, timedelta

import pymysql

from db import get_connection, init_db

_logger = logging.getLogger(__name__)

# ======================== 会员状态 ========================


def get_membership(user_id):
    """查询会员状态"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT * FROM memberships WHERE user_id = %s AND status = 1 AND end_date >= %s',
                (user_id, date.today())
            )
            row = cur.fetchone()
            if row:
                return {
                    'active': True,
                    'level': row['level'],
                    'start_date': str(row['start_date']),
                    'end_date': str(row['end_date']),
                }
            return {'active': False, 'level': None, 'start_date': None, 'end_date': None}
    finally:
        conn.close()


def is_member_active(user_id):
    """快速判断会员是否有效"""
    result = get_membership(user_id)
    return result['active']


def activate_membership(user_id, months):
    """管理后台：激活/续费会员"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM memberships WHERE user_id = %s', (user_id,))
            existing = cur.fetchone()

            if existing and existing['status'] == 1 and existing['end_date'] >= date.today():
                # 已有有效会员，续期
                new_end = existing['end_date'] + timedelta(days=months * 30)
                cur.execute(
                    'UPDATE memberships SET end_date = %s WHERE user_id = %s',
                    (new_end, user_id)
                )
            else:
                # 新开通或已过期重新开通
                member_id = str(uuid.uuid4())
                start_date = date.today()
                end_date = start_date + timedelta(days=months * 30)
                if existing:
                    cur.execute(
                        'UPDATE memberships SET level=%s, start_date=%s, end_date=%s, status=1 WHERE user_id=%s',
                        ('premium', start_date, end_date, user_id)
                    )
                else:
                    cur.execute(
                        'INSERT INTO memberships (id, user_id, level, start_date, end_date, status) VALUES (%s, %s, %s, %s, %s, 1)',
                        (member_id, user_id, 'premium', start_date, end_date)
                    )
            # 同时初始化宠物（如果还没有）
            _ensure_pet_exists(conn, user_id)

            conn.commit()

            return {
                'success': True,
                'message': f'会员已开通/续费 {months} 个月',
                'end_date': str((existing['end_date'] + timedelta(days=months * 30)) if (existing and existing['status'] == 1 and existing['end_date'] >= date.today()) else (date.today() + timedelta(days=months * 30)))
            }
    except Exception:
        _logger.error(f'activate_membership failed: {traceback.format_exc()}')
        raise
    finally:
        conn.close()


# ======================== 虚拟宠物 ========================

PET_STAGES = {1: '蛋', 2: '幼崽', 3: '成年', 4: '传说'}
PET_TYPES = ['cat', 'dog', 'bunny', 'panda']
STAGE_EXP_REQUIRED = {1: 0, 2: 100, 3: 300, 4: 700}  # 进化所需经验


def _ensure_pet_exists(conn, user_id):
    """确保用户有宠物记录（需调用方commit）"""
    with conn.cursor() as cur:
        cur.execute('SELECT id FROM pets WHERE user_id = %s', (user_id,))
        if not cur.fetchone():
            pet_id = str(uuid.uuid4())
            cur.execute(
                'INSERT INTO pets (id, user_id) VALUES (%s, %s)',
                (pet_id, user_id)
            )
            return True  # 新创建
        return False  # 已存在


def ensure_pet_exists(user_id):
    """公开接口：确保用户有宠物记录，自动commit"""
    init_db()
    conn = get_connection()
    try:
        created = _ensure_pet_exists(conn, user_id)
        if created:
            conn.commit()
        return created
    finally:
        conn.close()


def get_pet(user_id):
    """获取宠物信息和状态"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM pets WHERE user_id = %s', (user_id,))
            row = cur.fetchone()
            if not row:
                return None

            # 计算断签惩罚（动态计算心情/饥饿度）
            mood = int(row['mood'])
            hunger = int(row['hunger'])
            last_feed = row['last_feed_date']
            if last_feed:
                days_since_feed = (date.today() - last_feed).days
                if days_since_feed >= 1:
                    mood = max(0, mood - days_since_feed * 20)
                    hunger = max(0, hunger - days_since_feed * 30)

            accessories = row['accessory'].split(',') if row['accessory'] else []

            return {
                'id': row['id'],
                'pet_type': row['pet_type'],
                'pet_name': row['pet_name'],
                'stage': row['stage'],
                'stage_name': PET_STAGES.get(row['stage'], '未知'),
                'mood': mood,
                'hunger': hunger,
                'exp': row['exp'],
                'accessories': accessories,
                'last_feed_date': str(last_feed) if last_feed else None,
                'is_sick': mood < 30,
                'next_stage_exp': STAGE_EXP_REQUIRED.get(row['stage'] + 1, 9999) if row['stage'] < 4 else None,
            }
    finally:
        conn.close()


def feed_pet(user_id):
    """打卡喂食宠物，返回宠物变化信息"""
    if not is_member_active(user_id):
        return None  # 非会员不处理宠物

    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM pets WHERE user_id = %s', (user_id,))
            pet = cur.fetchone()
            if not pet:
                _ensure_pet_exists(conn, user_id)
                cur.execute('SELECT * FROM pets WHERE user_id = %s', (user_id,))
                pet = cur.fetchone()

            # 计算断签天数
            last_feed = pet['last_feed_date']
            days_missed = 0
            if last_feed:
                days_missed = (date.today() - last_feed).days - 1
                days_missed = max(0, days_missed)

            mood = int(pet['mood'])
            hunger = int(pet['hunger'])
            exp = int(pet['exp'])
            stage = int(pet['stage'])

            if last_feed and last_feed == date.today():
                # 今天已经喂过了，不重复计算
                return {
                    'mood': mood,
                    'hunger': hunger,
                    'exp': exp,
                    'stage': stage,
                    'stage_name': PET_STAGES.get(stage, '未知'),
                    'level_up': False,
                    'already_fed': True,
                }

            # 应用断签惩罚（在喂食前）
            if days_missed > 0:
                mood = max(0, mood - days_missed * 20)
                hunger = max(0, hunger - days_missed * 30)

            # 喂食效果
            mood = min(100, mood + 10)
            hunger = min(100, hunger + 15 + days_missed * 5)  # 断签后回归有额外补偿
            exp += 20

            # 检查进化
            level_up = False
            if stage < 4 and exp >= STAGE_EXP_REQUIRED.get(stage + 1, 9999):
                stage += 1
                level_up = True

            cur.execute(
                'UPDATE pets SET mood=%s, hunger=%s, exp=%s, stage=%s, last_feed_date=%s WHERE user_id=%s',
                (mood, hunger, exp, stage, date.today(), user_id)
            )
            conn.commit()

            return {
                'mood': mood,
                'hunger': hunger,
                'exp': exp,
                'stage': stage,
                'stage_name': PET_STAGES.get(stage, '未知'),
                'level_up': level_up,
                'already_fed': False,
            }
    finally:
        conn.close()


def update_pet_name(user_id, pet_name):
    """给宠物改名"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            _ensure_pet_exists(conn, user_id)
            cur.execute('UPDATE pets SET pet_name = %s WHERE user_id = %s', (pet_name, user_id))
            conn.commit()
            return {'success': True, 'pet_name': pet_name}
    finally:
        conn.close()


def equip_accessory(user_id, accessory):
    """装备饰品"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            _ensure_pet_exists(conn, user_id)
            cur.execute('SELECT accessory FROM pets WHERE user_id = %s', (user_id,))
            row = cur.fetchone()
            current = row['accessory'].split(',') if row['accessory'] else []
            if accessory not in current:
                current.append(accessory)
            new_acc = ','.join(current)
            cur.execute('UPDATE pets SET accessory = %s WHERE user_id = %s', (new_acc, user_id))
            conn.commit()
            return {'success': True, 'accessories': current}
    finally:
        conn.close()


# ======================== 打卡小队 ========================


def _generate_squad_code():
    """生成6-8位邀请码"""
    import secrets
    import string
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(6))


def create_squad(owner_id, name):
    """创建打卡小队"""
    init_db()
    conn = get_connection()
    try:
        squad_id = str(uuid.uuid4())
        # 生成唯一邀请码
        for _ in range(5):
            code = _generate_squad_code()
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM squads WHERE code = %s', (code,))
                if not cur.fetchone():
                    break
        else:
            return {'success': False, 'message': '邀请码生成失败，请重试'}

        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO squads (id, name, owner_id, code) VALUES (%s, %s, %s, %s)',
                (squad_id, name, owner_id, code)
            )
            # 队长自动加入
            member_id = str(uuid.uuid4())
            cur.execute(
                'INSERT INTO squad_members (id, squad_id, user_id) VALUES (%s, %s, %s)',
                (member_id, squad_id, owner_id)
            )
            conn.commit()

        return {
            'success': True,
            'squad_id': squad_id,
            'name': name,
            'code': code,
        }
    except pymysql.err.IntegrityError:
        return {'success': False, 'message': '创建小队失败'}
    finally:
        conn.close()


def join_squad(user_id, code):
    """通过邀请码加入小队"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM squads WHERE code = %s', (code,))
            squad = cur.fetchone()
            if not squad:
                return {'success': False, 'message': '邀请码无效，小队不存在'}

            # 检查人数上限
            cur.execute('SELECT COUNT(*) as cnt FROM squad_members WHERE squad_id = %s', (squad['id'],))
            count = cur.fetchone()['cnt']
            if count >= squad['max_members']:
                return {'success': False, 'message': f'小队已满（最多{squad["max_members"]}人）'}

            # 检查是否已加入
            cur.execute(
                'SELECT id FROM squad_members WHERE squad_id = %s AND user_id = %s',
                (squad['id'], user_id)
            )
            if cur.fetchone():
                return {'success': False, 'message': '你已在该小队中'}

            member_id = str(uuid.uuid4())
            cur.execute(
                'INSERT INTO squad_members (id, squad_id, user_id) VALUES (%s, %s, %s)',
                (member_id, squad['id'], user_id)
            )
            conn.commit()

        return {
            'success': True,
            'squad_id': squad['id'],
            'name': squad['name'],
        }
    finally:
        conn.close()


def get_my_squad(user_id):
    """获取我的小队信息（只读，不更新streak）"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT s.* FROM squads s
                JOIN squad_members sm ON s.id = sm.squad_id
                WHERE sm.user_id = %s
            ''', (user_id,))
            squad = cur.fetchone()
            if not squad:
                return None

            # 获取成员信息（含昵称）
            cur.execute('''
                SELECT sm.user_id, sm.joined_at, u.nickname
                FROM squad_members sm
                JOIN users u ON sm.user_id = u.id
                WHERE sm.squad_id = %s
                ORDER BY sm.joined_at ASC
            ''', (squad['id'],))
            members = cur.fetchall()

            # 获取每个成员今日打卡状态
            today_str = date.today().isoformat()
            member_list = []
            all_checked_today = True
            for m in members:
                cur.execute(
                    'SELECT id FROM check_ins WHERE user_id = %s AND check_date = %s',
                    (m['user_id'], today_str)
                )
                checked = bool(cur.fetchone())
                if not checked:
                    all_checked_today = False
                member_list.append({
                    'user_id': m['user_id'],
                    'nickname': m.get('nickname', '') or ('队友' + m['user_id'][:4]),
                    'checked_today': checked,
                    'is_owner': m['user_id'] == squad['owner_id'],
                })

            return {
                'id': squad['id'],
                'name': squad['name'],
                'code': squad['code'],
                'owner_id': squad['owner_id'],
                'current_streak': squad['current_streak'],
                'max_streak': squad['max_streak'],
                'all_checked_today': all_checked_today,
                'members': member_list,
            }
    finally:
        conn.close()


def update_squad_streaks_for_user(user_id):
    """用户打卡后，更新其所在小队的连续全勤（每天最多触发一次）"""
    init_db()
    conn = get_connection()
    today = date.today()
    try:
        with conn.cursor() as cur:
            # 查找用户所在的小队
            cur.execute('''
                SELECT s.* FROM squads s
                JOIN squad_members sm ON s.id = sm.squad_id
                WHERE sm.user_id = %s
            ''', (user_id,))
            squads = cur.fetchall()

            for squad in squads:
                # 今天已经更新过，跳过
                last_date = squad.get('last_streak_date')
                if last_date and last_date == today:
                    continue

                # 获取所有成员的今日打卡状态
                cur.execute(
                    'SELECT user_id FROM squad_members WHERE squad_id = %s',
                    (squad['id'],)
                )
                members = [m['user_id'] for m in cur.fetchall()]

                all_checked = True
                for member_id in members:
                    cur.execute(
                        'SELECT id FROM check_ins WHERE user_id = %s AND check_date = %s',
                        (member_id, today.isoformat())
                    )
                    if not cur.fetchone():
                        all_checked = False
                        break

                if all_checked:
                    new_streak = squad['current_streak'] + 1
                else:
                    new_streak = 0

                new_max = max(new_streak, squad['max_streak'])

                cur.execute(
                    'UPDATE squads SET current_streak = %s, max_streak = %s, last_streak_date = %s WHERE id = %s',
                    (new_streak, new_max, today, squad['id'])
                )
            conn.commit()
    finally:
        conn.close()


# ======================== 心愿清单 ========================


def create_wish(user_id, content, target_days):
    """创建心愿"""
    init_db()
    conn = get_connection()
    try:
        wish_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO wishes (id, user_id, content, target_days) VALUES (%s, %s, %s, %s)',
                (wish_id, user_id, content, target_days)
            )
            conn.commit()
        return {'success': True, 'wish_id': wish_id}
    finally:
        conn.close()


def get_wishes(user_id):
    """获取用户所有心愿"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT * FROM wishes WHERE user_id = %s ORDER BY created_at DESC',
                (user_id,)
            )
            rows = cur.fetchall()
            return [{
                'id': r['id'],
                'content': r['content'],
                'target_days': r['target_days'],
                'current_days': r['current_days'],
                'status': r['status'],
                'progress_pct': min(100, int(r['current_days'] / r['target_days'] * 100)) if r['target_days'] > 0 else 0,
                'created_at': str(r['created_at']),
                'achieved_at': str(r['achieved_at']) if r['achieved_at'] else None,
            } for r in rows]
    finally:
        conn.close()


def update_wish_progress(user_id):
    """打卡后更新所有进行中的心愿进度"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'UPDATE wishes SET current_days = current_days + 1 WHERE user_id = %s AND status = 0',
                (user_id,)
            )
            # 标记已达成的心愿
            cur.execute(
                'UPDATE wishes SET status = 1, achieved_at = NOW() WHERE user_id = %s AND status = 0 AND current_days >= target_days',
                (user_id,)
            )
            conn.commit()
    finally:
        conn.close()


# ======================== 时光胶囊 ========================


def create_capsule(user_id, content, target_streak, current_streak):
    """创建时光胶囊"""
    init_db()
    conn = get_connection()
    try:
        capsule_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO time_capsules (id, user_id, content, target_streak, created_streak) VALUES (%s, %s, %s, %s, %s)',
                (capsule_id, user_id, content, target_streak, current_streak)
            )
            conn.commit()
        return {'success': True, 'capsule_id': capsule_id}
    finally:
        conn.close()


def get_capsules(user_id):
    """获取用户所有胶囊"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT * FROM time_capsules WHERE user_id = %s ORDER BY created_at DESC',
                (user_id,)
            )
            rows = cur.fetchall()
            result = []
            for r in rows:
                item = {
                    'id': r['id'],
                    'target_streak': r['target_streak'],
                    'created_streak': r['created_streak'],
                    'status': r['status'],
                    'created_at': str(r['created_at']),
                    'opened_at': str(r['opened_at']) if r['opened_at'] else None,
                }
                if r['status'] == 1:
                    # 已开启，可以显示内容
                    item['content'] = r['content'][:50] + '...' if len(r['content']) > 50 else r['content']
                    item['full_content'] = r['content']
                else:
                    item['content'] = '🔒 封印中...'
                    item['full_content'] = None
                    item['preview'] = r['content'][:20] + '...' if len(r['content']) > 20 else r['content']
                result.append(item)
            return result
    finally:
        conn.close()


def open_capsule(capsule_id, user_id, current_streak):
    """尝试开启胶囊"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT * FROM time_capsules WHERE id = %s AND user_id = %s',
                (capsule_id, user_id)
            )
            capsule = cur.fetchone()
            if not capsule:
                return {'success': False, 'message': '胶囊不存在'}
            if capsule['status'] == 1:
                return {'success': False, 'message': '胶囊已开启', 'content': capsule['content']}
            if current_streak < capsule['target_streak']:
                need = capsule['target_streak'] - current_streak
                return {'success': False, 'message': f'还需连续打卡 {need} 天才能开启', 'need_days': need}

            cur.execute(
                'UPDATE time_capsules SET status = 1, opened_at = NOW() WHERE id = %s',
                (capsule_id,)
            )
            conn.commit()
            return {
                'success': True,
                'content': capsule['content'],
                'created_at': str(capsule['created_at']),
            }
    finally:
        conn.close()


# ======================== AI洞察 ========================


def get_week_start():
    """获取本周一的日期"""
    today = date.today()
    return today - timedelta(days=today.weekday())


def save_insight(user_id, content, force=False):
    """保存AI洞察"""
    init_db()
    conn = get_connection()
    try:
        week_start = get_week_start()
        insight_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            # 强制重新生成时，先删除已存在的本周洞察
            if force:
                cur.execute(
                    'DELETE FROM ai_insights WHERE user_id = %s AND week_start = %s',
                    (user_id, week_start)
                )
            cur.execute(
                'INSERT INTO ai_insights (id, user_id, week_start, content) VALUES (%s, %s, %s, %s)',
                (insight_id, user_id, week_start, content)
            )
            conn.commit()
        return {'success': True, 'id': insight_id}
    except pymysql.err.IntegrityError:
        return {'success': False, 'message': '本周洞察已生成'}
    finally:
        conn.close()


def get_insight(user_id, week_start=None):
    """获取AI洞察"""
    init_db()
    conn = get_connection()
    try:
        if week_start is None:
            week_start = get_week_start()
        with conn.cursor() as cur:
            cur.execute(
                'SELECT * FROM ai_insights WHERE user_id = %s AND week_start = %s',
                (user_id, week_start)
            )
            row = cur.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'week_start': str(row['week_start']),
                    'content': row['content'],
                    'created_at': str(row['created_at']),
                }
            return None
    finally:
        conn.close()


def get_insight_history(user_id, limit=10):
    """获取AI洞察历史列表"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT * FROM ai_insights WHERE user_id = %s ORDER BY week_start DESC LIMIT %s',
                (user_id, limit)
            )
            rows = cur.fetchall()
            return [{
                'id': r['id'],
                'week_start': str(r['week_start']),
                'content': r['content'],
                'created_at': str(r['created_at']),
            } for r in rows]
    finally:
        conn.close()


# ======================== 洞察手动生成配额 ========================

DEFAULT_INSIGHT_GENERATION_LIMIT = 3


def get_insight_generation_limit():
    """从数据库动态读取AI洞察每日手动生成上限"""
    try:
        from db_admin import get_config_value
        val = get_config_value('insight_generation_limit')
        return int(val) if val else DEFAULT_INSIGHT_GENERATION_LIMIT
    except Exception:
        return DEFAULT_INSIGHT_GENERATION_LIMIT


def check_insight_quota(user_id):
    """查询今日剩余手动生成洞察次数"""
    limit = get_insight_generation_limit()
    init_db()
    conn = get_connection()
    try:
        today = date.today()
        with conn.cursor() as cur:
            cur.execute(
                'SELECT count FROM insight_generation_quota WHERE user_id = %s AND gen_date = %s',
                (user_id, today)
            )
            row = cur.fetchone()
            used = row['count'] if row else 0
            remaining = max(0, limit - used)
            return {'used': used, 'remaining': remaining, 'limit': limit}
    finally:
        conn.close()


def use_insight_quota(user_id):
    """消耗一次手动生成配额，返回是否成功及剩余次数"""
    limit = get_insight_generation_limit()
    init_db()
    conn = get_connection()
    try:
        today = date.today()
        with conn.cursor() as cur:
            cur.execute(
                'SELECT count FROM insight_generation_quota WHERE user_id = %s AND gen_date = %s FOR UPDATE',
                (user_id, today)
            )
            row = cur.fetchone()
            used = row['count'] if row else 0
            if used >= limit:
                return {'success': False, 'remaining': 0, 'message': f'今日已达上限（{limit}次/天）'}

            if row:
                cur.execute(
                    'UPDATE insight_generation_quota SET count = count + 1 WHERE user_id = %s AND gen_date = %s',
                    (user_id, today)
                )
            else:
                cur.execute(
                    'INSERT INTO insight_generation_quota (user_id, gen_date, count) VALUES (%s, %s, 1)',
                    (user_id, today)
                )
            conn.commit()
            remaining = limit - used - 1
            return {'success': True, 'remaining': remaining, 'message': f'已消耗1次，剩余{remaining}次'}
    finally:
        conn.close()


# ======================== 补签卡 ========================

from db_admin import get_config_value, DEFAULT_MAKEUP_CARD_LIMIT


def get_makeup_card_limit():
    """从数据库动态读取补签卡月限额"""
    try:
        val = get_config_value('makeup_card_limit')
        return int(val) if val else DEFAULT_MAKEUP_CARD_LIMIT
    except Exception:
        return DEFAULT_MAKEUP_CARD_LIMIT


def get_makeup_card_used_count(user_id):
    """查询当月已使用的补签卡数量"""
    init_db()
    conn = get_connection()
    try:
        today = date.today()
        month_start = today.replace(day=1)
        with conn.cursor() as cur:
            cur.execute(
                'SELECT COUNT(*) as cnt FROM makeup_cards WHERE user_id = %s AND used_date >= %s',
                (user_id, month_start)
            )
            return cur.fetchone()['cnt']
    finally:
        conn.close()


def use_makeup_card(user_id, target_date):
    """使用补签卡，补签到指定日期"""
    init_db()
    conn = get_connection()
    try:
        today = date.today()
        month_start = today.replace(day=1)
        limit = get_makeup_card_limit()

        with conn.cursor() as cur:
            # 在同一事务中完成计数检查+插入，避免并发超限
            cur.execute(
                'SELECT COUNT(*) as cnt FROM makeup_cards WHERE user_id = %s AND used_date >= %s FOR UPDATE',
                (user_id, month_start)
            )
            used = cur.fetchone()['cnt']
            if used >= limit:
                return {'success': False, 'message': f'本月补签卡已用完（{limit}张/月）'}

            card_id = str(uuid.uuid4())
            cur.execute(
                'INSERT INTO makeup_cards (id, user_id, used_date) VALUES (%s, %s, %s)',
                (card_id, user_id, target_date)
            )
            # 同时插入打卡记录
            check_id = str(uuid.uuid4())
            cur.execute(
                'INSERT INTO check_ins (id, user_id, check_date) VALUES (%s, %s, %s)',
                (check_id, user_id, target_date)
            )
            conn.commit()

        return {
            'success': True,
            'message': f'补签成功：{target_date}',
            'cards_remaining': limit - used - 1,
        }
    except pymysql.err.IntegrityError:
        return {'success': False, 'message': '该日期已打卡或已补签'}
    finally:
        conn.close()
