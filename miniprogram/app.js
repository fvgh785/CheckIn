App({
  globalData: {
    apiBase: 'https://checkin.morefun.wang/api',
    token: '',
    isLoggedIn: false
  },

  onLaunch() {
    const token = wx.getStorageSync('token');
    if (token) {
      this.globalData.token = token;
      this.globalData.isLoggedIn = true;
    }
  },

  onShow() {
    const token = wx.getStorageSync('token');
    if (token) {
      this.globalData.token = token;
      this.globalData.isLoggedIn = true;
    }
  },

  /**
   * 通用请求方法，自动带Token
   */
  request(path, options = {}) {
    return new Promise((resolve, reject) => {
      const currentToken = this.globalData.token || wx.getStorageSync('token');
      if (!currentToken) {
        reject({ statusCode: 401 });
        return;
      }

      wx.request({
        url: this.globalData.apiBase + path,
        method: options.method || 'GET',
        data: options.data || {},
        header: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${currentToken}`
        },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res.data);
          } else {
            reject(res);
          }
        },
        fail: reject
      });
    });
  },

  /**
   * 处理401登录过期
   */
  handleAuthExpired() {
    wx.removeStorageSync('token');
    this.globalData.token = '';
    this.globalData.isLoggedIn = false;
    wx.showToast({ title: '登录已失效', icon: 'none' });
  },

  /**
   * 同步登录态给 tabBar
   */
  syncLoginStatus() {
    const token = this.globalData.token || wx.getStorageSync('token');
    this.globalData.isLoggedIn = !!token;
  }
});

