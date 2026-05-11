const app = getApp();

Page({
  data: {
    hasChecked: false,
    stats: {
      currentStreak: 0,
      maxStreak: 0,
      totalDays: 0
    },
    isLoggedIn: false,
    isMember: false,
    loading: false,
    today: '',
    // 宠物数据
    pet: null,
    // 补签卡
    makeupInfo: null,
    makeupDate: '',
    makeupStartDate: '',
    makeupEndDate: ''
  },

  onLoad() {
    this.setDate();
    this.checkLoginStatus();
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 });
    }
    this.checkLoginStatus();
  },

  setDate() {
    const now = new Date();
    const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    this.setData({ today: dateStr });
  },

  checkLoginStatus() {
    const token = app.globalData.token || wx.getStorageSync('token');
    if (token) {
      this.setData({ isLoggedIn: true });
      app.globalData.token = token;
      this.fetchAllData();
    } else {
      this.setData({
        isLoggedIn: false,
        isMember: false,
        pet: null,
        makeupInfo: null,
        stats: { currentStreak: 0, maxStreak: 0, totalDays: 0 }
      });
    }
  },

  async fetchAllData() {
    this.setData({ loading: true });
    try {
      await Promise.all([
        this.fetchStats(),
        this.fetchMembershipStatus()
      ]);
    } finally {
      this.setData({ loading: false });
    }
  },

  async fetchStats() {
    try {
      const res = await app.request('/stats');
      this.setData({
        hasChecked: res.has_checked_today,
        stats: {
          currentStreak: res.current_streak,
          maxStreak: res.max_streak,
          totalDays: res.total_days
        }
      });
    } catch (e) {
      if (e.statusCode === 401) {
        app.handleAuthExpired();
        this.setData({ isLoggedIn: false, hasChecked: false, isMember: false });
      } else {
        console.error('获取统计失败:', e);
      }
    }
  },

  async fetchMembershipStatus() {
    try {
      const res = await app.request('/membership/status');
      this.setData({ isMember: res.active });
      if (res.active) {
        // 获取宠物数据
        this.fetchPet();
        // 获取补签卡信息
        this.fetchMakeupInfo();
      }
    } catch (e) {
      if (e.statusCode !== 401) {
        console.error('获取会员状态失败:', e);
      }
    }
  },

  async fetchPet() {
    try {
      const res = await app.request('/membership/pet');
      this.setData({ pet: res });
    } catch (e) {
      // 404/403 表示会员未开通或宠物尚未初始化，静默处理
      if (e.statusCode !== 404 && e.statusCode !== 403) {
        console.error('获取宠物失败:', e);
      }
      this.setData({ pet: null });
    }
  },

  async fetchMakeupInfo() {
    try {
      const res = await app.request('/checkin/makeup/info');
      // 计算可选日期范围：当月1号 ~ 昨天
      const now = new Date();
      const monthStart = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
      const yesterday = new Date(now.getTime() - 86400000);
      const yesterdayStr = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`;
      this.setData({
        makeupInfo: res,
        makeupStartDate: monthStart,
        makeupEndDate: yesterdayStr
      });
    } catch (e) {
      console.error('获取补签卡信息失败:', e);
    }
  },

  async handleCheckIn() {
    if (!this.data.isLoggedIn) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }

    if (this.data.hasChecked) {
      wx.showToast({ title: '今日已打卡', icon: 'none' });
      return;
    }

    this.setData({ loading: true });

    try {
      const res = await app.request('/checkin', { method: 'POST' });
      this.setData({ hasChecked: true });

      // 处理宠物反馈
      if (res.pet) {
        const petResult = res.pet;
        if (petResult.already_fed) {
          wx.showToast({ title: '今日已投喂', icon: 'none' });
        } else {
          let title = '打卡成功！宠物+心情';
          if (petResult.level_up) {
            title = `🎉 宠物进化成${petResult.stage_name}了！`;
          }
          wx.showToast({ title, icon: 'success' });
          // 刷新宠物状态
          this.fetchPet();
        }
      } else {
        wx.showToast({ title: '打卡成功', icon: 'success' });
      }

      this.fetchStats();
      if (this.data.isMember) {
        this.fetchMakeupInfo();
      }
    } catch (e) {
      if (e.statusCode === 401) {
        app.handleAuthExpired();
        this.setData({ isLoggedIn: false, hasChecked: false });
      } else if (e.statusCode === 409) {
        this.setData({ hasChecked: true });
        wx.showToast({ title: '今日已打卡', icon: 'none' });
      } else {
        wx.showToast({ title: '打卡失败', icon: 'error' });
      }
    } finally {
      this.setData({ loading: false });
    }
  },

  handleGoMembership() {
    wx.switchTab({ url: '/pages/profile/profile' });
  },

  // ======================== 补签卡 ========================

  async handleMakeupDateChange(e) {
    const targetDate = e.detail.value;
    if (!targetDate) return;

    this.setData({ loading: true });
    try {
      const res = await app.request('/checkin/makeup', {
        method: 'POST',
        data: { date: targetDate }
      });
      wx.showToast({ title: `已补签 ${targetDate}`, icon: 'success' });
      // 刷新补签卡信息和打卡统计
      this.fetchMakeupInfo();
      this.fetchStats();
    } catch (e) {
      const msg = (e && e.data && e.data.error) || (e && e.data && e.data.message) || '补签失败';
      wx.showToast({ title: msg, icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  }
});
