import { useEffect, useState } from 'react';
import { Card, Descriptions, Typography, InputNumber, DatePicker, Button, message, Spin } from 'antd';
import dayjs from 'dayjs';
import { getConfig, updateConfig } from '../../services/admin';

const { Title } = Typography;

interface Config { makeup_card_limit: number; free_membership_cutoff_date: string; membership_level: string; app_version: string; }

export default function SystemConfig() {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [makeupLimit, setMakeupLimit] = useState(3);
  const [cutoffDate, setCutoffDate] = useState<string>('');

  useEffect(() => { loadConfig(); }, []);

  const loadConfig = async () => {
    try {
      const res = await getConfig();
      setConfig(res.data);
      setMakeupLimit(res.data.makeup_card_limit);
      setCutoffDate(res.data.free_membership_cutoff_date || '');
    }
    catch { /* handled */ } finally { setLoading(false); }
  };

  const handleSave = async () => {
    try {
      await updateConfig({ makeup_card_limit: makeupLimit, free_membership_cutoff_date: cutoffDate });
      message.success('配置已保存');
    }
    catch { /* handled */ }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div>
      <Title level={4}>系统配置</Title>
      <Card title="基本配置" style={{ maxWidth: 600, marginBottom: 16 }}>
        <Descriptions column={1}>
          <Descriptions.Item label="应用版本">{config?.app_version || '-'}</Descriptions.Item>
          <Descriptions.Item label="会员等级">{config?.membership_level || '-'}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="业务参数" style={{ maxWidth: 600 }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16 }}>
          <span>补签卡月限额:</span>
          <InputNumber min={0} max={10} value={makeupLimit} onChange={(v) => setMakeupLimit(v || 0)} />
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16 }}>
          <span>新注册免费送会员截止日期:</span>
          <DatePicker
            value={cutoffDate ? dayjs(cutoffDate) : null}
            onChange={(d) => setCutoffDate(d ? d.format('YYYY-MM-DD') : '')}
            placeholder="选择日期（留空则关闭活动）"
            style={{ width: 220 }}
          />
        </div>
        <Button type="primary" onClick={handleSave}>保存配置</Button>
      </Card>
    </div>
  );
}
