import api from './api';

// ======================== 登录认证 ========================
export const adminLogin = (username: string, password: string) =>
  api.post('/login', { username, password });

export const adminLogout = () => api.post('/logout');

export const getAdminMe = () => api.get('/me');

export const changePassword = (old_password: string, new_password: string) =>
  api.put('/password', { old_password, new_password });

// ======================== 数据看板 ========================
export const getDashboard = () => api.get('/dashboard');

// ======================== 用户管理 ========================
export const getUserList = (params: { page?: number; page_size?: number; keyword?: string }) =>
  api.get('/users', { params });

export const getUserDetail = (userId: string) => api.get(`/users/${userId}`);

// ======================== 会员管理 ========================
export const getMembershipList = (params: { page?: number; page_size?: number }) =>
  api.get('/memberships', { params });

export const activateMembership = (userId: string, months: number) =>
  api.post('/membership/activate', { user_id: userId, months });

export const activateMembershipByPhone = (phone: string, months: number) =>
  api.post('/membership/activate', { phone, months });

export const lookupUserByPhone = (phone: string) =>
  api.get('/users/lookup', { params: { phone } });

export const getMembershipStatus = (userId: string) =>
  api.get(`/membership/status/${userId}`);

export const cancelMembership = (userId: string) =>
  api.post('/membership/cancel', { user_id: userId });

// ======================== 打卡管理 ========================
export const getCheckinList = (params: {
  page?: number;
  page_size?: number;
  user_id?: string;
  date_from?: string;
  date_to?: string;
}) => api.get('/checkins', { params });

export const addCheckin = (userId: string, checkDate: string) =>
  api.post('/checkin/add', { user_id: userId, check_date: checkDate });

export const deleteCheckin = (checkinId: string) => api.delete(`/checkin/${checkinId}`);

// ======================== 小队管理 ========================
export const getSquadList = (params: { page?: number; page_size?: number }) =>
  api.get('/squads', { params });

export const deleteSquad = (squadId: string) => api.delete(`/squads/${squadId}`);

// ======================== 心愿管理 ========================
export const getWishList = (params: { page?: number; page_size?: number }) =>
  api.get('/wishes', { params });

export const deleteWish = (wishId: string) => api.delete(`/wishes/${wishId}`);

// ======================== 时光胶囊管理 ========================
export const getCapsuleList = (params: { page?: number; page_size?: number }) =>
  api.get('/capsules', { params });

export const deleteCapsule = (capsuleId: string) => api.delete(`/capsules/${capsuleId}`);

// ======================== 宠物管理 ========================
export const getPetList = (params: { page?: number; page_size?: number }) =>
  api.get('/pets', { params });

export const updatePet = (petId: string, data: Record<string, unknown>) =>
  api.put(`/pets/${petId}`, data);

// ======================== 补签卡管理 ========================
export const getMakeupCardList = (params: { page?: number; page_size?: number }) =>
  api.get('/makeup-cards', { params });

// ======================== AI洞察管理 ========================
export const getInsightList = (params: { page?: number; page_size?: number }) =>
  api.get('/insights', { params });

// ======================== 管理员管理（超管专用） ========================
export const getAdminList = (params: { page?: number; page_size?: number }) =>
  api.get('/admins', { params });

export const createAdmin = (username: string, password: string, role: string) =>
  api.post('/admins', { username, password, role });

export const updateAdmin = (adminId: string, data: Record<string, unknown>) =>
  api.put(`/admins/${adminId}`, data);

export const deleteAdmin = (adminId: string) => api.delete(`/admins/${adminId}`);

// ======================== 操作日志 ========================
export const getLogList = (params: {
  page?: number;
  page_size?: number;
  admin_id?: string;
  action?: string;
  target_type?: string;
}) => api.get('/logs', { params });

// ======================== 系统配置 ========================
export const getConfig = () => api.get('/config');

export const updateConfig = (data: Record<string, unknown>) => api.put('/config', data);
