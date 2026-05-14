Component({
  data: {
    selected: 0,
    list: [
      {
        pagePath: '/pages/index/index',
        text: '首页',
        iconPath: '/images/tab_home.png',
        selectedIconPath: '/images/tab_home_active.png'
      },
      {
        pagePath: '/pages/squad/squad',
        text: '小队',
        iconPath: '/images/tab_squad.png',
        selectedIconPath: '/images/tab_squad_active.png'
      },
      {
        pagePath: '/pages/insight/insight',
        text: '周报',
        iconPath: '/images/tab_ai.png',
        selectedIconPath: '/images/tab_ai_active.png'
      },
      {
        pagePath: '/pages/wish/wish',
        text: '心愿',
        iconPath: '/images/tab_wish.png',
        selectedIconPath: '/images/tab_wish_active.png'
      },
      {
        pagePath: '/pages/profile/profile',
        text: '我的',
        iconPath: '/images/tab_profile.png',
        selectedIconPath: '/images/tab_profile_active.png'
      }
    ]
  },

  methods: {
    switchTab(e) {
      const data = e.currentTarget.dataset;
      const url = data.path;
      wx.switchTab({ url });
    }
  }
});
