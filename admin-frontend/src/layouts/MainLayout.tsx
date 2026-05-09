import { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Button, Dropdown, theme, Modal, Input, App } from 'antd';
import {
  DashboardOutlined,
  UserOutlined,
  CrownOutlined,
  CheckCircleOutlined,
  TeamOutlined,
  HeartOutlined,
  HourglassOutlined,
  GithubOutlined,
  EditOutlined,
  BulbOutlined,
  SafetyOutlined,
  FileTextOutlined,
  SettingOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  KeyOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { adminLogout, changePassword } from '../services/admin';

const { Header, Sider, Content } = Layout;

const menuItems: MenuProps['items'] = [
  { key: '/', icon: <DashboardOutlined />, label: '数据看板' },
  { key: '/users', icon: <UserOutlined />, label: '用户管理' },
  { key: '/membership', icon: <CrownOutlined />, label: '会员管理' },
  { key: '/checkins', icon: <CheckCircleOutlined />, label: '打卡管理' },
  { key: '/squads', icon: <TeamOutlined />, label: '小队管理' },
  { key: '/wishes', icon: <HeartOutlined />, label: '心愿管理' },
  { key: '/capsules', icon: <HourglassOutlined />, label: '时光胶囊' },
  { key: '/pets', icon: <GithubOutlined />, label: '宠物管理' },
  { key: '/makeup-cards', icon: <EditOutlined />, label: '补签记录' },
  { key: '/insights', icon: <BulbOutlined />, label: 'AI洞察' },
  {
    key: 'system',
    icon: <SettingOutlined />,
    label: '系统管理',
    children: [
      { key: '/admins', icon: <SafetyOutlined />, label: '管理员' },
      { key: '/logs', icon: <FileTextOutlined />, label: '操作日志' },
      { key: '/config', icon: <SettingOutlined />, label: '系统配置' },
    ],
  },
];

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [openKeys, setOpenKeys] = useState<string[]>([]);
  const navigate = useNavigate();
  const location = useLocation();
  const { token: themeToken } = theme.useToken();
  const { message } = App.useApp();
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [oldPw, setOldPw] = useState('');
  const [newPw, setNewPw] = useState('');

  const adminInfo = (() => {
    try {
      return JSON.parse(localStorage.getItem('admin_info') || '{}');
    } catch {
      return {};
    }
  })();

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleLogout = async () => {
    try {
      await adminLogout();
    } catch {
      // ignore
    }
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_info');
    navigate('/login');
  };

  const handleChangePassword = async () => {
    if (!oldPw || !newPw) return;
    try {
      await changePassword(oldPw, newPw);
      message.success('密码修改成功');
      setPasswordModalOpen(false);
      setOldPw('');
      setNewPw('');
    } catch {
      // error handled by interceptor
    }
  };

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'password',
      icon: <KeyOutlined />,
      label: '修改密码',
      onClick: () => setPasswordModalOpen(true),
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  const getSelectedKey = () => {
    const path = location.pathname;
    if (path === '/') return '/';
    for (const item of menuItems || []) {
      if (item && 'key' in item && typeof item.key === 'string' && item.key !== '/' && path.startsWith(item.key)) {
        return item.key;
      }
      if (item && 'children' in item) {
        for (const child of item.children || []) {
          if (child && 'key' in child && typeof child.key === 'string' && path.startsWith(child.key)) {
            return child.key;
          }
        }
      }
    }
    return '/';
  };

  const getOpenKeys = () => {
    const path = location.pathname;
    if (['/admins', '/logs', '/config'].some(k => path.startsWith(k))) return ['system'];
    return [];
  };

  // 路由变化时同步 openKeys
  useEffect(() => {
    setOpenKeys(getOpenKeys());
  }, [location.pathname]);

  const handleOpenChange = (keys: string[]) => {
    setOpenKeys(keys);
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        style={{ background: themeToken.colorBgContainer }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
          }}
        >
          <h2
            style={{
              color: themeToken.colorPrimary,
              margin: 0,
              fontSize: collapsed ? 16 : 18,
              whiteSpace: 'nowrap',
            }}
          >
            {collapsed ? 'CK' : '打卡管理'}
          </h2>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[getSelectedKey()]}
          openKeys={openKeys}
          onOpenChange={handleOpenChange}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ borderRight: 0 }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: '0 24px',
            background: themeToken.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Button type="text" icon={<UserOutlined />}>
              {adminInfo.username || '管理员'}
            </Button>
          </Dropdown>
        </Header>
        <Content
          style={{
            margin: 24,
            padding: 24,
            background: themeToken.colorBgContainer,
            borderRadius: themeToken.borderRadiusLG,
            minHeight: 280,
            overflow: 'auto',
          }}
        >
          <Outlet />
        </Content>
      </Layout>

      <Modal
        title="修改密码"
        open={passwordModalOpen}
        onOk={handleChangePassword}
        onCancel={() => {
          setPasswordModalOpen(false);
          setOldPw('');
          setNewPw('');
        }}
        okText="确认"
        cancelText="取消"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
          <Input.Password
            placeholder="原密码"
            value={oldPw}
            onChange={(e) => setOldPw(e.target.value)}
          />
          <Input.Password
            placeholder="新密码（至少6位）"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
          />
        </div>
      </Modal>
    </Layout>
  );
}
