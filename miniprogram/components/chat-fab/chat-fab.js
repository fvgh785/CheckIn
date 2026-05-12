Component({
  properties: {
    visible: {
      type: Boolean,
      value: true
    }
  },

  methods: {
    handleTap() {
      wx.navigateTo({ url: '/pages/chat/chat' });
    }
  }
});
