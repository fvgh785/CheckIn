App({
  globalData: {
    apiBase: 'https://checkin.morefun.wang/api',
    token: ''
  },

  onLaunch() {
    // 启动时自动读取本地存储的 token，实现免登
    const token = wx.getStorageSync('token');
    if (token) {
      this.globalData.token = token;
    }
  },

  onShow() {
    // 每次从后台切入前台时，也检查一次 token，确保状态同步
    const token = wx.getStorageSync('token');
    if (token) {
      this.globalData.token = token;
    }
  }
});

