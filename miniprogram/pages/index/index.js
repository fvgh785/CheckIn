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
    makeupInfo: null
  },

  onLoad() {
    this.setDate();
    this.checkLoginStatus();
  },

  onShow() {
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
      console.error('获取宠物失败:', e);
    }
  },

  async fetchMakeupInfo() {
    try {
      const res = await app.request('/checkin/makeup/info');
      this.setData({ makeupInfo: res });
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
  }
});
