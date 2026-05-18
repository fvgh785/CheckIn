import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, Switch, Space, Tag, message, Popconfirm, Typography, Grid } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { getKnowledgeBases, getKnowledgeBaseDetail, createKnowledgeBase, updateKnowledgeBase, deleteKnowledgeBase, rebuildKnowledgeIndex } from '../../services/admin';

const { Title } = Typography;
const { TextArea } = Input;

interface KnowledgeBase {
  id: string;
  title: string;
  content_preview: string;
  category: string;
  enabled: number;
  created_at: string;
  updated_at: string | null;
}

const CATEGORIES = [
  { value: 'feature', label: '功能介绍' },
  { value: 'faq', label: '常见问题' },
  { value: 'announcement', label: '公告通知' },
  { value: 'general', label: '通用' },
];

export default function KnowledgeList() {
  const [data, setData] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<KnowledgeBase | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [contentLoading, setContentLoading] = useState(false);
  const [form] = Form.useForm();
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.lg;

  const fetchData = async (p = page) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page: p, page_size: 20 };
      if (categoryFilter) params.category = categoryFilter;
      const res = await getKnowledgeBases(params);
      setData(res.data.knowledge_bases);
      setTotal(res.data.total);
    } catch { /* handled */ }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchData(1); }, [categoryFilter]);

  const handleCreate = () => {
    setEditingItem(null);
    setContentLoading(false);
    form.resetFields();
    form.setFieldsValue({ category: 'general', enabled: true });
    setModalOpen(true);
  };

  const handleEdit = async (record: KnowledgeBase) => {
    setEditingItem(record);
    setContentLoading(true);
    // 先重置表单，避免残留数据
    form.resetFields();
    setModalOpen(true);
    try {
      const detail = await getKnowledgeBaseDetail(record.id);
      form.setFieldsValue({
        title: detail.data.title,
        content: detail.data.content,
        category: detail.data.category,
        enabled: detail.data.enabled === 1,
      });
    } catch {
      // 获取失败时至少回填已有数据
      form.setFieldsValue({
        title: record.title,
        category: record.category,
        enabled: record.enabled === 1,
      });
    } finally {
      setContentLoading(false);
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      if (editingItem) {
        await updateKnowledgeBase(editingItem.id, values);
        message.success('知识库已更新');
      } else {
        await createKnowledgeBase(values);
        message.success('知识库已创建');
      }
      setModalOpen(false);
      fetchData();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'errorFields' in err) return; // form validation
      message.error('操作失败');
    }
    finally { setSubmitting(false); }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteKnowledgeBase(id);
      message.success('已删除');
      fetchData();
    } catch { message.error('删除失败'); }
  };

  const handleRebuild = async () => {
    setRebuilding(true);
    try {
      await rebuildKnowledgeIndex();
      message.success('小程序功能介绍已更新');
    } catch { message.error('更新失败'); }
    finally { setRebuilding(false); }
  };

  const columns = [
    { title: '标题', dataIndex: 'title', key: 'title' },
    {
      title: '分类', dataIndex: 'category', key: 'category', width: 100,
      render: (cat: string) => {
        const found = CATEGORIES.find(c => c.value === cat);
        return <Tag>{found ? found.label : cat}</Tag>;
      },
    },
    {
      title: '状态', dataIndex: 'enabled', key: 'enabled', width: 80,
      render: (v: number) => v === 1 ? <Tag color="green">启用</Tag> : <Tag color="default">禁用</Tag>,
    },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 180, render: (v: string | null) => v || '-' },
    {
      title: '操作', key: 'actions', width: 160,
      render: (_: unknown, record: KnowledgeBase) => (
        <Space>
          <Button size="small" onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <Title level={4} style={{ margin: 0 }}>知识库管理</Title>
        <Space>
          <Select
            placeholder="分类筛选"
            allowClear
            style={{ width: 130 }}
            value={categoryFilter || undefined}
            onChange={(v) => { setCategoryFilter(v || ''); }}
            options={CATEGORIES.map(c => ({ value: c.value, label: c.label }))}
          />
          <Button icon={<ReloadOutlined />} loading={rebuilding} onClick={handleRebuild}>更新功能介绍</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新增知识库</Button>
        </Space>
      </div>

      <Table
        dataSource={data}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          onChange: (p) => { setPage(p); fetchData(p); },
        }}
      />

      <Modal
        title={editingItem ? '编辑知识库' : '新增知识库'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        confirmLoading={submitting}
        width={isMobile ? '95%' : 700}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input maxLength={200} placeholder="知识库标题" />
          </Form.Item>
          <Form.Item name="category" label="分类" rules={[{ required: true }]}>
            <Select options={CATEGORIES} />
          </Form.Item>
          <Form.Item name="enabled" label="启用状态（启用后用户可见）" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="content" label="内容" rules={editingItem ? [] : [{ required: true, message: '请输入内容' }]}>
            <TextArea rows={15} maxLength={10000} placeholder={contentLoading ? '加载中...' : '知识库正文内容'} disabled={contentLoading} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
