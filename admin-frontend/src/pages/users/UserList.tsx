import { useEffect, useState } from 'react';
import { Table, Input, Typography, Tag, Space, Button, Modal, InputNumber, message } from 'antd';
import { SearchOutlined, EyeOutlined, CrownOutlined, DeleteOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getUserList, activateMembership, deleteUser } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface User {
  user_id: string;
  open_id: string;
  phone: string;
  nickname: string;
  email: string;
  created_at: string;
  total_checkins: number;
  is_member: boolean;
}

export default function UserList() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const [activateModalOpen, setActivateModalOpen] = useState(false);
  const [activatingUserId, setActivatingUserId] = useState('');
  const [months, setMonths] = useState(1);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deletingUser, setDeletingUser] = useState<User | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadUsers();
  }, [page, keyword]);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const res = await getUserList({ page, page_size: 20, keyword });
      setUsers(res.data.users);
      setTotal(res.data.total);
    } catch {
      // handled
    } finally {
      setLoading(false);
    }
  };

  const handleActivateMember = async () => {
    try {
      await activateMembership(activatingUserId, months);
      message.success('会员开通成功');
      setActivateModalOpen(false);
      loadUsers();
    } catch { /* handled */ }
  };

  const handleDeleteUser = async () => {
    if (!deletingUser) return;
    try {
      await deleteUser(deletingUser.user_id);
      message.success('用户已删除');
      setDeleteModalOpen(false);
      setDeletingUser(null);
      loadUsers();
    } catch { /* handled */ }
  };

  const columns = [
    { title: 'User ID', dataIndex: 'user_id', key: 'user_id', width: 180, ellipsis: true },
    { title: 'Open ID', dataIndex: 'open_id', key: 'open_id', width: 160, ellipsis: true },
    { title: '手机号', dataIndex: 'phone', key: 'phone', width: 130, render: (v: string) => v || '-' },
    { title: '邮箱', dataIndex: 'email', key: 'email', width: 180, render: (v: string) => v || '-' },
    { title: '昵称', dataIndex: 'nickname', key: 'nickname', width: 110, render: (v: string) => v || '-' },
    { title: '注册时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm') },
    { title: '累计打卡', dataIndex: 'total_checkins', key: 'total_checkins', width: 90 },
    {
      title: '会员', dataIndex: 'is_member', key: 'is_member', width: 80,
      render: (v: boolean) => v ? <Tag color="gold">会员</Tag> : <Tag>普通</Tag>,
    },
    {
      title: '操作', key: 'action', width: 170,
      render: (_: unknown, record: User) => (
        <Space>
          <a onClick={() => navigate(`/users/${record.user_id}`)}><EyeOutlined /> 详情</a>
          {!record.is_member && (
            <a onClick={() => { setActivatingUserId(record.user_id); setMonths(1); setActivateModalOpen(true); }}>
              <CrownOutlined /> 开通会员
            </a>
          )}
          <a style={{ color: '#ff4d4f' }} onClick={() => { setDeletingUser(record); setDeleteModalOpen(true); }}>
            <DeleteOutlined /> 删除
          </a>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}>用户管理</Title>
      <Input
        placeholder="搜索 Open ID / 手机号 / 昵称 / 邮箱..."
        prefix={<SearchOutlined />}
        value={keyword}
        onChange={(e) => { setKeyword(e.target.value); setPage(1); }}
        style={{ width: 300, marginBottom: 16 }}
        allowClear
      />
      <Table
        dataSource={users}
        columns={columns}
        rowKey="user_id"
        loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          onChange: (p) => setPage(p),
          showTotal: (t) => `共 ${t} 条`,
        }}
      />

      <Modal title="开通会员" open={activateModalOpen} onOk={handleActivateMember}
        onCancel={() => setActivateModalOpen(false)} okText="确认" cancelText="取消">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
          <div>
            <span>用户ID: </span>
            <span style={{ fontWeight: 'bold' }}>{activatingUserId}</span>
          </div>
          <div>
            <span>开通月数: </span>
            <InputNumber min={1} max={36} value={months} onChange={(v) => setMonths(v || 1)} />
          </div>
        </div>
      </Modal>

      <Modal
        title={<span><ExclamationCircleOutlined style={{ color: '#faad14', marginRight: 8 }} />确认删除用户</span>}
        open={deleteModalOpen}
        onOk={handleDeleteUser}
        onCancel={() => { setDeleteModalOpen(false); setDeletingUser(null); }}
        okText="确认删除"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <p>确定要删除该用户及所有关联数据吗？此操作不可撤销。</p>
        {deletingUser && (
          <div style={{ marginTop: 12, padding: 12, background: '#fff7e6', borderRadius: 8 }}>
            <p><strong>用户ID:</strong> {deletingUser.user_id}</p>
            <p><strong>昵称:</strong> {deletingUser.nickname || '-'}</p>
            <p><strong>手机号:</strong> {deletingUser.phone || '-'}</p>
            <p><strong>邮箱:</strong> {deletingUser.email || '-'}</p>
          </div>
        )}
      </Modal>
    </div>
  );
}
