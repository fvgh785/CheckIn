const app = getApp();

Page({
  data: {
    capsules: [],
    loading: false,
    showCreate: false,
    content: '',
    targetStreak: 30,
    currentStreak: 0,
    openedCapsule: null
  },

  onLoad() {
    this.loadData();
  },

  async loadData() {
    this.setData({ loading: true });
    try {
      const stats = await app.request('/stats');
      this.setData({ currentStreak: stats.current_streak });

      const res = await app.request('/capsule/list');
      this.setData({ capsules: res.capsules || [] });
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
      wx.showToast({ title: '请写信给未来的自己', icon: 'none' });
      return;
    }
    try {
      await app.request('/capsule/create', {
        method: 'POST',
        data: {
          content,
          target_streak: this.data.targetStreak,
          current_streak: this.data.currentStreak
        }
      });
      wx.showToast({ title: '胶囊已封印', icon: 'success' });
      this.setData({ showCreate: false, content: '', targetStreak: 30 });
      this.loadData();
    } catch (e) {
      wx.showToast({ title: '创建失败', icon: 'error' });
    }
  },

  async handleOpen(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const res = await app.request(`/capsule/open/${id}`, {
        method: 'POST',
        data: { current_streak: this.data.currentStreak }
      });
      if (res.success) {
        this.setData({ openedCapsule: res });
        wx.showToast({ title: '胶囊已开启！', icon: 'success' });
        this.loadData();
      }
    } catch (e) {
      if (e.statusCode === 401) {
        app.handleAuthExpired();
      } else if (e.statusCode === 403) {
        wx.showToast({ title: '该功能需要会员', icon: 'none' });
      } else if (e.data && e.data.message) {
        wx.showToast({ title: e.data.message, icon: 'none' });
      } else {
        wx.showToast({ title: '开启失败，请稍后重试', icon: 'none' });
      }
    }
  },

  closeModal() { this.setData({ openedCapsule: null }); },

  onContentInput(e) { this.setData({ content: e.detail.value }); },
  onStreakChange(e) { this.setData({ targetStreak: parseInt(e.detail.value) || 30 }); },
  toggleCreate() { this.setData({ showCreate: !this.data.showCreate }); }
});
