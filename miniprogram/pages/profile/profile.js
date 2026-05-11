const app = getApp();

Page({
  data: {
    isLoggedIn: false,
    isMember: false,
    membership: null,
    pet: null,
    makeupInfo: null,
    // 昵称编辑
    showNicknameEdit: false,
    nicknameInput: '',
    nickname: '',
    // 邮箱绑定/换绑
    email: '',
    emailBound: false,
    showRebind: false,
    rebindEmail: '',
    emailCode: '',
    emailSent: false,
    countdown: 0,
    sendingCode: false,
    bindingEmail: false,
    _countdownTimer: null,
    // 宠物改名
    petName: '',
    showRename: false,
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 4 });
    }
    this.checkLoginStatus();
  },

  onLoad() {},

  checkLoginStatus() {
    const token = app.globalData.token || wx.getStorageSync('token');
    if (token) {
      app.globalData.token = token;
      this.setData({ isLoggedIn: true });
      this.loadData();
    } else {
      this.setData({
        isLoggedIn: false,
        isMember: false,
        membership: null,
        pet: null,
        makeupInfo: null,
        nickname: '',
        nicknameInput: '',
        email: '',
        emailBound: false
      });
    }
  },

  async loadData() {
    try {
      const memberRes = await app.request('/membership/status');
      this.setData({ isMember: memberRes.active, membership: memberRes });
      if (memberRes.active) {
        this.loadMemberData();
      }
      this.loadProfile();
    } catch (e) {
      if (e.statusCode === 401) app.handleAuthExpired();
    }
  },

  // ======================== 昵称编辑 ========================

  async loadProfile() {
    try {
      const profile = await app.request('/auth/profile');
      const bound = !!profile.email;
      if (this.data.showRebind) {
        // 换绑流程中：只刷新基本信息，保留换绑状态不重置
        this.setData({
          nickname: profile.nickname || '',
          nicknameInput: profile.nickname || '',
          email: profile.email || '',
          emailBound: bound,
        });
      } else {
        this.setData({
          nickname: profile.nickname || '',
          nicknameInput: profile.nickname || '',
          email: profile.email || '',
          emailBound: bound,
          showRebind: false,
          rebindEmail: '',
          emailCode: '',
          emailSent: false,
          countdown: 0,
          sendingCode: false,
          bindingEmail: false,
        });
        if (this.data._countdownTimer) {
          clearInterval(this.data._countdownTimer);
          this.data._countdownTimer = null;
        }
      }
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

  // ======================== 昵称编辑 ========================

  toggleNicknameEdit() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    const willEdit = !this.data.showNicknameEdit;
    if (willEdit) {
      this.setData({
        showNicknameEdit: true,
        nicknameInput: this.data.nickname
      });
    } else {
      this.setData({ showNicknameEdit: false });
    }
  },

  onNicknameInput(e) {
    this.setData({ nicknameInput: e.detail.value });
  },

  async handleSaveNickname() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    const name = this.data.nicknameInput.trim();
    if (!name) {
      wx.showToast({ title: '请输入昵称', icon: 'none' });
      return;
    }
    try {
      await app.request('/auth/update-profile', {
        method: 'POST',
        data: { nickname: name }
      });
      wx.showToast({ title: '昵称已更新', icon: 'success' });
      this.setData({ nickname: name, showNicknameEdit: false });
    } catch (e) {
      const msg = (e && e.data && e.data.error) || '更新失败';
      wx.showToast({ title: msg, icon: 'none' });
    }
  },

  // ======================== 邮箱绑定/换绑 ========================

  toggleRebind() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    if (this.data.showRebind) {
      // 取消换绑，回到已绑定展示状态
      if (this.data._countdownTimer) {
        clearInterval(this.data._countdownTimer);
        this.data._countdownTimer = null;
      }
      this.setData({
        showRebind: false,
        rebindEmail: '',
        emailCode: '',
        emailSent: false,
        countdown: 0,
        sendingCode: false,
        bindingEmail: false,
        emailBound: true
      });
    } else {
      // 进入换绑模式：预填当前邮箱，开始新邮箱验证流程
      this.setData({
        showRebind: true,
        rebindEmail: this.data.email,
        emailCode: '',
        emailSent: false,
        countdown: 0,
        sendingCode: false,
        bindingEmail: false,
        emailBound: false
      });
    }
  },

  onRebindEmailInput(e) {
    this.setData({ rebindEmail: e.detail.value.trim() });
  },

  onEmailInput(e) {
    this.setData({ email: e.detail.value.trim() });
  },

  onEmailCodeInput(e) {
    this.setData({ emailCode: e.detail.value });
  },

  handleSendEmailCode() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    const email = this.data.showRebind ? this.data.rebindEmail : this.data.email;
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
        this.data._countdownTimer = null;
      } else {
        this.setData({ countdown });
      }
    }, 1000);
    this.data._countdownTimer = timer;
  },

  handleBindEmail() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    const email = this.data.showRebind ? this.data.rebindEmail : this.data.email;
    const { emailCode } = this.data;
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
      if (this.data._countdownTimer) {
        clearInterval(this.data._countdownTimer);
        this.data._countdownTimer = null;
      }
      this.setData({
        email: email,
        emailBound: true,
        showRebind: false,
        rebindEmail: '',
        bindingEmail: false,
        emailCode: '',
        emailSent: false,
        countdown: 0
      });
    }).catch((err) => {
      const msg = (err && err.data && err.data.error) || '绑定失败';
      wx.showToast({ title: msg, icon: 'none' });
      this.setData({ bindingEmail: false });
    });
  },

  // ======================== 宠物操作 ========================

  async handleRename() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
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

  toggleRename() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    this.setData({ showRename: !this.data.showRename });
  },

  goToCapsule() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    wx.navigateTo({ url: '/pages/capsule/capsule' });
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  },

  onUnload() {
    if (this.data._countdownTimer) {
      clearInterval(this.data._countdownTimer);
    }
  }
});
