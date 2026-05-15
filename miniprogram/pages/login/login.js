const app = getApp();

Page({
  data: {
    loading: false,
    loggedIn: false,
    nickname: '',
    email: '',
    emailCode: '',
    emailSent: false,
    emailBound: false,
    countdown: 0,
    sendingCode: false,
    bindingEmail: false,
    saving: false,
    _countdownTimer: null
  },

  /**
   * 一键登录：纯微信登录，无需手机号
   */
  handleLogin() {
    this.setData({ loading: true });

    wx.login({
      success: (res) => {
        if (!res.code) {
          wx.showToast({ title: '登录失败', icon: 'error' });
          this.setData({ loading: false });
          return;
        }
        this.doLogin(res.code);
      },
      fail: () => {
        wx.showToast({ title: '登录失败', icon: 'error' });
        this.setData({ loading: false });
      }
    });
  },

  doLogin(code) {
    wx.request({
      url: app.globalData.apiBase.replace('/api', '') + '/api/auth/login',
      method: 'POST',
      data: { code },
      header: { 'Content-Type': 'application/json' },
      success: (res) => {
        if (res.statusCode === 200 && res.data.token) {
          wx.setStorageSync('token', res.data.token);
          app.globalData.token = res.data.token;
          app.globalData.isLoggedIn = true;

          const nickname = res.data.nickname || '';
          const email = res.data.email || '';

          this.setData({
            loading: false,
            loggedIn: true,
            nickname: nickname,
            email: email,
            emailBound: !!email
          });

          // 已有昵称 → 直接进入首页
          if (nickname) {
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

  onEmailInput(e) {
    this.setData({ email: e.detail.value.trim() });
  },

  onEmailCodeInput(e) {
    this.setData({ emailCode: e.detail.value });
  },

  /**
   * 发送邮箱验证码
   */
  handleSendEmailCode() {
    const { email } = this.data;
    if (!email) {
      wx.showToast({ title: '请输入邮箱地址', icon: 'none' });
      return;
    }
    // 简单邮箱格式校验
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      wx.showToast({ title: '邮箱格式不正确', icon: 'none' });
      return;
    }

    this.setData({ sendingCode: true });

    app.request('/auth/send-email-code', {
      method: 'POST',
      data: { email }
    }).then(() => {
      wx.showToast({ title: '验证码已发送', icon: 'success' });
      this.setData({ emailSent: true, sendingCode: false, emailCode: '' });
      this.startCountdown();
    }).catch((err) => {
      const msg = (err && err.data && err.data.error) || '发送失败';
      wx.showToast({ title: msg, icon: 'none' });
      this.setData({ sendingCode: false });
    });
  },

  /**
   * 验证码倒计时
   */
  startCountdown() {
    this.setData({ countdown: 60 });
    const timer = setInterval(() => {
      const countdown = this.data.countdown - 1;
      if (countdown <= 0) {
        clearInterval(timer);
        this.setData({ countdown: 0 });
      } else {
        this.setData({ countdown });
      }
    }, 1000);
    this.data._countdownTimer = timer;
  },

  /**
   * 绑定邮箱（验证码校验）
   */
  handleBindEmail() {
    const { email, emailCode } = this.data;
    if (!emailCode || emailCode.length < 6) {
      wx.showToast({ title: '请输入6位验证码', icon: 'none' });
      return;
    }

    this.setData({ bindingEmail: true });

    app.request('/auth/bind-email', {
      method: 'POST',
      data: { email, code: emailCode }
    }).then(() => {
      wx.showToast({ title: '邮箱绑定成功', icon: 'success' });
      this.setData({
        emailBound: true,
        bindingEmail: false,
        emailCode: '',
        emailSent: false
      });
    }).catch((err) => {
      const msg = (err && err.data && err.data.error) || '绑定失败';
      wx.showToast({ title: msg, icon: 'none' });
      this.setData({ bindingEmail: false });
    });
  },

  handleGoBack() {
    // 清除倒计时
    if (this.data._countdownTimer) {
      clearInterval(this.data._countdownTimer);
    }
    this.setData({
      loggedIn: false,
      nickname: '',
      email: '',
      emailCode: '',
      emailSent: false,
      emailBound: false,
      countdown: 0,
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

    app.request('/auth/update-profile', {
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
  },

  onUnload() {
    if (this.data._countdownTimer) {
      clearInterval(this.data._countdownTimer);
    }
  }
});
