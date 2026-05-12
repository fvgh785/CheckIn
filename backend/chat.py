import os
import uuid
import json
import logging
import threading
import traceback
from datetime import date, datetime

import requests
import chromadb
from chromadb.config import Settings

from db import get_connection, init_db

_logger = logging.getLogger(__name__)

AI_API_KEY = os.environ.get('AI_API_KEY', '')
AI_API_URL = os.environ.get('AI_API_URL', 'https://api.deepseek.com/v1/chat/completions')
AI_MODEL = os.environ.get('AI_MODEL', 'deepseek-chat')
EMBEDDING_URL = os.environ.get('EMBEDDING_URL', 'https://api.deepseek.com/v1/embeddings')
EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'deepseek-chat')

CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'chroma_db')
COLLECTION_NAME = 'knowledge_bases'

_chroma_client = None
_collection = None
_vector_store_initialized = False
_lock = threading.Lock()

# ======================== 向量存储初始化 ========================


def _get_chroma_client():
    """懒加载 Chroma 客户端（线程安全）"""
    global _chroma_client
    if _chroma_client is None:
        with _lock:
            if _chroma_client is None:
                os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
                _chroma_client = chromadb.PersistentClient(
                    path=CHROMA_PERSIST_DIR,
                    settings=Settings(anonymized_telemetry=False),
                )
    return _chroma_client


def _get_collection():
    """获取或创建 collection（线程安全）"""
    global _collection
    if _collection is None:
        with _lock:
            if _collection is None:
                client = _get_chroma_client()
                try:
                    _collection = client.get_collection(COLLECTION_NAME)
                except Exception:
                    _collection = client.create_collection(COLLECTION_NAME)
    return _collection


def _get_embedding(text):
    """调用 DeepSeek Embedding API 获取向量"""
    if not AI_API_KEY:
        _logger.warning('AI_API_KEY not configured, using fallback embedding')
        return [0.0] * 1024  # fallback

    try:
        headers = {
            'Authorization': f'Bearer {AI_API_KEY}',
            'Content-Type': 'application/json',
        }
        body = {
            'model': EMBEDDING_MODEL,
            'input': text,
        }
        resp = requests.post(EMBEDDING_URL, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        return result['data'][0]['embedding']
    except Exception:
        _logger.error(f'Embedding API call failed: {traceback.format_exc()}')
        # fallback: simple hash-based embedding for graceful degradation
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        return [float(b) / 255.0 for b in h[:1024]]


def init_vector_store():
    """启动时/首次调用时从 knowledge_bases 表构建向量索引"""
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
        _logger.info('No enabled knowledge bases found, skipping vector store init')
        return

    collection = _get_collection()

    ids = []
    documents = []
    metadatas = []
    embeddings = []

    for row in rows:
        kb_id = row['id']
        full_text = f"{row['title']}\n{row['content']}"
        emb = _get_embedding(full_text)

        ids.append(kb_id)
        documents.append(full_text)
        metadatas.append({
            'id': kb_id,
            'title': row['title'],
            'category': row['category'],
        })
        embeddings.append(emb)

    # 清空并重建
    try:
        existing = collection.get()
        if existing.get('ids'):
            collection.delete(ids=existing['ids'])
    except Exception:
        pass

    if ids:
        collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
        _logger.info(f'Vector store initialized with {len(ids)} knowledge bases')


def rebuild_vector_store():
    """公开接口，admin 修改知识库后调用重建（线程安全）"""
    global _collection, _vector_store_initialized
    with _lock:
        _collection = None  # 重置，下次 _get_collection 会重新获取
        init_vector_store()
        _vector_store_initialized = True


# ======================== RAG 检索 ========================


def _ensure_vector_store():
    """惰性初始化向量存储（首次 RAG 调用时触发，避免阻塞 worker 启动）"""
    global _vector_store_initialized
    if _vector_store_initialized:
        return
    with _lock:
        if _vector_store_initialized:
            return
        # 带重试的初始化
        for attempt in range(1, 4):
            try:
                init_vector_store()
                _vector_store_initialized = True
                _logger.info('Vector store lazily initialized')
                return
            except Exception:
                _logger.error(
                    f'init_vector_store attempt {attempt}/3 failed: {traceback.format_exc()}'
                )
                if attempt < 3:
                    import time
                    time.sleep(2)
        _logger.critical('Vector store initialization failed after all attempts, RAG will be unavailable')


def build_rag_context(user_message):
    """将用户问题向量化，在 Chroma 中检索 Top-3 最相关片段"""
    _ensure_vector_store()

    if not AI_API_KEY:
        return ''

    collection = _get_collection()
    try:
        existing = collection.get()
        if not existing.get('ids'):
            return ''
    except Exception:
        return ''

    query_embedding = _get_embedding(user_message)

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=3,
            include=['documents', 'metadatas', 'distances'],
        )
    except Exception:
        _logger.error(f'Chroma query failed: {traceback.format_exc()}')
        return ''

    if not results['ids'] or not results['ids'][0]:
        return ''

    snippets = []
    for i in range(len(results['ids'][0])):
        title = results['metadatas'][0][i].get('title', '未知')
        doc = results['documents'][0][i]
        snippets.append(f'【{title}】\n{doc}')

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
    """获取所有已启用的知识库列表"""
    init_db()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id, title, content, category, created_at FROM knowledge_bases WHERE enabled = 1 ORDER BY category, created_at ASC'
            )
            rows = cur.fetchall()
            result = []
            for r in rows:
                content = r['content']
                # 生成摘要：前80字
                summary = content[:80] + '...' if len(content) > 80 else content
                result.append({
                    'id': r['id'],
                    'title': r['title'],
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
