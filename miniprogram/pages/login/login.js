const app = getApp();

Page({
  data: {
    loading: false
  },

  handleLogin() {
    this.setData({ loading: true });

    wx.login({
      success: (res) => {
        if (!res.code) {
          wx.showToast({ title: '登录失败', icon: 'error' });
          this.setData({ loading: false });
          return;
        }
        this.loginToServer(res.code);
      },
      fail: () => {
        wx.showToast({ title: '登录失败', icon: 'error' });
        this.setData({ loading: false });
      }
    });
  },

  loginToServer(code) {
    wx.request({
      url: app.globalData.apiBase.replace('/api', '') + '/api/auth/login',
      method: 'POST',
      data: { code },
      header: { 'Content-Type': 'application/json' },
      success: (res) => {
        if (res.statusCode === 200 && res.data.token) {
          wx.setStorageSync('token', res.data.token);
          app.globalData.token = res.data.token;
          wx.showToast({ title: '登录成功', icon: 'success' });
          setTimeout(() => {
            wx.reLaunch({ url: '/pages/index/index' });
          }, 500);
        } else {
          wx.showToast({ title: res.data.error || '登录失败', icon: 'error' });
        }
      },
      fail: () => {
        wx.showToast({ title: '网络错误', icon: 'error' });
      },
      complete: () => {
        this.setData({ loading: false });
      }
    });
  }
});
