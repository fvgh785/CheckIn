import { useEffect, useState } from 'react';
import { Table, Typography, Button, Modal, Input, Select, Tag, message } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { getAdminList, createAdmin, updateAdmin, deleteAdmin } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Admin { id: string; username: string; role: string; status: number; created_at: string; }

export default function AdminList() {
  const [data, setData] = useState<Admin[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingAdmin, setEditingAdmin] = useState<Admin | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('admin');

  useEffect(() => { loadData(); }, [page]);

  const loadData = async () => {
    setLoading(true);
    try { const res = await getAdminList({ page, page_size: 20 }); setData(res.data.admins); setTotal(res.data.total); }
    catch { /* handled */ } finally { setLoading(false); }
  };

  const openCreate = () => { setEditingAdmin(null); setUsername(''); setPassword(''); setRole('admin'); setModalOpen(true); };
  const openEdit = (a: Admin) => { setEditingAdmin(a); setUsername(a.username); setPassword(''); setRole(a.role); setModalOpen(true); };

  const handleSubmit = async () => {
    try {
      if (editingAdmin) {
        await updateAdmin(editingAdmin.id, { username, ...(password ? { password } : {}), role });
        message.success('更新成功');
      } else {
        await createAdmin(username, password, role);
        message.success('创建成功');
      }
      setModalOpen(false); loadData();
    } catch { /* handled */ }
  };

  const handleDelete = (id: string) => {
    Modal.confirm({ title: '确认删除该管理员？', onOk: async () => { await deleteAdmin(id); message.success('已删除'); loadData(); } });
  };

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '角色', dataIndex: 'role', key: 'role', render: (v: string) => v === 'super_admin' ? <Tag color="red">超级管理员</Tag> : <Tag color="blue">管理员</Tag> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (v: number) => v === 1 ? <Tag color="green">启用</Tag> : <Tag color="red">禁用</Tag> },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm') },
    { title: '操作', key: 'action', width: 150, render: (_: unknown, r: Admin) => (
      <>
        <Button type="link" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button>
        <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)}>删除</Button>
      </>
    )},
  ];

  return (
    <div>
      <Title level={4}>管理员管理</Title>
      <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} style={{ marginBottom: 16 }}>新增管理员</Button>
      <Table dataSource={data} columns={columns} rowKey="id" loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={{ current: page, total, pageSize: 20, onChange: (p) => setPage(p), showTotal: (t) => `共 ${t} 位` }} />

      <Modal title={editingAdmin ? '编辑管理员' : '新增管理员'} open={modalOpen} onOk={handleSubmit}
        onCancel={() => setModalOpen(false)} okText="确认" cancelText="取消">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
          <Input placeholder="用户名" value={username} onChange={(e) => setUsername(e.target.value)} />
          <Input.Password placeholder={editingAdmin ? '留空则不修改密码' : '密码（至少6位）'} value={password} onChange={(e) => setPassword(e.target.value)} />
          <Select value={role} onChange={(v) => setRole(v)} options={[{ label: '管理员', value: 'admin' }, { label: '超级管理员', value: 'super_admin' }]} />
        </div>
      </Modal>
    </div>
  );
}
