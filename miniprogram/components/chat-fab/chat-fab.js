Component({
  properties: {
    visible: {
      type: Boolean,
      value: true
    }
  },

  data: {
    x: 0,
    y: 0,
    _startX: 0,
    _startY: 0
  },

  lifetimes: {
    attached() {
      this._initPosition();
    }
  },

  pageLifetimes: {
    show() {
      // 页面显示时重新计算位置，适配屏幕旋转等场景
      this._initPosition();
    }
  },

  methods: {
    /** 根据屏幕尺寸计算初始位置（右下角） */
    _initPosition() {
      const sys = wx.getSystemInfoSync();
      const rpxRatio = sys.windowWidth / 750;
      const fabSize = 100 * rpxRatio;  // 100rpx 转 px
      // 距离右边缘 32rpx，距离底部 160rpx
      const x = sys.windowWidth - 32 * rpxRatio - fabSize;
      const y = sys.windowHeight - 160 * rpxRatio - fabSize;
      this.setData({ x, y });
    },

    /** 记录触摸起始位置 */
    onTouchStart(e) {
      this.data._startX = e.touches[0].pageX;
      this.data._startY = e.touches[0].pageY;
    },

    /** 触摸结束时判断是点击还是拖动 */
    onTouchEnd(e) {
      const endX = e.changedTouches[0].pageX;
      const endY = e.changedTouches[0].pageY;
      const dx = Math.abs(endX - this.data._startX);
      const dy = Math.abs(endY - this.data._startY);

      // 移动距离小于 5px 视为点击
      if (dx < 5 && dy < 5) {
        wx.navigateTo({ url: '/pages/chat/chat' });
      }
    },

    /** 拖动结束后记录新位置，防止下次初始位置弹回 */
    onChange(e) {
      this.data.x = e.detail.x;
      this.data.y = e.detail.y;
    }
  }
});
