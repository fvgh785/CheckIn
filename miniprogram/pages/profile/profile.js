const app = getApp();

Page({
  data: {
    isMember: false,
    membership: null,
    pet: null,
    makeupInfo: null,
    petName: '',
    showRename: false,
    // 邮箱绑定
    nickname: '',
    email: '',
    emailBound: false,
    emailCode: '',
    emailSent: false,
    countdown: 0,
    sendingCode: false,
    bindingEmail: false,
    _countdownTimer: null
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 4 });
    }
    this.loadData();
  },

  async loadData() {
    try {
      const memberRes = await app.request('/membership/status');
      this.setData({ isMember: memberRes.active, membership: memberRes });
      if (memberRes.active) {
        this.loadMemberData();
      }
      // 加载用户资料（昵称、邮箱）
      this.loadProfile();
    } catch (e) {
      if (e.statusCode === 401) app.handleAuthExpired();
    }
  },

  async loadProfile() {
    try {
      const profile = await app.request('/auth/profile');
      this.setData({
        nickname: profile.nickname || '',
        email: profile.email || '',
        emailBound: !!profile.email
      });
    } catch (e) {
      if (e.statusCode !== 401) {
        console.error('加载用户资料失败:', e);
      }
    }
  },

  async loadMemberData() {
    try {
      const [petRes, makeupRes] = await Promise.all([
        app.request('/membership/pet').catch(() => null),
        app.request('/checkin/makeup/info').catch(() => null)
      ]);
      this.setData({ pet: petRes, makeupInfo: makeupRes });
    } catch (e) { /* silent */ }
  },

  // ======================== 邮箱绑定 ========================

  onEmailInput(e) {
    this.setData({ email: e.detail.value.trim() });
  },

  onEmailCodeInput(e) {
    this.setData({ emailCode: e.detail.value });
  },

  handleSendEmailCode() {
    const { email } = this.data;
    if (!email) {
      wx.showToast({ title: '请输入邮箱地址', icon: 'none' });
      return;
    }
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

  // ======================== 宠物操作 ========================

  async handleRename() {
    const name = this.data.petName.trim();
    if (!name) {
      wx.showToast({ title: '请输入新名字', icon: 'none' });
      return;
    }
    try {
      await app.request('/membership/pet/name', {
        method: 'PUT',
        data: { pet_name: name }
      });
      wx.showToast({ title: '改名成功', icon: 'success' });
      this.setData({ showRename: false, petName: '' });
      this.loadMemberData();
    } catch (e) {
      wx.showToast({ title: '改名失败', icon: 'error' });
    }
  },

  onPetNameInput(e) { this.setData({ petName: e.detail.value }); },

  toggleRename() { this.setData({ showRename: !this.data.showRename }); },

  goToCapsule() {
    wx.navigateTo({ url: '/pages/capsule/capsule' });
  },

  onUnload() {
    if (this.data._countdownTimer) {
      clearInterval(this.data._countdownTimer);
    }
  }
});
