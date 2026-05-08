import { useEffect, useState } from 'react';
import { Table, Typography } from 'antd';
import { getMakeupCardList } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Card { id: string; user_id: string; open_id: string; used_date: string; used_at: string; }

export default function MakeupList() {
  const [data, setData] = useState<Card[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => { loadData(); }, [page]);

  const loadData = async () => {
    setLoading(true);
    try { const res = await getMakeupCardList({ page, page_size: 20 }); setData(res.data.cards); setTotal(res.data.total); }
    catch { /* handled */ } finally { setLoading(false); }
  };

  const columns = [
    { title: 'User ID', dataIndex: 'user_id', key: 'user_id', width: 180, ellipsis: true },
    { title: 'Open ID', dataIndex: 'open_id', key: 'open_id', width: 160, ellipsis: true },
    { title: '补签日期', dataIndex: 'used_date', key: 'used_date', width: 120 },
    { title: '使用时间', dataIndex: 'used_at', key: 'used_at', width: 170, render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss') },
  ];

  return (
    <div>
      <Title level={4}>补签记录</Title>
      <Table dataSource={data} columns={columns} rowKey="id" loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={{ current: page, total, pageSize: 20, onChange: (p) => setPage(p), showTotal: (t) => `共 ${t} 条` }} />
    </div>
  );
}
