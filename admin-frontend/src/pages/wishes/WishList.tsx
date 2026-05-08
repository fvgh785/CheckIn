import { useEffect, useState } from 'react';
import { Table, Typography, Button, Modal, Tag, message } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import { getWishList, deleteWish } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Wish { id: string; user_id: string; open_id: string; content: string; target_days: number; current_days: number; status: number; created_at: string; achieved_at: string | null; }

export default function WishList() {
  const [data, setData] = useState<Wish[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => { loadData(); }, [page]);

  const loadData = async () => {
    setLoading(true);
    try { const res = await getWishList({ page, page_size: 20 }); setData(res.data.wishes); setTotal(res.data.total); }
    catch { /* handled */ } finally { setLoading(false); }
  };

  const handleDelete = (id: string) => {
    Modal.confirm({ title: '确认删除该心愿？', onOk: async () => { await deleteWish(id); message.success('已删除'); loadData(); } });
  };

  const columns = [
    { title: 'User ID', dataIndex: 'user_id', key: 'user_id', width: 120, ellipsis: true },
    { title: 'Open ID', dataIndex: 'open_id', key: 'open_id', ellipsis: true },
    { title: '心愿内容', dataIndex: 'content', key: 'content', ellipsis: true },
    { title: '进度', key: 'progress', width: 110, render: (_: unknown, r: Wish) => `${r.current_days}/${r.target_days}天` },
    { title: '状态', dataIndex: 'status', key: 'status', width: 80, render: (v: number) => v === 1 ? <Tag color="green">已达成</Tag> : <Tag color="blue">进行中</Tag> },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 110, render: (v: string) => dayjs(v).format('YYYY-MM-DD') },
    { title: '操作', key: 'action', width: 80, render: (_: unknown, r: Wish) => <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)}>删除</Button> },
  ];

  return (
    <div>
      <Title level={4}>心愿管理</Title>
      <Table dataSource={data} columns={columns} rowKey="id" loading={loading}
        pagination={{ current: page, total, pageSize: 20, onChange: (p) => setPage(p), showTotal: (t) => `共 ${t} 条` }} />
    </div>
  );
}
