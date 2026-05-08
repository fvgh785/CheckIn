import { Component, ErrorInfo, ReactNode } from 'react';
import { Button, Result } from 'antd';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary] Caught error:', error, errorInfo);
  }

  handleReset = () => {
    // 清除状态并强制刷新页面
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_info');
    this.setState({ hasError: false, error: null });
    window.location.href = '/login';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          background: '#f0f2f5',
          padding: 24,
        }}>
          <Result
            status="error"
            title="页面加载异常"
            subTitle="应用遇到了一个错误，请尝试重新登录"
            extra={[
              <Button type="primary" key="retry" onClick={this.handleReset}>
                重新登录
              </Button>,
            ]}
          />
        </div>
      );
    }

    return this.props.children;
  }
}
