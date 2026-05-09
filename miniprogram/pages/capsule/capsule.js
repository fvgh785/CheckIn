const app = getApp();

Page({
  data: {
    capsules: [],
    loading: false,
    showCreate: false,
    content: '',
    targetStreak: 30,
    customStreak: '',
    presetStreaks: [7, 14, 21, 30, 60, 100],
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
  onStreakTap(e) {
    const days = parseInt(e.currentTarget.dataset.days);
    this.setData({ targetStreak: days, customStreak: '' });
  },

  onStreakInput(e) {
    const val = e.detail.value;
    this.setData({ customStreak: val });
    const days = parseInt(val);
    if (days >= 7 && days <= 365) {
      this.setData({ targetStreak: days });
    }
  },

  toggleCreate() {
    const show = !this.data.showCreate;
    this.setData({ showCreate: show });
    if (show) {
      // 延迟滚动，等待 DOM 渲染完成
      setTimeout(() => {
        wx.pageScrollTo({ selector: '.create-panel', duration: 300 });
      }, 150);
    }
  }
});
