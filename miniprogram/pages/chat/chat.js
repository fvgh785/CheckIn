const app = getApp();

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
      this.loadQuota();
      this.loadHistory(false);
    } else {
      this.setData({
        isLoggedIn: false,
        messages: [],
        quota: { used: 0, remaining: 0, limit: 5000 }
      });
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
      const newMsgs = res.messages || [];
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
          created_at: ''
        });
        this.setData({
          messages: finalMessages,
          quota: res.quota || this.data.quota
        });
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
