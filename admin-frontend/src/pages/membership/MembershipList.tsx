import { useEffect, useState } from 'react';
import { Table, Typography, Tag, Button, Modal, InputNumber, Space, message } from 'antd';
import { CrownOutlined, StopOutlined } from '@ant-design/icons';
import { getMembershipList, activateMembership, cancelMembership } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Membership {
  id: string;
  user_id: string;
  open_id: string;
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
  const [months, setMonths] = useState(1);

  useEffect(() => { loadData(); }, [page]);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await getMembershipList({ page, page_size: 20 });
      setData(res.data.memberships);
      setTotal(res.data.total);
    } catch { /* handled */ } finally { setLoading(false); }
  };

  const handleActivate = async () => {
    if (!activatingUserId) return;
    try {
      await activateMembership(activatingUserId, months);
      message.success('会员开通/续费成功');
      setModalOpen(false);
      loadData();
    } catch { /* handled */ }
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
          <a onClick={() => { setActivatingUserId(r.user_id); setMonths(1); setModalOpen(true); }}>
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
      <Table dataSource={data} columns={columns} rowKey="id" loading={loading}
        pagination={{ current: page, total, pageSize: 20, onChange: (p) => setPage(p), showTotal: (t) => `共 ${t} 条` }} />

      <Modal title="开通/续费会员" open={modalOpen} onOk={handleActivate}
        onCancel={() => setModalOpen(false)} okText="确认" cancelText="取消">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
          <div>
            <span>用户ID: </span>
            <span style={{ fontWeight: 'bold' }}>{activatingUserId}</span>
          </div>
          <div>
            <span>续费月数: </span>
            <InputNumber min={1} max={36} value={months} onChange={(v) => setMonths(v || 1)} />
          </div>
        </div>
      </Modal>
    </div>
  );
}
