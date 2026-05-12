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

# ======================== 关键词提取（公共） ========================

# 停用词表：分词时过滤掉无实义的常见词
STOP_WORDS = {
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
    '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有',
    '看', '好', '自己', '这', '他', '她', '它', '们', '那', '什么', '怎么',
    '如何', '为什么', '哪', '吗', '吧', '呢', '啊', '哦', '嗯', '可以', '能',
    '请问', '一下', '现在', '已经', '还是', '这个', '那个', '哪些', '这些',
    '如果', '需要', '应该', '是否', '知道', '告诉', '帮忙', '帮我',
}


def _extract_keywords(text):
    """使用 jieba 中文分词提取关键词，过滤单字和停用词"""
    if not text or not text.strip():
        return []
    return [w for w in jieba.cut(text.strip()) if len(w) > 1 and w.strip() and w not in STOP_WORDS]


# ======================== 知识库关键词检索 ========================


def build_rag_context(user_message):
    """使用 jieba 中文分词 + 关键词匹配从知识库检索 Top-3 最相关条目
    
    策略：
    1. jieba 分词提取关键词，按精确命中计数打分（标题×3，内容×1）
    2. 若关键词匹配无结果，回退到 MySQL LIKE 模糊搜索
    """
    if not user_message or not AI_API_KEY:
        return ''

    keywords = _extract_keywords(user_message)

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
        _logger.warning('build_rag_context: no enabled knowledge base entries found in DB')
        return ''

    # 策略1：关键词精确匹配计分
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

    # 策略2：关键词匹配无结果时，回退到 MySQL LIKE 模糊搜索
    if not scored and keywords:
        _logger.info(
            'build_rag_context: keyword exact match failed for "%s" (keywords=%s), falling back to LIKE search',
            user_message[:50], keywords
        )
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                # 用每个关键词做 LIKE 搜索
                like_clauses = []
                like_params = []
                for kw in keywords:
                    like_clauses.append('(title LIKE %s OR content LIKE %s)')
                    like_params.extend([f'%{kw}%', f'%{kw}%'])

                sql = 'SELECT id, title, content, category FROM knowledge_bases WHERE enabled = 1 AND (' + ' OR '.join(like_clauses) + ')'
                cur.execute(sql, like_params)
                like_rows = cur.fetchall()
        finally:
            conn.close()

        for row in like_rows:
            full_text = f"{row['title']}\n{row['content']}"
            # LIKE 命中的给基础分 1，保证能参与排序
            scored.append((1, row['title'], full_text))

    if not scored:
        _logger.info('build_rag_context: no matches found for "%s" (keywords=%s)', user_message[:50], keywords)
        return ''

    # 按得分降序排列，取 Top-3
    scored.sort(key=lambda x: x[0], reverse=True)
    top_results = scored[:3]

    snippets = []
    for _, title, text in top_results:
        # 截断过长内容（最多500字），避免 context 过大
        display_text = text if len(text) <= 500 else text[:500] + '...'
        snippets.append(f'【{title}】\n{display_text}')

    _logger.info('build_rag_context: matched %d entries for "%s"', len(top_results), user_message[:30])
    return '\n\n---\n\n'.join(snippets)


# ======================== 智能话题切换检测 ========================

# 话题重叠度阈值：当前消息关键词与历史关键词的交集占比低于此值时，判定为新话题
TOPIC_OVERLAP_THRESHOLD = 0.25


def _detect_topic_switch(current_message, history_messages):
    """
    检测当前消息是否属于新话题，避免跨话题上下文污染。

    策略：提取当前消息关键词，与历史中所有 user 消息的关键词比较，
    若交集占当前关键词的比例低于阈值，则判定为新话题（应重置上下文）。

    Args:
        current_message: 当前用户消息文本
        history_messages: 历史消息列表 [{'role':..., 'content':...}, ...]

    Returns:
        True  — 话题已切换，建议只发送当前消息
        False — 话题延续，可保留历史上下文
    """
    if not history_messages:
        return False

    current_keywords = set(_extract_keywords(current_message))

    # 收集历史中最近 N 条 user 消息的关键词（窗口限制，防止长期对话关键词膨胀）
    history_keywords = set()
    user_msg_count = 0
    MAX_USER_MSGS = 6  # 与上下文窗口 messages[-6:] 保持一致
    for msg in reversed(history_messages):
        if msg.get('role') == 'user':
            history_keywords.update(_extract_keywords(msg.get('content', '')))
            user_msg_count += 1
            if user_msg_count >= MAX_USER_MSGS:
                break

    # 当前消息无法提取关键词（如"你是谁"、"好的"、纯语气词等）
    if not current_keywords:
        # 极短消息（≤4字）几乎总是对上一轮的回应/追问，保留上下文
        if len(current_message.strip()) <= 4:
            _logger.info(
                '_detect_topic_switch: short msg with no keywords "%s", keeping context',
                current_message[:30]
            )
            return False
        # 较长但无关键词的消息（罕见），历史有关键词则判定为话题切换
        return bool(history_keywords)

    if not history_keywords:
        return False

    overlap = current_keywords & history_keywords
    overlap_ratio = len(overlap) / len(current_keywords)

    _logger.info(
        '_detect_topic_switch: current="%s" cur_kw=%s hist_kw=%s '
        'overlap=%s ratio=%.2f thresh=%.2f switch=%s',
        current_message[:30], current_keywords, history_keywords,
        overlap, overlap_ratio, TOPIC_OVERLAP_THRESHOLD,
        overlap_ratio < TOPIC_OVERLAP_THRESHOLD
    )

    return overlap_ratio < TOPIC_OVERLAP_THRESHOLD


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

    # === 智能上下文窗口：检测话题是否切换 ===
    msgs_for_api = [{'role': 'system', 'content': system_content}]

    # 分离当前消息和历史消息
    if len(messages) > 1:
        history = messages[:-1]  # 历史消息（不含当前用户消息）
        current_msg = messages[-1]
    else:
        history = []
        current_msg = messages[0] if messages else {'role': 'user', 'content': ''}

    # 检测话题是否切换
    topic_switched = _detect_topic_switch(
        current_msg.get('content', ''),
        history
    )

    if topic_switched:
        # 新话题：只发送当前消息，不带历史上下文，避免污染
        msgs_for_api.append(current_msg)
        _logger.info('chat_with_ai: topic switched, sending only current message: "%s"',
                     user_message[:30])
    else:
        # 同话题延续：保留最近6条（3轮）上下文
        recent_history = messages[-6:]
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


def get_chat_history(user_id, page=1, page_size=20, newest_first=False):
    """分页获取历史对话
    
    Args:
        newest_first: True 返回最新消息在前（DESC），False 返回最早消息在前（ASC）
    """
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
                'SELECT id, role, content, token_used, created_at FROM chat_history WHERE user_id = %s ORDER BY created_at {} LIMIT %s OFFSET %s'.format(
                    'DESC' if newest_first else 'ASC'
                ),
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
