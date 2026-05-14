const app = getApp();

Page({
  data: {
    isLoggedIn: false,
    isMember: false,
    insight: null,
    insights: [],
    loading: false,
    generating: false,
    quota: { remaining: 0, limit: 3 }
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: '/pages/insight/insight' });
    }
    this.checkLoginStatus();
  },

  checkLoginStatus() {
    const token = app.globalData.token || wx.getStorageSync('token');
    if (token) {
      app.globalData.token = token;
      this.setData({ isLoggedIn: true });
      this.loadAll();
    } else {
      this.setData({
        isLoggedIn: false,
        isMember: false,
        insight: null,
        insights: [],
        quota: { remaining: 0, limit: 3 }
      });
    }
  },

  async loadMembershipStatus() {
    if (!this.data.isLoggedIn) return;
    try {
      const res = await app.request('/membership/status');
      const active = res.active || false;
      this.setData({ isMember: active });
      app.globalData.isMember = active;
    } catch (e) {
      console.error('获取会员状态失败:', e);
    }
  },

  async loadAll() {
    await this.loadMembershipStatus();
    this.loadData();
  },

  async loadData() {
    this.setData({ loading: true });
    try {
      const [weekly, history, quotaData] = await Promise.all([
        app.request('/insight/weekly'),
        app.request('/insight/history'),
        app.request('/insight/generate/quota')
      ]);
      this.setData({
        insight: weekly && weekly.content ? weekly : null,
        insights: history.insights || [],
        quota: quotaData || { remaining: 0, limit: 3 }
      });
    } catch (e) {
      if (e.statusCode === 401) {
        app.handleAuthExpired();
      } else if (e.statusCode === 403) {
        wx.showToast({ title: '该功能需要会员', icon: 'none' });
      }
    } finally {
      this.setData({ loading: false });
    }
  },

  async handleGenerate() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    if (this.data.generating) return;

    wx.showLoading({ title: '生成中...', mask: true });
    this.setData({ generating: true });

    try {
      const res = await app.request('/insight/generate', { method: 'POST' });
      if (res.success) {
        wx.showToast({ title: '洞察已生成！', icon: 'success' });
        this.setData({
          insight: res.insight,
          quota: res.quota
        });
        // 刷新历史列表
        this.loadData();
      } else {
        wx.showToast({ title: res.message || '生成失败', icon: 'none' });
        // 刷新配额
        try {
          const quotaData = await app.request('/insight/generate/quota');
          this.setData({ quota: quotaData });
        } catch (e) { /* ignore */ }
      }
    } catch (e) {
      if (e.statusCode === 429) {
        wx.showToast({ title: '今日次数已用完', icon: 'none' });
        this.setData({ quota: { remaining: 0, limit: this.data.quota.limit } });
      } else if (e.statusCode === 400) {
        const msg = (e.data && e.data.message) ? e.data.message : '暂无打卡数据';
        wx.showToast({ title: msg, icon: 'none' });
      } else {
        wx.showToast({ title: '生成失败，请稍后重试', icon: 'none' });
      }
    } finally {
      this.setData({ generating: false });
      wx.hideLoading();
    }
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  }
});
