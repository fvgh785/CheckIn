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
    loading: false,
    today: ''
  },

  onLoad() {
    this.setDate();
    this.checkLoginStatus();
  },

  onShow() {
    // 每次页面显示时都检查登录状态，以便处理从登录页返回后的状态更新
    this.checkLoginStatus();
  },

  setDate() {
    const now = new Date();
    const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    this.setData({ today: dateStr });
  },

  checkLoginStatus() {
    // 优先取全局 token，如果没有则去本地存储读取
    const token = app.globalData.token || wx.getStorageSync('token');

    if (token) {
      this.setData({ isLoggedIn: true });
      app.globalData.token = token; // 确保全局数据是最新的
      this.fetchStats(); // 登录后自动拉取数据
    } else {
      // 没有 token 则是未登录状态
      this.setData({ isLoggedIn: false, stats: { currentStreak: 0, maxStreak: 0, totalDays: 0 } });
    }
  },

  async fetchStats() {
    this.setData({ loading: true });
    try {
      const res = await this.request('/stats');
      this.setData({
        hasChecked: res.has_checked_today,
        stats: {
          currentStreak: res.current_streak,
          maxStreak: res.max_streak,
          totalDays: res.total_days
        }
      });
    } catch (e) {
      // 处理 Token 过期或被篡改的情况
      if (e.statusCode === 401) {
        wx.removeStorageSync('token');
        app.globalData.token = '';
        this.setData({ isLoggedIn: false, hasChecked: false });
        wx.showToast({ title: '登录已失效', icon: 'none' });
      } else {
        console.error('获取统计失败:', e);
      }
    } finally {
      this.setData({ loading: false });
    }
  },

  async handleCheckIn() {
    // 未登录则引导去登录
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
      await this.request('/checkin', { method: 'POST' });
      this.setData({ hasChecked: true });
      wx.showToast({ title: '打卡成功', icon: 'success' });
      this.fetchStats();
    } catch (e) {
      if (e.statusCode === 401) {
        wx.removeStorageSync('token');
        app.globalData.token = '';
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

  request(path, options = {}) {
    return new Promise((resolve, reject) => {
      // 确保请求带上最新的 token
      const currentToken = app.globalData.token || wx.getStorageSync('token');
      if (!currentToken) {
        reject({ statusCode: 401 });
        return;
      }

      wx.request({
        url: app.globalData.apiBase + path,
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
  }
});
