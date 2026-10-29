import { ApiOutlined, GithubOutlined, GitlabOutlined, SendOutlined, SlackOutlined, DatabaseOutlined, GlobalOutlined, FolderOpenOutlined, CheckSquareOutlined } from '@ant-design/icons';

export const getProviderIcon = (provider: string, size = 24) => {
    switch (provider.toLowerCase()) {
      case 'github':
      case 'git':
        return <GithubOutlined style={{ fontSize: size, color: '#f0f6fc' }} />;
      case 'gitlab':
        return <GitlabOutlined style={{ fontSize: size, color: '#fc6d26' }} />;
      case 'trello':
        return <CheckSquareOutlined style={{ fontSize: size, color: '#0079bf' }} />;
      case 'telegram':
        return <SendOutlined style={{ fontSize: size, color: '#229ED9' }} />;
      case 'slack':
        return <SlackOutlined style={{ fontSize: size, color: '#ECB22E' }} />;
      case 'postgres':
      case 'database':
        return <DatabaseOutlined style={{ fontSize: size, color: '#336791' }} />;
      case 'brave-search':
      case 'search':
        return <GlobalOutlined style={{ fontSize: size, color: '#FB542B' }} />;
      case 'filesystem':
        return <FolderOpenOutlined style={{ fontSize: size, color: '#10b981' }} />;
      default:
        return <ApiOutlined style={{ fontSize: size, color: '#a855f7' }} />;
    }
  };

