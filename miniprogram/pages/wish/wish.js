const app = getApp();

Page({
  data: {
    wishes: [],
    loading: false,
    showCreate: false,
    content: '',
    targetDays: 30
  },

  onShow() {
    this.loadWishes();
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

  toggleCreate() { this.setData({ showCreate: !this.data.showCreate }); }
});
