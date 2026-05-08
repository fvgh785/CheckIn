import { useEffect, useState } from 'react';
import { Table, Typography } from 'antd';
import { getInsightList } from '../../services/admin';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Insight { id: string; user_id: string; open_id: string; week_start: string; content: string; created_at: string; }

export default function InsightList() {
  const [data, setData] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => { loadData(); }, [page]);

  const loadData = async () => {
    setLoading(true);
    try { const res = await getInsightList({ page, page_size: 20 }); setData(res.data.insights); setTotal(res.data.total); }
    catch { /* handled */ } finally { setLoading(false); }
  };

  const columns = [
    { title: 'User ID', dataIndex: 'user_id', key: 'user_id', width: 120, ellipsis: true },
    { title: 'Open ID', dataIndex: 'open_id', key: 'open_id', ellipsis: true },
    { title: '周起始', dataIndex: 'week_start', key: 'week_start', width: 110 },
    { title: '洞察内容', dataIndex: 'content', key: 'content', ellipsis: true },
    { title: '生成时间', dataIndex: 'created_at', key: 'created_at', width: 170, render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss') },
  ];

  return (
    <div>
      <Title level={4}>AI洞察管理</Title>
      <Table dataSource={data} columns={columns} rowKey="id" loading={loading}
        pagination={{ current: page, total, pageSize: 20, onChange: (p) => setPage(p), showTotal: (t) => `共 ${t} 条` }} />
    </div>
  );
}
