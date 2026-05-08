import { useEffect, useState } from 'react';
import { Table, Typography, Button, Modal, Tag, message } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import { getCapsuleList, deleteCapsule } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Capsule { id: string; user_id: string; open_id: string; content: string; target_streak: number; created_streak: number; status: number; status_text: string; created_at: string; opened_at: string | null; }

export default function CapsuleList() {
  const [data, setData] = useState<Capsule[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => { loadData(); }, [page]);

  const loadData = async () => {
    setLoading(true);
    try { const res = await getCapsuleList({ page, page_size: 20 }); setData(res.data.capsules); setTotal(res.data.total); }
    catch { /* handled */ } finally { setLoading(false); }
  };

  const handleDelete = (id: string) => {
    Modal.confirm({ title: '确认删除该胶囊？', onOk: async () => { await deleteCapsule(id); message.success('已删除'); loadData(); } });
  };

  const columns = [
    { title: 'User ID', dataIndex: 'user_id', key: 'user_id', width: 120, ellipsis: true },
    { title: 'Open ID', dataIndex: 'open_id', key: 'open_id', ellipsis: true },
    { title: '内容预览', dataIndex: 'content', key: 'content', ellipsis: true },
    { title: '目标/已打卡', key: 'streak', width: 100, render: (_: unknown, r: Capsule) => `${r.target_streak}/${r.created_streak}天` },
    { title: '状态', dataIndex: 'status_text', key: 'status_text', width: 80, render: (v: string) => v === '已开启' ? <Tag color="green">{v}</Tag> : <Tag color="orange">{v}</Tag> },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 110, render: (v: string) => dayjs(v).format('YYYY-MM-DD') },
    { title: '操作', key: 'action', width: 80, render: (_: unknown, r: Capsule) => <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)}>删除</Button> },
  ];

  return (
    <div>
      <Title level={4}>时光胶囊管理</Title>
      <Table dataSource={data} columns={columns} rowKey="id" loading={loading}
        pagination={{ current: page, total, pageSize: 20, onChange: (p) => setPage(p), showTotal: (t) => `共 ${t} 条` }} />
    </div>
  );
}
