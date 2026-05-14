const app = getApp();

/**
 * 将 markdown 文本转换为 rich-text 组件可用的 nodes 数组
 * 支持：标题(#)、加粗(**)、斜体(*)、行内代码(`)、链接、无序列表(-)、有序列表(1.)
 */
function parseInline(text) {
  if (!text) return [{ type: 'text', text: '' }];
  const children = [];
  let remaining = text;
  const regex = /(\*\*(.+?)\*\*)|(\*(.+?)\*)|(`(.+?)`)|(\[(.+?)\]\((.+?)\))/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(remaining)) !== null) {
    if (match.index > lastIndex) {
      children.push({ type: 'text', text: remaining.slice(lastIndex, match.index) });
    }
    if (match[1]) {
      children.push({ name: 'strong', children: [{ type: 'text', text: match[2] }] });
    } else if (match[3]) {
      children.push({ name: 'em', children: [{ type: 'text', text: match[4] }] });
    } else if (match[5]) {
      children.push({
        name: 'code',
        attrs: { style: 'background:#E8F7F6;padding:2rpx 8rpx;border-radius:4rpx;font-family:monospace;font-size:26rpx;' },
        children: [{ type: 'text', text: match[6] }]
      });
    } else if (match[7]) {
      children.push({
        name: 'a',
        attrs: { style: 'color:#5EBFB7;text-decoration:underline;' },
        children: [{ type: 'text', text: match[8] }]
      });
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < remaining.length) {
    children.push({ type: 'text', text: remaining.slice(lastIndex) });
  }
  return children.length > 0 ? children : [{ type: 'text', text }];
}

function parseMarkdownToNodes(text) {
  if (!text) return [{ type: 'text', text: '' }];
  const lines = text.split('\n');
  const nodes = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const headingMatch = line.match(/^(#{1,3})\s+(.+)/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const sizes = { 1: '36rpx', 2: '32rpx', 3: '30rpx' };
      nodes.push({
        name: 'h' + level,
        attrs: { style: 'font-size:' + (sizes[level] || '30rpx') + ';font-weight:bold;margin:16rpx 0 8rpx;' },
        children: parseInline(headingMatch[2])
      });
      i++; continue;
    }
    if (line.trim() === '') { i++; continue; }
    // 无序列表
    if (/^[-*]\s+/.test(line)) {
      const listItems = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        listItems.push({ name: 'li', children: parseInline(lines[i].replace(/^[-*]\s+/, '')) });
        i++;
      }
      nodes.push({ name: 'ul', attrs: { style: 'padding-left:36rpx;margin:8rpx 0;' }, children: listItems });
      continue;
    }
    // 有序列表
    if (/^\d+\.\s+/.test(line)) {
      const listItems = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        listItems.push({ name: 'li', children: parseInline(lines[i].replace(/^\d+\.\s+/, '')) });
        i++;
      }
      nodes.push({ name: 'ol', attrs: { style: 'padding-left:36rpx;margin:8rpx 0;' }, children: listItems });
      continue;
    }
    // 普通段落
    const paraLines = [];
    while (i < lines.length && lines[i].trim() !== '' && !/^(#{1,3}\s+|[-*]\s+|\d+\.\s+)/.test(lines[i])) {
      paraLines.push(lines[i]);
      i++;
    }
    nodes.push({ name: 'p', attrs: { style: 'margin:4rpx 0;' }, children: parseInline(paraLines.join('\n')) });
  }
  return nodes.length > 0 ? nodes : [{ type: 'text', text }];
}

Page({
  data: {
    isLoggedIn: false,
    messages: [],
    inputValue: '',
    loading: false,
    sending: false,
    quota: { used: 0, remaining: 0, limit: 5000 },
    knowledgeBases: [],
    showKnowledge: true,
    page: 1,
    hasMore: true,
    scrollToView: '',
    chatEnabled: true,
    isMember: true,
    // 知识库详情弹窗
    kbModalVisible: false,
    kbDetail: null
  },

  onLoad() {
    this.loadKnowledgeBases();
  },

  onShow() {
    this.checkLoginStatus();
  },

  checkLoginStatus() {
    const token = app.globalData.token || wx.getStorageSync('token');
    if (token) {
      app.globalData.token = token;
      this.setData({ isLoggedIn: true });
      this.loadKnowledgeBases();
      this.loadMembershipStatus();
      this.loadQuota();
      this.loadHistory(false);
    } else {
      this.setData({
        isLoggedIn: false,
        messages: [],
        quota: { used: 0, remaining: 0, limit: 5000 },
        isMember: true
      });
    }
  },

  async loadMembershipStatus() {
    if (!this.data.isLoggedIn) return;
    try {
      const res = await app.request('/membership/status');
      const isActive = res.active || false;
      this.setData({ isMember: isActive });
    } catch (e) {
      // 请求失败默认可聊天（由后端兜底校验）
      console.error('获取会员状态失败:', e);
    }
  },

  async loadKnowledgeBases() {
    if (!this.data.isLoggedIn) return;
    try {
      const res = await app.request('/chat/knowledge-bases');
      this.setData({ knowledgeBases: res.knowledge_bases || [] });
    } catch (e) {
      console.error('加载知识库失败:', e);
    }
  },

  async loadQuota() {
    if (!this.data.isLoggedIn) return;
    try {
      const res = await app.request('/chat/quota');
      this.setData({ quota: res });
    } catch (e) {
      if (e.statusCode === 401) {
        app.handleAuthExpired();
        this.setData({ isLoggedIn: false });
      }
    }
  },

  async loadHistory(append = false) {
    if (!this.data.isLoggedIn) return;
    const page = append ? this.data.page + 1 : 1;
    try {
      const res = await app.request(`/chat/history?page=${page}&page_size=20`);
      const newMsgs = (res.messages || []).reverse().map(m => ({
        ...m,
        contentNodes: m.role === 'assistant' ? parseMarkdownToNodes(m.content) : undefined
      }));
      let messages = append ? [...newMsgs, ...this.data.messages] : newMsgs;
      this.setData({
        messages,
        page,
        hasMore: newMsgs.length >= 20
      });
      if (!append && messages.length > 0) {
        this.scrollToBottom();
      }
    } catch (e) {
      if (e.statusCode === 401) {
        app.handleAuthExpired();
        this.setData({ isLoggedIn: false });
      }
    }
  },

  onInput(e) {
    this.setData({ inputValue: e.detail.value });
  },

  async handleSend() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    if (!this.data.isMember) {
      wx.showToast({ title: 'AI对话为会员专属功能', icon: 'none' });
      return;
    }
    const message = this.data.inputValue.trim();
    if (!message || this.data.sending) return;

    this.setData({ inputValue: '', sending: true });

    // 添加用户消息到界面
    const userMsg = { id: 'temp-' + Date.now(), role: 'user', content: message, created_at: '' };
    const messages = [...this.data.messages, userMsg];
    this.setData({ messages });
    this.scrollToBottom();

    try {
      const res = await app.request('/chat/send', {
        method: 'POST',
        data: { message }
      });

      if (res.success) {
        // 用真实消息替换临时消息
        const finalMessages = [...this.data.messages];
        // 替换用户临时消息
        const userIdx = finalMessages.findIndex(m => m.id === userMsg.id);
        if (userIdx >= 0) {
          finalMessages[userIdx] = { id: 'u-' + Date.now(), role: 'user', content: message, created_at: '' };
        }
        finalMessages.push({
          id: 'a-' + Date.now(),
          role: 'assistant',
          content: res.reply,
          contentNodes: parseMarkdownToNodes(res.reply),
          created_at: ''
        });
        this.setData({
          messages: finalMessages,
          quota: res.quota || this.data.quota
        });
        this.scrollToBottom();
      } else {
        wx.showToast({ title: res.message || '发送失败', icon: 'none' });
        // 移除临时消息
        this.setData({ messages: this.data.messages.filter(m => m.id !== userMsg.id) });
      }
    } catch (e) {
      if (e.statusCode === 401) {
        app.handleAuthExpired();
        this.setData({ isLoggedIn: false });
      } else if (e.statusCode === 503) {
        wx.showToast({ title: 'AI助手暂未开放', icon: 'none' });
      } else if (e.statusCode === 429) {
        wx.showToast({ title: '今日额度已用完', icon: 'none' });
      } else {
        wx.showToast({ title: '网络异常，请重试', icon: 'none' });
      }
      // 移除临时用户消息
      this.setData({ messages: this.data.messages.filter(m => m.id !== userMsg.id) });
    } finally {
      this.setData({ sending: false });
    }
  },

  handleQuickAsk(e) {
    const q = e.currentTarget.dataset.question;
    this.setData({ inputValue: q });
    this.handleSend();
  },

  async handleShowKB(e) {
    const id = e.currentTarget.dataset.id;
    wx.showLoading({ title: '加载中...' });
    try {
      const kb = await app.request(`/chat/knowledge-bases/${id}`);
      wx.hideLoading();
      this.setData({
        kbModalVisible: true,
        kbDetail: kb
      });
    } catch (err) {
      wx.hideLoading();
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  closeKBModal() {
    this.setData({ kbModalVisible: false, kbDetail: null });
  },

  toggleKnowledge() {
    this.setData({ showKnowledge: !this.data.showKnowledge });
  },

  scrollToBottom() {
    setTimeout(() => {
      this.setData({ scrollToView: 'msg-bottom' });
    }, 100);
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.loadHistory(true);
    }
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  }
});
