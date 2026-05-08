const app = getApp();

Page({
  data: {
    loading: false,
    loggedIn: false,
    nickname: '',
    phone: '',
    gettingPhone: false,
    saving: false
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

          // 如果有已存储的手机号/昵称，先填上
          const phone = res.data.phone || '';
          const nickname = res.data.nickname || '';

          this.setData({
            loading: false,
            loggedIn: true,
            phone: phone,
            nickname: nickname
          });

          // 如果资料已完善，直接跳转
          if (phone && nickname) {
            this.goToIndex();
          }
        } else {
          wx.showToast({ title: res.data.error || '登录失败', icon: 'error' });
          this.setData({ loading: false });
        }
      },
      fail: () => {
        wx.showToast({ title: '网络错误', icon: 'error' });
        this.setData({ loading: false });
      }
    });
  },

  onNicknameInput(e) {
    this.setData({ nickname: e.detail.value });
  },

  onGetPhoneNumber(e) {
    const { code } = e.detail;
    if (!code) {
      wx.showToast({ title: '获取手机号失败', icon: 'none' });
      return;
    }

    this.setData({ gettingPhone: true });
    app.request('/api/auth/exchange-phone', {
      method: 'POST',
      data: { phone_code: code }
    }).then((res) => {
      if (res.phone) {
        this.setData({ phone: res.phone });
        wx.showToast({ title: '手机号获取成功', icon: 'success' });
      }
    }).catch((err) => {
      const msg = (err.data && err.data.error) || '手机号获取失败';
      wx.showToast({ title: msg, icon: 'none' });
    }).finally(() => {
      this.setData({ gettingPhone: false });
    });
  },

  handleSkipProfile() {
    this.goToIndex();
  },

  handleConfirmProfile() {
    const { nickname, phone } = this.data;

    // 如果什么都没填，直接跳过
    if (!nickname && !phone) {
      this.goToIndex();
      return;
    }

    this.setData({ saving: true });

    const promises = [];
    if (nickname) {
      promises.push(
        app.request('/api/auth/update-profile', {
          method: 'POST',
          data: { nickname }
        })
      );
    }
    // phone 已通过 exchange-phone 接口实时保存，无需再次提交

    if (promises.length === 0) {
      this.goToIndex();
      return;
    }

    Promise.all(promises).then(() => {
      wx.showToast({ title: '资料保存成功', icon: 'success' });
      setTimeout(() => {
        this.goToIndex();
      }, 500);
    }).catch((err) => {
      const msg = (err.data && err.data.error) || '保存失败';
      wx.showToast({ title: msg, icon: 'none' });
      this.setData({ saving: false });
    });
  },

  goToIndex() {
    wx.reLaunch({ url: '/pages/index/index' });
  }
});
