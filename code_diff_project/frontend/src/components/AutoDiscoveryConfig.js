import React, { useState, useEffect } from 'react';
import { 
    Card, Button, Form, Input, Select, message, Space, Spin, 
    Table, Tag, Tooltip, Modal, Alert 
} from 'antd';
import { 
    ReloadOutlined, CheckCircleOutlined, CloseCircleOutlined,
    SettingOutlined, FolderOpenOutlined, InfoCircleOutlined 
} from '@ant-design/icons';
import axios from 'axios';
import { API_BASE } from '../utils/api';

const { Option } = Select;
const { TextArea } = Input;

const GIT_ORG_URL = `${API_BASE}git-organizations/`;
const DISCOVERED_PROJECTS_URL = `${API_BASE}discovered-projects/`;

const AutoDiscoveryConfig = () => {
    const [organizations, setOrganizations] = useState([]);
    const [selectedOrg, setSelectedOrg] = useState(null);
    const [discoveredProjects, setDiscoveredProjects] = useState([]);
    const [loading, setLoading] = useState(false);
    const [discovering, setDiscovering] = useState(false);
    const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
    const [form] = Form.useForm();

    // 加载组织列表
    const fetchOrganizations = async () => {
        setLoading(true);
        try {
            const response = await axios.get(GIT_ORG_URL);
            setOrganizations(response.data);
            if (response.data.length > 0 && !selectedOrg) {
                setSelectedOrg(response.data[0]);
                fetchDiscoveredProjects(response.data[0].id);
            }
        } catch (error) {
            console.error('加载组织配置失败:', error);
            message.error('加载组织配置失败');
        } finally {
            setLoading(false);
        }
    };

    // 加载发现的项目
    const fetchDiscoveredProjects = async (orgId) => {
        setLoading(true);
        try {
            const response = await axios.get(DISCOVERED_PROJECTS_URL, {
                params: { organization_id: orgId }
            });
            setDiscoveredProjects(response.data);
        } catch (error) {
            console.error('加载发现的项目失败:', error);
            message.error('加载发现的项目失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchOrganizations();
    }, []);

    // 打开配置模态框
    const handleOpenConfigModal = () => {
        if (selectedOrg) {
            form.setFieldsValue({
                ...selectedOrg,
                access_token: '' // 不显示已有的 Token
            });
        } else {
            form.resetFields();
            form.setFieldsValue({
                git_server_type: 'gitlab',
                default_branch: 'master',
                is_active: true
            });
        }
        setIsConfigModalOpen(true);
    };

    // 保存配置
    const handleSaveConfig = async () => {
        try {
            const values = await form.validateFields();
            
            // 如果 Token 为空且是编辑模式，则不更新 Token
            if (!values.access_token && selectedOrg) {
                delete values.access_token;
            }
            
            if (selectedOrg) {
                // 更新
                await axios.put(`${GIT_ORG_URL}${selectedOrg.id}/`, values);
                message.success('更新配置成功');
            } else {
                // 创建
                await axios.post(GIT_ORG_URL, values);
                message.success('创建配置成功');
            }
            
            setIsConfigModalOpen(false);
            fetchOrganizations();
        } catch (error) {
            console.error('保存配置失败:', error);
            if (error.response?.data) {
                const errorMsg = Object.values(error.response.data).flat().join(', ');
                message.error(`保存失败: ${errorMsg}`);
            } else {
                message.error('保存配置失败');
            }
        }
    };

    // 测试连接
    const handleTestConnection = async () => {
        if (!selectedOrg) {
            message.warning('请先配置 Git 组织');
            return;
        }
        
        setLoading(true);
        try {
            const response = await axios.post(`${GIT_ORG_URL}${selectedOrg.id}/test-connection/`);
            if (response.data.success) {
                message.success(response.data.message);
            } else {
                message.error(response.data.message);
            }
        } catch (error) {
            console.error('测试连接失败:', error);
            const errorMsg = error.response?.data?.message || '测试连接失败';
            message.error(errorMsg);
        } finally {
            setLoading(false);
        }
    };

    // 发现项目
    const handleDiscoverProjects = async () => {
        if (!selectedOrg) {
            message.warning('请先配置 Git 组织');
            return;
        }
        
        setDiscovering(true);
        try {
            const response = await axios.post(`${GIT_ORG_URL}${selectedOrg.id}/discover-projects/`);
            if (response.data.success) {
                message.success(response.data.message);
                fetchOrganizations();
                fetchDiscoveredProjects(selectedOrg.id);
            } else {
                message.error(response.data.message);
            }
        } catch (error) {
            console.error('发现项目失败:', error);
            const errorMsg = error.response?.data?.message || '发现项目失败';
            message.error(errorMsg);
        } finally {
            setDiscovering(false);
        }
    };

    // 项目表格列定义
    const columns = [
        {
            title: 'ID',
            dataIndex: 'id',
            key: 'id',
            width: 50,
            fixed: 'left',
        },
        {
            title: '项目名称',
            dataIndex: 'project_name',
            key: 'project_name',
            width: 180,
            ellipsis: true,
        },
        {
            title: 'Git 地址',
            dataIndex: 'git_url',
            key: 'git_url',
            width: 250,
            ellipsis: true,
            render: (text) => (
                <Tooltip title={text}>
                    <span style={{ fontSize: '11px' }}>{text}</span>
                </Tooltip>
            ),
        },
        {
            title: '语言',
            dataIndex: 'language',
            key: 'language',
            width: 80,
            render: (text) => text ? <Tag color="blue">{text}</Tag> : '-',
        },
        {
            title: '默认分支',
            dataIndex: 'default_branch',
            key: 'default_branch',
            width: 90,
        },
        {
            title: '状态',
            dataIndex: 'is_active',
            key: 'is_active',
            width: 70,
            render: (isActive) => (
                isActive ? 
                    <Tag color="success" icon={<CheckCircleOutlined />}>启用</Tag> : 
                    <Tag color="default" icon={<CloseCircleOutlined />}>禁用</Tag>
            ),
        },
    ];

    return (
        <div style={{ padding: '20px' }}>
            {/* 配置卡片 */}
            <Card 
                title={
                    <Space>
                        <FolderOpenOutlined />
                        <span>自动发现配置</span>
                    </Space>
                }
                extra={
                    <Button 
                        type="primary" 
                        icon={<SettingOutlined />}
                        onClick={handleOpenConfigModal}
                    >
                        {selectedOrg ? '编辑配置' : '新建配置'}
                    </Button>
                }
                style={{ marginBottom: '20px' }}
            >
                {selectedOrg ? (
                    <div>
                        <Space direction="vertical" style={{ width: '100%' }} size="middle">
                            <div>
                                <strong>Git 服务器:</strong> {selectedOrg.git_server_url}
                            </div>
                            <div>
                                <strong>组织名称:</strong> {selectedOrg.name}
                            </div>
                            <div>
                                <strong>服务器类型:</strong> <Tag>{selectedOrg.git_server_type.toUpperCase()}</Tag>
                            </div>
                            {selectedOrg.last_discovery_at && (
                                <div>
                                    <strong>上次发现:</strong> {new Date(selectedOrg.last_discovery_at).toLocaleString('zh-CN')}
                                    <span style={{ marginLeft: '20px' }}>
                                        <strong>发现项目:</strong> {selectedOrg.discovered_project_count} 个
                                    </span>
                                </div>
                            )}
                            <Space>
                                <Button 
                                    onClick={handleTestConnection}
                                    loading={loading}
                                >
                                    测试连接
                                </Button>
                                <Button 
                                    type="primary"
                                    icon={<ReloadOutlined />}
                                    onClick={handleDiscoverProjects}
                                    loading={discovering}
                                >
                                    立即发现项目
                                </Button>
                            </Space>
                        </Space>
                    </div>
                ) : (
                    <Alert
                        message="尚未配置 Git 组织"
                        description="请点击右上角的"新建配置"按钮，配置您的 Git 组织信息以启用自动发现功能。"
                        type="info"
                        showIcon
                        icon={<InfoCircleOutlined />}
                    />
                )}
            </Card>

            {/* 发现的项目列表 */}
            {selectedOrg && (
                <Card 
                    title={`发现的项目 (${discoveredProjects.length})`}
                    extra={
                        <Button 
                            icon={<ReloadOutlined />}
                            onClick={() => fetchDiscoveredProjects(selectedOrg.id)}
                        >
                            刷新
                        </Button>
                    }
                >
                    <Table
                        columns={columns}
                        dataSource={discoveredProjects}
                        rowKey="id"
                        loading={loading}
                        pagination={{
                            pageSize: 10,
                            showSizeChanger: true,
                            showTotal: (total) => `共 ${total} 个项目`,
                        }}
                        scroll={{ x: 900 }}
                        size="small"
                    />
                </Card>
            )}

            {/* 配置模态框 */}
            <Modal
                title={selectedOrg ? "编辑 Git 组织配置" : "新建 Git 组织配置"}
                open={isConfigModalOpen}
                onOk={handleSaveConfig}
                onCancel={() => setIsConfigModalOpen(false)}
                width={600}
                okText="保存"
                cancelText="取消"
            >
                <Form
                    form={form}
                    layout="vertical"
                >
                    <Form.Item
                        label="Git 服务器地址"
                        name="git_server_url"
                        rules={[{ required: true, message: '请输入 Git 服务器地址' }]}
                        tooltip="例如: https://git.hrlyit.com"
                    >
                        <Input placeholder="https://git.hrlyit.com" />
                    </Form.Item>

                    <Form.Item
                        label="组织/群组名称"
                        name="name"
                        rules={[{ required: true, message: '请输入组织名称' }]}
                        tooltip="例如: beehive"
                    >
                        <Input placeholder="beehive" />
                    </Form.Item>

                    <Form.Item
                        label="Git 服务器类型"
                        name="git_server_type"
                        rules={[{ required: true, message: '请选择服务器类型' }]}
                    >
                        <Select>
                            <Option value="gitlab">GitLab</Option>
                            <Option value="github">GitHub (暂不支持)</Option>
                            <Option value="gitea">Gitea (暂不支持)</Option>
                        </Select>
                    </Form.Item>

                    <Form.Item
                        label="访问 Token"
                        name="access_token"
                        rules={[
                            { required: !selectedOrg, message: '请输入访问 Token' }
                        ]}
                        tooltip="在 GitLab 中生成的 Personal Access Token，需要 read_api 和 read_repository 权限"
                    >
                        <Input.Password 
                            placeholder={selectedOrg ? "留空则不修改" : "glpat-xxxxxxxxxxxx"} 
                        />
                    </Form.Item>

                    <Form.Item
                        label="默认分支"
                        name="default_branch"
                        rules={[{ required: true, message: '请输入默认分支' }]}
                    >
                        <Input placeholder="master" />
                    </Form.Item>

                    <Alert
                        message="如何获取 Token？"
                        description={
                            <div>
                                <p>1. 登录 GitLab → 点击头像 → Settings</p>
                                <p>2. 左侧菜单选择 "Access Tokens"</p>
                                <p>3. 创建新 Token，勾选权限: read_api, read_repository</p>
                                <p>4. 复制生成的 Token 并粘贴到上方输入框</p>
                            </div>
                        }
                        type="info"
                        showIcon
                        style={{ marginTop: '10px' }}
                    />
                </Form>
            </Modal>
        </div>
    );
};

export default AutoDiscoveryConfig;
