import { useEffect, useState } from 'react';
import { Table, Typography, Button, Modal, DatePicker, Space, message, Input } from 'antd';
import { PlusOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons';
import { getCheckinList, addCheckin, deleteCheckin } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Checkin {
  id: string;
  user_id: string;
  open_id: string;
  check_date: string;
  created_at: string;
}

export default function CheckinList() {
  const [data, setData] = useState<Checkin[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterUserId, setFilterUserId] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [addUserId, setAddUserId] = useState('');
  const [addDate, setAddDate] = useState<string>('');

  useEffect(() => { loadData(); }, [page]);

  const loadData = async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: 20 };
      if (filterUserId) params.user_id = filterUserId;
      if (filterDateFrom) params.date_from = filterDateFrom;
      if (filterDateTo) params.date_to = filterDateTo;
      const res = await getCheckinList(params);
      setData(res.data.checkins);
      setTotal(res.data.total);
    } catch { /* handled */ } finally { setLoading(false); }
  };

  const handleAdd = async () => {
    if (!addUserId || !addDate) return;
    try {
      await addCheckin(addUserId, addDate);
      message.success('打卡添加成功');
      setAddModalOpen(false);
      setAddUserId('');
      setAddDate('');
      loadData();
    } catch { /* handled */ }
  };

  const handleDelete = (id: string) => {
    Modal.confirm({
      title: '确认删除该打卡记录？',
      onOk: async () => {
        await deleteCheckin(id);
        message.success('已删除');
        loadData();
      },
    });
  };

  const columns = [
    { title: 'User ID', dataIndex: 'user_id', key: 'user_id', width: 180, ellipsis: true },
    { title: 'Open ID', dataIndex: 'open_id', key: 'open_id', width: 160, ellipsis: true },
    { title: '打卡日期', dataIndex: 'check_date', key: 'check_date', width: 120 },
    { title: '打卡时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss') },
    {
      title: '操作', key: 'action', width: 80,
      render: (_: unknown, r: Checkin) => (
        <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)}>删除</Button>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}>打卡管理</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input placeholder="User ID" value={filterUserId}
          onChange={(e) => setFilterUserId(e.target.value)} style={{ width: 200 }} prefix={<SearchOutlined />} />
        <DatePicker placeholder="开始日期" onChange={(d) => setFilterDateFrom(d ? d.format('YYYY-MM-DD') : '')} />
        <DatePicker placeholder="结束日期" onChange={(d) => setFilterDateTo(d ? d.format('YYYY-MM-DD') : '')} />
        <Button type="primary" onClick={loadData}>搜索</Button>
        <Button icon={<PlusOutlined />} onClick={() => setAddModalOpen(true)}>手动添加打卡</Button>
      </Space>
      <Table dataSource={data} columns={columns} rowKey="id" loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={{ current: page, total, pageSize: 20, onChange: (p) => setPage(p), showTotal: (t) => `共 ${t} 条` }} />

      <Modal title="手动添加打卡" open={addModalOpen} onOk={handleAdd}
        onCancel={() => { setAddModalOpen(false); setAddUserId(''); setAddDate(''); }}
        okText="确认" cancelText="取消">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
          <Input placeholder="用户ID" value={addUserId} onChange={(e) => setAddUserId(e.target.value)} />
          <DatePicker placeholder="选择打卡日期" onChange={(d) => setAddDate(d ? d.format('YYYY-MM-DD') : '')} style={{ width: '100%' }} />
        </div>
      </Modal>
    </div>
  );
}
