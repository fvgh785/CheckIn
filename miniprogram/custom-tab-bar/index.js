Component({
  data: {
    selected: '/pages/index/index',
    visible: false,
    allTabs: [
      {
        id: '/pages/index/index',
        pagePath: '/pages/index/index',
        text: '首页',
        iconPath: '/images/tab_home.png',
        selectedIconPath: '/images/tab_home_active.png'
      },
      {
        id: '/pages/squad/squad',
        pagePath: '/pages/squad/squad',
        text: '小队',
        iconPath: '/images/tab_squad.png',
        selectedIconPath: '/images/tab_squad_active.png'
      },
      {
        id: '/pages/insight/insight',
        pagePath: '/pages/insight/insight',
        text: '周报',
        iconPath: '/images/tab_ai.png',
        selectedIconPath: '/images/tab_ai_active.png'
      },
      {
        id: '/pages/wish/wish',
        pagePath: '/pages/wish/wish',
        text: '心愿',
        iconPath: '/images/tab_wish.png',
        selectedIconPath: '/images/tab_wish_active.png'
      },
      {
        id: '/pages/profile/profile',
        pagePath: '/pages/profile/profile',
        text: '我的',
        iconPath: '/images/tab_profile.png',
        selectedIconPath: '/images/tab_profile_active.png'
      }
    ],
    list: []
  },

  observers: {
    'selected': function () {
      this._updateList();
    }
  },

  lifetimes: {
    attached() {
      this._destroyed = false;
      this._updateList();
    },
    detached() {
      this._destroyed = true;
    }
  },

  methods: {
    _pending: false,
    _switchLocked: false,

    _updateList() {
      if (this._pending || this._destroyed) return;
      this._pending = true;
      const app = getApp();
      app.syncLoginStatus();
      const token = app.globalData.token || wx.getStorageSync('token');
      if (!token) {
        if (!this._destroyed) {
          this.setData({ visible: false, list: [] });
        }
        this._pending = false;
        return;
      }
      if (!this._destroyed) {
        this.setData({ visible: true });
      }
      wx.request({
        url: app.globalData.apiBase + '/membership/status',
        header: { 'Authorization': 'Bearer ' + token },
        success: (res) => {
          if (this._destroyed) return;
          const active = res.data && res.data.active;
          app.globalData.isMember = active;
          this._applyList(active);
        },
        fail: () => {
          if (this._destroyed) return;
          this._applyList(app.globalData.isMember || false);
        },
        complete: () => {
          this._pending = false;
        }
      });
    },

    _applyList(isMember) {
      if (this._destroyed) return;
      this.setData({
        list: this.data.allTabs.filter(t => isMember || t.id !== '/pages/insight/insight')
      });
    },

    switchTab(e) {
      if (this._switchLocked) return;
      const path = e.currentTarget.dataset.path;
      if (path === this.data.selected) return;
      this._switchLocked = true;
      try {
        wx.switchTab({ url: path });
      } catch (err) {
        console.error('switchTab error:', err);
      }
      setTimeout(() => { this._switchLocked = false; }, 500);
    }
  }
});
