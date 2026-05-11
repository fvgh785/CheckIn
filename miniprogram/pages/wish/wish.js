const app = getApp();

Page({
  data: {
    isLoggedIn: false,
    wishes: [],
    loading: false,
    showCreate: false,
    content: '',
    targetDays: 30,
    customDays: '',
    presetDays: [7, 15, 30, 60, 100, 365]
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 3 });
    }
    this.checkLoginStatus();
  },

  checkLoginStatus() {
    const token = app.globalData.token || wx.getStorageSync('token');
    if (token) {
      app.globalData.token = token;
      this.setData({ isLoggedIn: true });
      this.loadWishes();
    } else {
      this.setData({
        isLoggedIn: false,
        wishes: [],
        showCreate: false,
        content: '',
        targetDays: 30,
        customDays: ''
      });
    }
  },

  async loadWishes() {
    this.setData({ loading: true });
    try {
      const res = await app.request('/wish/list');
      this.setData({ wishes: res.wishes || [] });
    } catch (e) {
      if (e.statusCode === 401) app.handleAuthExpired();
      else if (e.statusCode === 403) wx.showToast({ title: '该功能需要会员', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  async handleCreate() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    const content = this.data.content.trim();
    if (!content) {
      wx.showToast({ title: '请输入心愿内容', icon: 'none' });
      return;
    }
    try {
      await app.request('/wish/create', {
        method: 'POST',
        data: { content, target_days: this.data.targetDays }
      });
      wx.showToast({ title: '心愿已创建', icon: 'success' });
      this.setData({ showCreate: false, content: '', targetDays: 30 });
      this.loadWishes();
    } catch (e) {
      wx.showToast({ title: '创建失败', icon: 'error' });
    }
  },

  onContentInput(e) { this.setData({ content: e.detail.value }); },

  onDaysChange(e) { this.setData({ targetDays: parseInt(e.detail.value) || 30 }); },

  onDaysTap(e) {
    const days = parseInt(e.currentTarget.dataset.days);
    this.setData({ targetDays: days, customDays: '' });
  },

  onDaysInput(e) {
    const val = e.detail.value;
    this.setData({ customDays: val });
    const days = parseInt(val);
    if (days >= 7 && days <= 365) {
      this.setData({ targetDays: days });
    }
  },

  toggleCreate() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    this.setData({ showCreate: !this.data.showCreate });
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  }
});
