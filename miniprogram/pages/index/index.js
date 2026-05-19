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
    // 补签卡日历
    showCalendar: false,
    calYear: 0,
    calMonth: 0,
    calDays: [],
    calCanPrev: true,
    calCanNext: false,
    calMakeupRemaining: 0,
    // 心情打卡
    moodList: [
      { key: 'happy', emoji: '😊', label: '开心', color: '#FCD34D', bgColor: '#FEF3C7' },
      { key: 'calm', emoji: '😌', label: '平静', color: '#81D8D0', bgColor: '#D4F1F0' },
      { key: 'down', emoji: '😔', label: '低落', color: '#A5B4FC', bgColor: '#E0E7FF' },
      { key: 'annoyed', emoji: '😤', label: '烦躁', color: '#FCA5A5', bgColor: '#FEE2E2' },
      { key: 'tired', emoji: '😴', label: '疲惫', color: '#D1D5DB', bgColor: '#F3F4F6' }
    ],
    selectedMood: 'calm',
    showMoodNote: false,
    moodNote: ''
  },

  onLoad() {
    this.setDate();
    this.checkLoginStatus();
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: '/pages/index/index' });
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
      app.globalData.isMember = res.active;
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
      const res = await app.request('/checkin', {
        method: 'POST',
        data: {
          mood: this.data.selectedMood,
          mood_note: this.data.moodNote || ''
        }
      });
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

  // ======================== 心情打卡 ========================

  selectMood(e) {
    const key = e.currentTarget.dataset.key;
    this.setData({ selectedMood: key });
  },

  toggleMoodNote() {
    this.setData({ showMoodNote: !this.data.showMoodNote });
  },

  onMoodNoteInput(e) {
    this.setData({ moodNote: e.detail.value });
  },

  // ======================== 补签卡日历 ========================

  openCalendar() {
    const now = new Date();
    this.setData({
      showCalendar: true,
      calYear: now.getFullYear(),
      calMonth: now.getMonth() + 1
    });
    this.fetchCalendarData();
  },

  closeCalendar() {
    this.setData({ showCalendar: false });
  },

  noop() {},

  async fetchCalendarData() {
    const { calYear, calMonth } = this.data;
    try {
      const res = await app.request(`/checkin/makeup/calendar?year=${calYear}&month=${calMonth}`);
      this.buildCalendarDays(res);
    } catch (e) {
      console.error('获取日历数据失败:', e);
    }
  },

  buildCalendarDays(data) {
    const { year, month, checked_dates, makeup_dates, makeup_info, mood_map } = data;
    const checkedSet = new Set(checked_dates);
    const makeupSet = new Set(makeup_dates);

    const now = new Date();
    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const todayDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    // 当月第一天是星期几（0=周日）
    const firstDay = new Date(year, month - 1, 1);
    const startWeekDay = firstDay.getDay();

    // 当月总天数
    const daysInMonth = new Date(year, month, 0).getDate();

    // 当前月份是否可前进（不能超过当月）
    const currentMonth = new Date(now.getFullYear(), now.getMonth(), 1);
    const viewMonth = new Date(year, month - 1, 1);
    const canNext = viewMonth < currentMonth;
    const canPrev = true; // 总是可以往前翻

    const days = [];

    // 填充前置空白
    for (let i = 0; i < startWeekDay; i++) {
      days.push({ date: `pad-${i}`, day: '', cls: 'cal-day-pad', isChecked: false, isMakeup: false, canTap: false });
    }

    // 填充当月日期
    for (let d = 1; d <= daysInMonth; d++) {
      const m = String(month).padStart(2, '0');
      const dd = String(d).padStart(2, '0');
      const dateStr = `${year}-${m}-${dd}`;
      const cellDate = new Date(year, month - 1, d);
      const isToday = dateStr === todayStr;
      const isFuture = cellDate > todayDate;
      const isChecked = checkedSet.has(dateStr);
      const isMakeup = makeupSet.has(dateStr);
      const mood = mood_map[dateStr] || null;
      const remaining = makeup_info ? makeup_info.remaining : 0;
      // 可补签条件：过去的日期 + 未打卡 + 还有补签卡剩余
      const isAvailable = !isFuture && !isToday && !isChecked && remaining > 0;

      let cls = 'cal-day-normal';
      if (isToday) cls += ' cal-day-today';
      if (isChecked && !isMakeup) cls += ' cal-day-checked';
      else if (isMakeup) cls += ' cal-day-makeup';
      else if (isAvailable) cls += ' cal-day-available';
      else if (isFuture) cls += ' cal-day-future';

      // 心情热力图：已打卡日期叠加心情颜色类
      let moodCls = '';
      if (isChecked && mood) {
        moodCls = `cal-mood-${mood}`;
      }

      days.push({
        date: dateStr,
        day: d,
        cls,
        moodCls,
        isChecked,
        isMakeup,
        isAvailable,
        canTap: isAvailable,
        mood
      });
    }

    this.setData({
      calDays: days,
      calCanPrev: canPrev,
      calCanNext: canNext,
      calMakeupRemaining: makeup_info ? makeup_info.remaining : 0
    });
  },

  calPrevMonth() {
    let { calYear, calMonth } = this.data;
    if (calMonth === 1) {
      calYear -= 1;
      calMonth = 12;
    } else {
      calMonth -= 1;
    }
    this.setData({ calYear, calMonth });
    this.fetchCalendarData();
  },

  calNextMonth() {
    if (!this.data.calCanNext) return;
    let { calYear, calMonth } = this.data;
    if (calMonth === 12) {
      calYear += 1;
      calMonth = 1;
    } else {
      calMonth += 1;
    }
    this.setData({ calYear, calMonth });
    this.fetchCalendarData();
  },

  async calTapDay(e) {
    const targetDate = e.currentTarget.dataset.date;
    if (!targetDate) return;

    wx.showModal({
      title: '使用补签卡',
      content: `确认对 ${targetDate} 使用一张补签卡吗？`,
      success: async (res) => {
        if (!res.confirm) return;
        this.setData({ loading: true });
        try {
          await app.request('/checkin/makeup', {
            method: 'POST',
            data: { date: targetDate }
          });
          wx.showToast({ title: `已补签 ${targetDate}`, icon: 'success' });
          // 刷新数据
          this.fetchMakeupInfo();
          this.fetchStats();
          // 刷新日历
          this.fetchCalendarData();
        } catch (err) {
          const msg = (err && err.data && err.data.error) || (err && err.data && err.data.message) || '补签失败';
          wx.showToast({ title: msg, icon: 'none' });
        } finally {
          this.setData({ loading: false });
        }
      }
    });
  }
});
