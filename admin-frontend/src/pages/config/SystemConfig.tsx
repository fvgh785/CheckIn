import { useEffect, useState } from 'react';
import { Card, Descriptions, Typography, InputNumber, DatePicker, Button, message, Spin, Switch, Grid } from 'antd';
import dayjs from 'dayjs';
import { getConfig, updateConfig } from '../../services/admin';

const { Title } = Typography;

interface Config { makeup_card_limit: number; free_membership_cutoff_date: string; insight_generation_limit: number; chat_enabled: string; chat_token_limit_per_day: number; membership_level: string; app_version: string; }

export default function SystemConfig() {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [makeupLimit, setMakeupLimit] = useState(3);
  const [cutoffDate, setCutoffDate] = useState<string>('');
  const [insightLimit, setInsightLimit] = useState(3);
  const [chatEnabled, setChatEnabled] = useState(true);
  const [chatTokenLimit, setChatTokenLimit] = useState(5000);
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.lg;

  useEffect(() => { loadConfig(); }, []);

  const loadConfig = async () => {
    try {
      const res = await getConfig();
      setConfig(res.data);
      setMakeupLimit(res.data.makeup_card_limit);
      setCutoffDate(res.data.free_membership_cutoff_date || '');
      setInsightLimit(res.data.insight_generation_limit ?? 3);
      setChatEnabled(res.data.chat_enabled !== '0');
      setChatTokenLimit(res.data.chat_token_limit_per_day ?? 5000);
    }
    catch { /* handled */ } finally { setLoading(false); }
  };

  const handleSave = async () => {
    try {
      await updateConfig({ makeup_card_limit: makeupLimit, free_membership_cutoff_date: cutoffDate, insight_generation_limit: insightLimit, chat_enabled: chatEnabled, chat_token_limit_per_day: chatTokenLimit });
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
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
          <span>补签卡月限额:</span>
          <InputNumber min={0} max={10} value={makeupLimit} onChange={(v) => setMakeupLimit(v || 0)} />
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
          <span>新注册免费送会员截止日期:</span>
          <DatePicker
            value={cutoffDate ? dayjs(cutoffDate) : null}
            onChange={(d) => setCutoffDate(d ? d.format('YYYY-MM-DD') : '')}
            placeholder="选择日期（留空则关闭活动）"
            style={{ maxWidth: 220, width: '100%' }}
          />
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
          <span>AI洞察每日手动生成上限:</span>
          <InputNumber min={0} max={20} value={insightLimit} onChange={(v) => setInsightLimit(v || 0)} />
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
          <span>AI智能助手全局开关:</span>
          <Switch checked={chatEnabled} onChange={(v) => setChatEnabled(v)} />
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
          <span>AI助手每日Token上限:</span>
          <InputNumber min={0} max={100000} value={chatTokenLimit} onChange={(v) => setChatTokenLimit(v || 0)} />
        </div>
        <Button type="primary" onClick={handleSave}>保存配置</Button>
      </Card>
    </div>
  );
}
