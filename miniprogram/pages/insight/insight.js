const app = getApp();

Page({
  data: {
    insight: null,
    insights: [],
    loading: false
  },

  onShow() {
    this.loadData();
  },

  async loadData() {
    this.setData({ loading: true });
    try {
      const [weekly, history] = await Promise.all([
        app.request('/insight/weekly'),
        app.request('/insight/history')
      ]);
      this.setData({
        insight: weekly && weekly.content ? weekly : null,
        insights: history.insights || []
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
  }
});
