import os
import uuid
import json
import logging
import traceback
from datetime import date, datetime

import requests
import jieba

from db import get_connection, init_db

_logger = logging.getLogger(__name__)

AI_API_KEY = os.environ.get('AI_API_KEY', '')
AI_API_URL = os.environ.get('AI_API_URL', 'https://api.deepseek.com/v1/chat/completions')
AI_MODEL = os.environ.get('AI_MODEL', 'deepseek-chat')

# ======================== 知识库关键词检索 ========================


def build_rag_context(user_message):
    """使用 jieba 中文分词 + 关键词匹配从知识库检索 Top-3 最相关条目"""
    if not user_message or not AI_API_KEY:
        return ''

    # jieba 中文分词提取关键词（过滤单字和停用词）
    stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
                  '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有',
                  '看', '好', '自己', '这', '他', '她', '它', '们', '那', '什么', '怎么',
                  '如何', '为什么', '哪', '吗', '吧', '呢', '啊', '哦', '嗯'}
    keywords = [w for w in jieba.cut(user_message) if len(w) > 1 and w not in stop_words]

    if not keywords:
        return ''

    # 查询所有已启用的知识库条目
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id, title, content, category FROM knowledge_bases WHERE enabled = 1'
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return ''

    # 计算每条知识库条目的关键词匹配得分
    scored = []
    for row in rows:
        title = row['title']
        content = row['content']
        full_text = f"{title}\n{content}"
        score = 0
        for kw in keywords:
            # 标题命中权重 3x
            score += title.lower().count(kw.lower()) * 3
            # 内容命中权重 1x
            score += content.lower().count(kw.lower())
        if score > 0:
            scored.append((score, title, full_text))

    if not scored:
        return ''

    # 按得分降序排列，取 Top-3
    scored.sort(key=lambda x: x[0], reverse=True)
    top_results = scored[:3]

    snippets = []
    for _, title, text in top_results:
        # 截断过长内容（最多500字），避免 context 过大
        display_text = text if len(text) <= 500 else text[:500] + '...'
        snippets.append(f'【{title}】\n{display_text}')

    return '\n\n---\n\n'.join(snippets)


SYSTEM_PROMPT_TEMPLATE = (
    '你是每日打卡小程序的智能助手。请根据以下参考资料回答用户问题，语气温暖亲切。\n\n'
    '参考资料：\n{rag_context}\n\n'
    '要求：\n'
    '- 回复不超过200字\n'
    '- 优先使用参考资料中的描述回答\n'
    '- 如果参考资料不足以回答用户问题，请如实告知并建议联系人工客服\n'
    '- 不要编造不存在于参考资料中的功能信息'
)

# ======================== AI对话 ========================


def chat_with_ai(user_id, messages):
    """
    调用 LLM 进行对话，注入 RAG 上下文。
    
    Args:
        user_id: 用户ID
        messages: 消息列表，每条含 role 和 content，最后一条为当前用户消息
    
    Returns:
        (reply_content, token_used) 或 (error_message, 0)
    """
    if not AI_API_KEY:
        return 'AI服务暂未配置，请联系管理员', 0

    # 获取最后一条用户消息用于 RAG 检索
    user_message = ''
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            user_message = msg['content']
            break

    # 构建 RAG 上下文（失败不影响对话）
    rag_context = ''
    try:
        rag_context = build_rag_context(user_message)
    except Exception:
        _logger.error(f'RAG context build failed: {traceback.format_exc()}')

    # 构建 system prompt
    system_content = SYSTEM_PROMPT_TEMPLATE.format(rag_context=rag_context or '(暂无参考资料)')

    # 构建消息列表（限制最近10轮对话以控制token消耗）
    msgs_for_api = [{'role': 'system', 'content': system_content}]
    recent_history = messages[-20:]  # 最多10轮（20条）
    for m in recent_history:
        msgs_for_api.append({'role': m['role'], 'content': m['content']})

    try:
        headers = {
            'Authorization': f'Bearer {AI_API_KEY}',
            'Content-Type': 'application/json',
        }
        body = {
            'model': AI_MODEL,
            'messages': msgs_for_api,
            'temperature': 0.7,
            'max_tokens': 300,
        }
        resp = requests.post(AI_API_URL, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        reply = result['choices'][0]['message']['content'].strip()

        # 获取 token 消耗
        usage = result.get('usage', {})
        token_used = usage.get('total_tokens', 0)
        if token_used == 0:
            # 估算
            total_chars = sum(len(m['content']) for m in msgs_for_api) + len(reply)
            token_used = total_chars // 2

        return reply, token_used

    except Exception:
        _logger.error(f'Chat API call failed: {traceback.format_exc()}')
        return '抱歉，AI服务暂时不可用，请稍后再试', 0


# ======================== Token配额管理 ========================

DEFAULT_TOKEN_LIMIT = 5000


def _get_token_limit():
    """从数据库读取每日token上限"""
    try:
        from db_admin import get_config_value
        val = get_config_value('chat_token_limit_per_day')
        return int(val) if val else DEFAULT_TOKEN_LIMIT
    except Exception:
        return DEFAULT_TOKEN_LIMIT


def check_chat_quota(user_id):
    """查询今日Token消耗情况"""
    limit = _get_token_limit()
    init_db()
    conn = get_connection()
    try:
        today = date.today()
        with conn.cursor() as cur:
            cur.execute(
                'SELECT COALESCE(SUM(token_used), 0) as total FROM chat_history WHERE user_id = %s AND DATE(created_at) = %s',
                (user_id, today)
            )
            row = cur.fetchone()
            used = row['total'] if row else 0
            remaining = max(0, limit - used)
            return {'used': used, 'remaining': remaining, 'limit': limit}
    finally:
        conn.close()


def pre_check_chat_quota(user_id):
    """发送前检查是否已超限，返回剩余额度"""
    quota = check_chat_quota(user_id)
    if quota['remaining'] <= 0:
        return {'success': False, 'remaining': 0, 'message': f'今日Token已达上限（{quota["limit"]}/天），请明天再来', 'limit': quota['limit']}
    return {'success': True, 'remaining': quota['remaining'], 'message': '', 'limit': quota['limit']}


def is_chat_enabled():
    """检查全局开关，异常时保守关闭"""
    try:
        from db_admin import get_config_value
        val = get_config_value('chat_enabled')
        return val == '1'
    except Exception:
        _logger.error(f'Failed to read chat_enabled config: {traceback.format_exc()}')
        return False


# ======================== 对话记录 ========================


def save_chat_message(user_id, role, content, token_used=0):
    """存储单条对话消息"""
    init_db()
    conn = get_connection()
    try:
        msg_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO chat_history (id, user_id, role, content, token_used) VALUES (%s, %s, %s, %s, %s)',
                (msg_id, user_id, role, content, token_used)
            )
            conn.commit()
        return True
    except Exception:
        _logger.error(f'save_chat_message failed: {traceback.format_exc()}')
        return False
    finally:
        conn.close()


def get_chat_history(user_id, page=1, page_size=20):
    """分页获取历史对话"""
    init_db()
    conn = get_connection()
    try:
        offset = (page - 1) * page_size
        with conn.cursor() as cur:
            cur.execute(
                'SELECT COUNT(*) as total FROM chat_history WHERE user_id = %s',
                (user_id,)
            )
            total = cur.fetchone()['total']

            cur.execute(
                'SELECT id, role, content, token_used, created_at FROM chat_history WHERE user_id = %s ORDER BY created_at ASC LIMIT %s OFFSET %s',
                (user_id, page_size, offset)
            )
            rows = cur.fetchall()
            messages = [{
                'id': r['id'],
                'role': r['role'],
                'content': r['content'],
                'token_used': r['token_used'],
                'created_at': str(r['created_at']),
            } for r in rows]
            return {'messages': messages, 'total': total, 'page': page, 'page_size': page_size}
    finally:
        conn.close()


def get_knowledge_bases():
    """获取所有已启用的知识库列表（按标题去重，保留最先出现的）"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id, title, content, category, created_at FROM knowledge_bases WHERE enabled = 1 ORDER BY category, created_at ASC'
            )
            rows = cur.fetchall()
            result = []
            seen_titles = set()
            for r in rows:
                title = r['title']
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                content = r['content']
                # 生成摘要：前80字
                summary = content[:80] + '...' if len(content) > 80 else content
                result.append({
                    'id': r['id'],
                    'title': title,
                    'summary': summary,
                    'category': r['category'],
                    'created_at': str(r['created_at']),
                })
            return result
    finally:
        conn.close()


def get_knowledge_base_detail(kb_id):
    """获取单条知识库完整内容"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id, title, content, category, created_at FROM knowledge_bases WHERE id = %s AND enabled = 1',
                (kb_id,)
            )
            row = cur.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'title': row['title'],
                    'content': row['content'],
                    'category': row['category'],
                    'created_at': str(row['created_at']),
                }
            return None
    finally:
        conn.close()
