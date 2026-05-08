import { useEffect, useState } from 'react';
import { Table, Typography, Tag, Button, Modal, InputNumber, Space, message, Input, Radio } from 'antd';
import { CrownOutlined, StopOutlined } from '@ant-design/icons';
import { getMembershipList, activateMembership, activateMembershipByPhone, cancelMembership } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Membership {
  id: string;
  user_id: string;
  open_id: string;
  phone: string;
  nickname: string;
  email: string;
  level: string;
  start_date: string;
  end_date: string;
  status: number;
  is_active: boolean;
  created_at: string;
}

export default function MembershipList() {
  const [data, setData] = useState<Membership[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [activatingUserId, setActivatingUserId] = useState('');
  const [phoneInput, setPhoneInput] = useState('');
  const [months, setMonths] = useState(1);
  const [activateMode, setActivateMode] = useState<'id' | 'phone'>('id');

  useEffect(() => { loadData(); }, [page]);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await getMembershipList({ page, page_size: 20 });
      setData(res.data.memberships);
      setTotal(res.data.total);
    } catch { /* handled */ } finally { setLoading(false); }
  };

  const openActivateModal = (userId: string) => {
    setActivateMode('id');
    setActivatingUserId(userId);
    setPhoneInput('');
    setMonths(1);
    setModalOpen(true);
  };

  const openActivateByPhoneModal = () => {
    setActivateMode('phone');
    setActivatingUserId('');
    setPhoneInput('');
    setMonths(1);
    setModalOpen(true);
  };

  const handleActivate = async () => {
    if (activateMode === 'phone') {
      if (!phoneInput) {
        message.warning('请输入手机号');
        return;
      }
      try {
        await activateMembershipByPhone(phoneInput, months);
        message.success('会员开通/续费成功');
        setModalOpen(false);
        loadData();
      } catch { /* handled */ }
    } else {
      if (!activatingUserId) return;
      try {
        await activateMembership(activatingUserId, months);
        message.success('会员开通/续费成功');
        setModalOpen(false);
        loadData();
      } catch { /* handled */ }
    }
  };

  const handleCancel = async (userId: string) => {
    Modal.confirm({
      title: '确认撤销会员？',
      content: '撤销后用户将变为普通用户',
      onOk: async () => {
        await cancelMembership(userId);
        message.success('会员已撤销');
        loadData();
      },
    });
  };

  const columns = [
    { title: 'User ID', dataIndex: 'user_id', key: 'user_id', width: 120, ellipsis: true },
    { title: 'Open ID', dataIndex: 'open_id', key: 'open_id', ellipsis: true },
    { title: '手机号', dataIndex: 'phone', key: 'phone', width: 120, render: (v: string) => v || '-' },
    { title: '邮箱', dataIndex: 'email', key: 'email', width: 160, render: (v: string) => v || '-' },
    { title: '昵称', dataIndex: 'nickname', key: 'nickname', width: 100, render: (v: string) => v || '-' },
    { title: '等级', dataIndex: 'level', key: 'level', width: 80 },
    { title: '开始日期', dataIndex: 'start_date', key: 'start_date', width: 110 },
    { title: '到期日期', dataIndex: 'end_date', key: 'end_date', width: 110 },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80,
      render: (v: boolean) => v ? <Tag color="green">有效</Tag> : <Tag color="red">已过期</Tag>,
    },
    { title: '开通时间', dataIndex: 'created_at', key: 'created_at', width: 110,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD') },
    {
      title: '操作', key: 'action', width: 100,
      render: (_: unknown, r: Membership) => (
        <Space>
          <a onClick={() => openActivateModal(r.user_id)}>
            <CrownOutlined /> 续费
          </a>
          {r.is_active && (
            <a onClick={() => handleCancel(r.user_id)} style={{ color: '#ff4d4f' }}>
              <StopOutlined /> 撤销
            </a>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}>会员管理</Title>
      <Button type="primary" icon={<CrownOutlined />} onClick={openActivateByPhoneModal} style={{ marginBottom: 16 }}>
        按手机号开通会员
      </Button>
      <Table dataSource={data} columns={columns} rowKey="id" loading={loading}
        pagination={{ current: page, total, pageSize: 20, onChange: (p) => setPage(p), showTotal: (t) => `共 ${t} 条` }} />

      <Modal title={activateMode === 'phone' ? '按手机号开通会员' : '开通/续费会员'} open={modalOpen} onOk={handleActivate}
        onCancel={() => setModalOpen(false)} okText="确认" cancelText="取消">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
          <Radio.Group value={activateMode} onChange={(e) => setActivateMode(e.target.value)}>
            <Radio.Button value="id">按用户ID</Radio.Button>
            <Radio.Button value="phone">按手机号</Radio.Button>
          </Radio.Group>
          {activateMode === 'id' ? (
            <div>
              <span>用户ID: </span>
              <span style={{ fontWeight: 'bold' }}>{activatingUserId}</span>
            </div>
          ) : (
            <Input
              placeholder="请输入手机号"
              value={phoneInput}
              onChange={(e) => setPhoneInput(e.target.value)}
            />
          )}
          <div>
            <span>续费月数: </span>
            <InputNumber min={1} max={36} value={months} onChange={(v) => setMonths(v || 1)} />
          </div>
        </div>
      </Modal>
    </div>
  );
}
