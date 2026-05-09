import axios from 'axios';
import { message } from 'antd';

const api = axios.create({
  baseURL: '/api/admin',
  timeout: 15000,
});

// 请求拦截器：自动添加 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：统一处理错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const { status, data } = error.response;
      if (status === 401) {
        localStorage.removeItem('admin_token');
        localStorage.removeItem('admin_info');
        // 仅在非登录页时跳转
        if (window.location.pathname !== '/login') {
          message.error('登录已过期，请重新登录');
          window.location.href = '/login';
        }
      } else if (status === 403) {
        message.error(data?.error || '无权限执行此操作');
      } else {
        message.error(data?.error || data?.message || '请求失败');
      }
    }
    return Promise.reject(error);
  }
);

export default api;
