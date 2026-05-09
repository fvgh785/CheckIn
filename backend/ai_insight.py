import os
import logging
import traceback
from datetime import date, timedelta
import json
import requests

from db import get_connection, get_stats_by_user_id
from db_membership import get_insight, save_insight

_logger = logging.getLogger(__name__)

# AI配置：支持DeepSeek或通义千问
AI_API_KEY = os.environ.get('AI_API_KEY', '')
AI_API_URL = os.environ.get('AI_API_URL', 'https://api.deepseek.com/v1/chat/completions')
AI_MODEL = os.environ.get('AI_MODEL', 'deepseek-chat')

INSIGHT_PROMPT = """你是习惯养成教练，请基于用户本周的打卡数据分析并给出个性化建议。

用户本周打卡数据（格式：星期几 打卡时间）：
{checkin_data}

用户数据：本周打卡 {checked_days} 天，当前连续打卡 {current_streak} 天。

请分析：
1. 打卡时间规律（习惯在什么时间段打卡？）
2. 如果有漏打卡，可能的原因是什么？
3. 针对性给出1条下周改善建议
4. 用一句温暖的鼓励结束

要求：
- 总共不超过150字
- 像朋友聊天一样亲切自然
- 不要用"根据数据分析"这种生硬表述
- 不要用编号列表"""


def generate_insight_for_user(user_id, force=False):
    """为指定用户生成本周AI洞察
    
    Args:
        user_id: 用户ID
        force: 是否强制重新生成（手动触发时使用，会覆盖已存在的洞察）
    """
    if not AI_API_KEY:
        _logger.warning('AI_API_KEY not configured, skipping insight generation')
        return None

    # 检查是否已生成本周洞察（手动强制生成时跳过此检查）
    if not force:
        existing = get_insight(user_id)
        if existing:
            return existing

    # 收集本周打卡数据
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT check_date FROM check_ins WHERE user_id = %s AND check_date >= %s ORDER BY check_date ASC',
                (user_id, week_start)
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return None

    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    checkin_lines = []
    checked_dates = set()
    
    for r in rows:
        d = r['check_date']
        checked_dates.add(d if isinstance(d, str) else str(d))
    
    # 获取打卡时间（简化处理，展示日期即可）
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_str = day.isoformat()
        if day_str in checked_dates:
            checkin_lines.append(f'{weekday_names[i]}：已打卡')
        else:
            checkin_lines.append(f'{weekday_names[i]}：未打卡')

    checkin_data = '\n'.join(checkin_lines)
    checked_days = len(rows)

    # 从全局统计获取准确的连续天数
    stats = get_stats_by_user_id(user_id)
    current_streak = stats['current_streak']

    prompt = INSIGHT_PROMPT.format(
        checkin_data=checkin_data,
        checked_days=checked_days,
        current_streak=current_streak,
    )

    try:
        headers = {
            'Authorization': f'Bearer {AI_API_KEY}',
            'Content-Type': 'application/json',
        }
        body = {
            'model': AI_MODEL,
            'messages': [
                {'role': 'system', 'content': '你是一个温暖亲切的习惯养成教练。'},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.7,
            'max_tokens': 300,
        }
        resp = requests.post(AI_API_URL, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        content = result['choices'][0]['message']['content'].strip()
    except Exception:
        _logger.error(f'AI API call failed: {traceback.format_exc()}')
        # 降级：生成一条默认洞察
        content = f'本周完成了 {checked_days}/7 天打卡。继续加油，每一个坚持都值得被看见！'

    # 保存洞察
    try:
        save_insight(user_id, content, force=force)
    except Exception:
        _logger.error(f'save_insight failed: {traceback.format_exc()}')

    return {'week_start': str(week_start), 'content': content}


def generate_insights_for_all_members():
    """为所有会员生成周报（定时任务入口）"""
    from db import get_connection
    from db_membership import get_membership

    _logger.info('Starting weekly insight generation for all members')
    
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT m.user_id FROM memberships m WHERE m.status = 1 AND m.end_date >= %s',
                (date.today(),)
            )
            members = cur.fetchall()
    finally:
        conn.close()

    count = 0
    for m in members:
        try:
            result = generate_insight_for_user(m['user_id'])
            if result:
                count += 1
        except Exception:
            _logger.error(f'Failed to generate insight for user {m["user_id"]}: {traceback.format_exc()}')

    _logger.info(f'Weekly insight generation completed: {count}/{len(members)} members')
    return count
