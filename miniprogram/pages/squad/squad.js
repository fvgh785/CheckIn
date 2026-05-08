const app = getApp();

Page({
  data: {
    hasSquad: false,
    squad: null,
    isMember: false,
    loading: false,
    showCreate: false,
    showJoin: false,
    squadName: '',
    inviteCode: ''
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 });
    }
    this.checkStatus();
  },

  async checkStatus() {
    try {
      const memberRes = await app.request('/membership/status');
      this.setData({ isMember: memberRes.active });
    } catch (e) {
      this.setData({ isMember: false });
    }
    this.loadSquad();
  },

  async loadSquad() {
    this.setData({ loading: true });
    try {
      const res = await app.request('/squad/my');
      this.setData({
        hasSquad: res.has_squad,
        squad: res.squad || null
      });
    } catch (e) {
      if (e.statusCode === 401) {
        app.handleAuthExpired();
      } else {
        console.error('加载小队失败:', e);
      }
    } finally {
      this.setData({ loading: false });
    }
  },

  async handleCreate() {
    if (!this.data.isMember) {
      wx.showToast({ title: '创建小队需要会员', icon: 'none' });
      return;
    }
    const name = this.data.squadName.trim();
    if (!name) {
      wx.showToast({ title: '请输入小队名称', icon: 'none' });
      return;
    }
    try {
      const res = await app.request('/squad/create', {
        method: 'POST',
        data: { name }
      });
      if (res.success) {
        wx.showToast({ title: '小队创建成功', icon: 'success' });
        this.setData({ showCreate: false, squadName: '' });
        this.loadSquad();
      }
    } catch (e) {
      wx.showToast({ title: '创建失败', icon: 'error' });
    }
  },

  async handleJoin() {
    const code = this.data.inviteCode.trim().toUpperCase();
    if (!code) {
      wx.showToast({ title: '请输入邀请码', icon: 'none' });
      return;
    }
    try {
      const res = await app.request('/squad/join', {
        method: 'POST',
        data: { code }
      });
      if (res.success) {
        wx.showToast({ title: '加入成功', icon: 'success' });
        this.setData({ showJoin: false, inviteCode: '' });
        this.loadSquad();
      }
    } catch (e) {
      if (e.data && e.data.error) {
        wx.showToast({ title: e.data.error, icon: 'none' });
      } else {
        wx.showToast({ title: '加入失败', icon: 'error' });
      }
    }
  },

  onNameInput(e) {
    this.setData({ squadName: e.detail.value });
  },

  onCodeInput(e) {
    this.setData({ inviteCode: e.detail.value });
  },

  toggleCreate() {
    this.setData({ showCreate: !this.data.showCreate, showJoin: false });
  },

  toggleJoin() {
    this.setData({ showJoin: !this.data.showJoin, showCreate: false });
  }
});
