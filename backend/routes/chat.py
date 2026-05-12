import logging
import traceback
from flask import Blueprint, request, jsonify, g
from middleware.auth import auth_required
from chat import (
    check_chat_quota, pre_check_chat_quota, save_chat_message,
    get_chat_history, chat_with_ai, get_knowledge_bases, get_knowledge_base_detail,
    is_chat_enabled, init_vector_store,
)

chat_bp = Blueprint('chat', __name__)
_logger = logging.getLogger(__name__)


# ======================== 对话接口 ========================


@chat_bp.route('/chat/send', methods=['POST'])
@auth_required
def handle_chat_send():
    """发送消息"""
    # 检查全局开关
    if not is_chat_enabled():
        return jsonify({'success': False, 'message': 'AI助手功能当前已关闭'}), 503

    data = request.get_json(silent=True) or {}
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'error': '消息不能为空'}), 400
    if len(user_message) > 500:
        return jsonify({'error': '消息过长，请控制在500字以内'}), 400

    user_id = g.user['userId']

    # 检查配额（预检：已超限则拒绝）
    pre_result = pre_check_chat_quota(user_id)
    if not pre_result['success']:
        return jsonify({
            'success': False,
            'message': pre_result['message'],
            'quota': {'remaining': 0, 'limit': pre_result['limit']},
        }), 429

    # 保存用户消息
    save_chat_message(user_id, 'user', user_message, 0)

    # 获取最近对话历史
    history = get_chat_history(user_id, page=1, page_size=20)
    messages = []
    for m in history['messages']:
        messages.append({'role': m['role'], 'content': m['content']})

    # 调用 AI
    reply, token_used = chat_with_ai(user_id, messages)

    # 事后校验：实际消耗是否超过当日剩余额度
    quota_after = check_chat_quota(user_id)
    limit = quota_after['limit']
    already_used = quota_after['used'] - token_used
    if already_used + token_used > limit:
        return jsonify({
            'success': False,
            'message': f'本次对话消耗 {token_used} token，超出今日上限（{limit}/天），请明天再来',
            'quota': {'remaining': max(0, limit - already_used), 'limit': limit},
        }), 429

    # 保存 AI 回复
    save_chat_message(user_id, 'assistant', reply, token_used)

    return jsonify({
        'success': True,
        'reply': reply,
        'token_used': token_used,
        'quota': quota_after,
    })


@chat_bp.route('/chat/history', methods=['GET'])
@auth_required
def handle_chat_history():
    """获取历史对话"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 50:
        page_size = 20

    try:
        result = get_chat_history(g.user['userId'], page=page, page_size=page_size)
        return jsonify(result)
    except Exception:
        _logger.error(f'get_chat_history failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@chat_bp.route('/chat/quota', methods=['GET'])
@auth_required
def handle_chat_quota():
    """查询今日剩余额度"""
    try:
        quota = check_chat_quota(g.user['userId'])
        return jsonify(quota)
    except Exception:
        _logger.error(f'check_chat_quota failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


# ======================== 知识库展示接口 ========================


@chat_bp.route('/chat/knowledge-bases', methods=['GET'])
@auth_required
def handle_knowledge_bases():
    """获取已启用的知识库列表"""
    try:
        bases = get_knowledge_bases()
        return jsonify({'knowledge_bases': bases})
    except Exception:
        _logger.error(f'get_knowledge_bases failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500


@chat_bp.route('/chat/knowledge-bases/<kb_id>', methods=['GET'])
@auth_required
def handle_knowledge_base_detail(kb_id):
    """获取单条知识库详情"""
    try:
        kb = get_knowledge_base_detail(kb_id)
        if kb:
            return jsonify(kb)
        return jsonify({'error': '知识库条目不存在'}), 404
    except Exception:
        _logger.error(f'get_knowledge_base_detail failed: {traceback.format_exc()}')
        return jsonify({'error': '服务器内部错误'}), 500
