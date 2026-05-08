const app = getApp();

Page({
  data: {
    loading: false,
    loggedIn: false,
    nickname: '',
    phone: '',
    saving: false
  },

  /**
   * 一键登录：open-type="getPhoneNumber" 触发
   * 微信弹出手机号授权 → 用户同意 → 同时获取登录code和手机号code
   */
  handleLoginWithPhone(e) {
    const { code: phoneCode, errMsg } = e.detail;

    // 用户拒绝手机号授权
    if (errMsg && errMsg.includes('fail')) {
      wx.showModal({
        title: '需要手机号授权',
        content: '手机号是账号安全的基础，请授权后登录。重试请再次点击按钮。',
        showCancel: false,
        confirmText: '知道了'
      });
      return;
    }

    // 开发工具/模拟器不支持 getPhoneNumber
    if (!phoneCode) {
      wx.showModal({
        title: '提示',
        content: '手机号授权需要在真机上操作。请使用真机预览或体验版测试。',
        showCancel: false,
        confirmText: '知道了'
      });
      return;
    }

    this.setData({ loading: true });

    // 获取登录凭证
    wx.login({
      success: (res) => {
        if (!res.code) {
          wx.showToast({ title: '登录失败', icon: 'error' });
          this.setData({ loading: false });
          return;
        }
        // 一次请求同时完成登录和手机号换取
        this.loginWithPhone(res.code, phoneCode);
      },
      fail: () => {
        wx.showToast({ title: '登录失败', icon: 'error' });
        this.setData({ loading: false });
      }
    });
  },

  loginWithPhone(code, phoneCode) {
    wx.request({
      url: app.globalData.apiBase.replace('/api', '') + '/api/auth/login',
      method: 'POST',
      data: { code, phone_code: phoneCode },
      header: { 'Content-Type': 'application/json' },
      success: (res) => {
        if (res.statusCode === 200 && res.data.token) {
          wx.setStorageSync('token', res.data.token);
          app.globalData.token = res.data.token;

          const phone = res.data.phone || '';
          const nickname = res.data.nickname || '';

          this.setData({
            loading: false,
            loggedIn: true,
            phone: phone,
            nickname: nickname
          });

          // 手机号已获取 + 昵称已有 → 直接进入首页
          if (phone && nickname) {
            this.goToIndex();
          }
          // 手机号已获取但无昵称 → 停留完善资料页，手机号只读展示
          // phone 存在则自动显示 "✓ 已授权"
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

  handleGoBack() {
    // 返回登录初始状态
    this.setData({
      loggedIn: false,
      nickname: '',
      phone: '',
      saving: false
    });
  },

  handleConfirmProfile() {
    const { nickname } = this.data;

    // 昵称可选，没填直接进入首页
    if (!nickname.trim()) {
      this.goToIndex();
      return;
    }

    this.setData({ saving: true });

    app.request('/api/auth/update-profile', {
      method: 'POST',
      data: { nickname: nickname.trim() }
    }).then(() => {
      wx.showToast({ title: '资料保存成功', icon: 'success' });
      setTimeout(() => {
        this.goToIndex();
      }, 500);
    }).catch((err) => {
      const msg = (err && err.data && err.data.error) || '保存失败';
      wx.showToast({ title: msg, icon: 'none' });
      this.setData({ saving: false });
    });
  },

  goToIndex() {
    wx.reLaunch({ url: '/pages/index/index' });
  }
});
