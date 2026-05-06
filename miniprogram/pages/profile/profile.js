const app = getApp();

Page({
  data: {
    isMember: false,
    membership: null,
    pet: null,
    makeupInfo: null,
    petName: '',
    showRename: false
  },

  onShow() {
    this.loadData();
  },

  async loadData() {
    try {
      const memberRes = await app.request('/membership/status');
      this.setData({ isMember: memberRes.active, membership: memberRes });
      if (memberRes.active) {
        this.loadMemberData();
      }
    } catch (e) {
      if (e.statusCode === 401) app.handleAuthExpired();
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
  }
});
