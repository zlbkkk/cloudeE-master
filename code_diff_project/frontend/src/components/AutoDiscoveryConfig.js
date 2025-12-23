import { useState, useEffect } from 'react';
import { 
    Card, Button, Form, Input, Select, message, Space,
    Table, Tag, Tooltip, Modal, Alert 
} from 'antd';
import { 
    ReloadOutlined, CheckCircleOutlined, CloseCircleOutlined,
    SettingOutlined, FolderOpenOutlined, InfoCircleOutlined 
} from '@ant-design/icons';
import axios from 'axios';
import { API_BASE } from '../utils/api';
import './AutoDiscoveryConfig.css';

const { Option } = Select;

const GIT_ORG_URL = `${API_BASE}git-organizations/`;
const DISCOVERED_PROJECTS_URL = `${API_BASE}discovered-projects/`;

// 组织项目列表子组件
const OrganizationProjects = ({ orgId, onDelete, refreshTrigger, onProjectCountChange, searchText, onSearchChange }) => {
    const [projects, setProjects] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedRowKeys, setSelectedRowKeys] = useState([]);
    const [batchDeleting, setBatchDeleting] = useState(false);
    const [batchDeleteModalVisible, setBatchDeleteModalVisible] = useState(false);

    useEffect(() => {
        fetchProjects();
    }, [orgId, refreshTrigger]);

    const fetchProjects = async () => {
        setLoading(true);
        try {
            const response = await axios.get(DISCOVERED_PROJECTS_URL, {
                params: { organization_id: orgId }
            });
            setProjects(response.data);
        } catch (error) {
            console.error('加载项目失败:', error);
        } finally {
            setLoading(false);
        }
    };

    // 根据搜索文本过滤项目
    const filteredProjects = projects.filter(project =>
        project.project_name.toLowerCase().includes(searchText.toLowerCase())
    );

    // 当过滤后的项目数量变化时，通知父组件
    useEffect(() => {
        if (onProjectCountChange) {
            onProjectCountChange(filteredProjects.length);
        }
    }, [filteredProjects.length]); // 移除 onProjectCountChange 依赖

    // 批量删除处理 - 打开确认对话框
    const handleBatchDelete = () => {
        if (!selectedRowKeys || selectedRowKeys.length === 0) {
            message.warning('请先选择要删除的项目');
            return;
        }
        setBatchDeleteModalVisible(true);
    };

    // 执行批量删除
    const executeBatchDelete = async () => {
        setBatchDeleting(true);
        const deleteCount = selectedRowKeys.length;
        
        try {
            const hideLoading = message.loading('正在批量删除...', 0);
            
            const deletePromises = selectedRowKeys.map(id => 
                axios.delete(`${DISCOVERED_PROJECTS_URL}${id}/`)
            );
            
            await Promise.all(deletePromises);
            hideLoading();
            
            // 先关闭对话框
            setBatchDeleteModalVisible(false);
            setSelectedRowKeys([]);
            
            // 显示成功提示并刷新数据
            setTimeout(() => {
                message.success(`成功删除 ${deleteCount} 个项目`);
                fetchProjects();
            }, 300);
            
        } catch (error) {
            console.error('批量删除失败:', error);
            message.error('批量删除失败，请重试');
        } finally {
            setBatchDeleting(false);
        }
    };

    // 行选择配置
    const rowSelection = {
        selectedRowKeys,
        onChange: (selectedKeys) => {
            setSelectedRowKeys(selectedKeys);
        },
    };

    const columns = [
        {
            title: '项目名称',
            dataIndex: 'project_name',
            key: 'project_name',
            width: 200,
        },
        {
            title: 'Git 地址',
            dataIndex: 'git_url',
            key: 'git_url',
            ellipsis: true,
            render: (text) => (
                <Tooltip title={text}>
                    <a href={text} target="_blank" rel="noopener noreferrer" style={{ fontSize: '12px' }}>
                        {text}
                    </a>
                </Tooltip>
            ),
        },
        {
            title: '默认分支',
            dataIndex: 'default_branch',
            key: 'default_branch',
            width: 100,
        },
        {
            title: '创建时间',
            dataIndex: 'created_at',
            key: 'created_at',
            width: 150,
            render: (text) => text ? new Date(text).toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            }) : '-',
        },
        {
            title: '操作',
            key: 'action',
            width: 80,
            fixed: 'right',
            render: (_, record) => (
                <Button 
                    type="link" 
                    danger 
                    size="small"
                    onClick={(e) => {
                        e.stopPropagation();
                        onDelete(record.id, record.project_name);
                    }}
                >
                    删除
                </Button>
            ),
        },
    ];

    if (projects.length === 0 && !loading) {
        return (
            <Alert
                message="暂无项目"
                description="点击上方【采集项目】按钮开始自动采集该组织下的所有项目"
                type="info"
                showIcon
            />
        );
    }

    return (
        <div>
            {/* 批量操作工具栏 */}
            {selectedRowKeys.length > 0 && (
                <div style={{
                    marginBottom: '12px',
                    padding: '12px 16px',
                    backgroundColor: '#e6f7ff',
                    borderRadius: '4px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    border: '1px solid #91d5ff'
                }}>
                    <span style={{ color: '#1890ff', fontWeight: '500' }}>
                        已选择 {selectedRowKeys.length} 个项目
                    </span>
                    <Space>
                        <Button 
                            size="small"
                            onClick={() => setSelectedRowKeys([])}
                        >
                            取消选择
                        </Button>
                        <Button 
                            type="primary"
                            danger
                            size="small"
                            loading={batchDeleting}
                            onClick={handleBatchDelete}
                        >
                            批量删除
                        </Button>
                    </Space>
                </div>
            )}

            {/* 项目表格 */}
            <Table
                rowSelection={rowSelection}
                columns={columns}
                dataSource={filteredProjects}
                rowKey="id"
                loading={loading}
                pagination={{
                    pageSize: 5,
                    showSizeChanger: false,
                    showTotal: (total) => `共 ${total} 个项目`,
                    size: 'small'
                }}
                scroll={{ x: 1000 }}
                size="small"
            />

            {/* 批量删除确认对话框 */}
            <Modal
                open={batchDeleteModalVisible}
                onOk={executeBatchDelete}
                onCancel={() => setBatchDeleteModalVisible(false)}
                footer={[
                    <Button 
                        key="cancel" 
                        onClick={() => setBatchDeleteModalVisible(false)}
                        style={{
                            height: '36px',
                            fontSize: '14px',
                            fontWeight: '500'
                        }}
                    >
                        取消
                    </Button>,
                    <Button 
                        key="delete" 
                        type="primary" 
                        danger
                        onClick={executeBatchDelete}
                        loading={batchDeleting}
                        style={{
                            height: '36px',
                            fontSize: '14px',
                            fontWeight: '500'
                        }}
                    >
                        确定删除
                    </Button>
                ]}
                width={460}
                centered
                closable={false}
                transitionName=""
                maskTransitionName=""
            >
                <div style={{ 
                    display: 'flex', 
                    alignItems: 'flex-start', 
                    gap: '16px',
                    padding: '8px 0'
                }}>
                    {/* 警告图标 */}
                    <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '50%',
                        backgroundColor: '#fff2e8',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0
                    }}>
                        <span style={{ 
                            fontSize: '24px',
                            color: '#fa8c16'
                        }}>⚠</span>
                    </div>
                    
                    {/* 文本内容 */}
                    <div style={{ flex: 1 }}>
                        <h3 style={{ 
                            margin: '0 0 12px 0', 
                            fontSize: '16px', 
                            fontWeight: '600',
                            color: '#262626'
                        }}>
                            批量删除确认
                        </h3>
                        <p style={{ 
                            margin: '0 0 8px 0', 
                            fontSize: '14px',
                            color: '#595959',
                            lineHeight: '1.6'
                        }}>
                            确定要删除选中的 <strong style={{ color: '#262626' }}>{selectedRowKeys.length}</strong> 个项目吗？
                        </p>
                        <p style={{ 
                            margin: 0, 
                            fontSize: '13px',
                            color: '#ff4d4f',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px'
                        }}>
                            <span style={{ fontSize: '16px' }}>⚠</span>
                            <span>此操作不可恢复！</span>
                        </p>
                    </div>
                </div>
            </Modal>
        </div>
    );
};

const AutoDiscoveryConfig = () => {
    const [organizations, setOrganizations] = useState([]);
    const [selectedOrg, setSelectedOrg] = useState(null);
    const [testingConnection, setTestingConnection] = useState(false);
    const [discoveringOrgs, setDiscoveringOrgs] = useState({});
    const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
    const [deleteModalVisible, setDeleteModalVisible] = useState(false);
    const [projectToDelete, setProjectToDelete] = useState(null);
    const [refreshTrigger, setRefreshTrigger] = useState(0);
    const [orgProjectCounts, setOrgProjectCounts] = useState({});
    const [toastMessage, setToastMessage] = useState(null);
    const [orgSearchTexts, setOrgSearchTexts] = useState({});
    const [form] = Form.useForm();

    // 显示 toast 提示
    const showToast = (message, type = 'success') => {
        setToastMessage({ message, type });
        setTimeout(() => {
            setToastMessage(null);
        }, 2000);
    };

    // 更新组织的项目数量
    const handleProjectCountChange = (orgId, count) => {
        setOrgProjectCounts(prev => ({
            ...prev,
            [orgId]: count
        }));
    };

    // 加载组织列表
    const fetchOrganizations = async () => {
        try {
            const response = await axios.get(GIT_ORG_URL);
            setOrganizations(response.data);
        } catch (error) {
            console.error('加载组织配置失败:', error);
            message.error('加载组织配置失败');
        }
    };

    useEffect(() => {
        fetchOrganizations();
    }, []);

    // 打开配置模态框
    const handleOpenConfigModal = (org = null) => {
        if (org) {
            // 先设置选中的组织
            setSelectedOrg(org);
            // 然后填充表单
            form.setFieldsValue({
                git_server_url: org.git_server_url,
                name: org.name,
                git_server_type: org.git_server_type,
                default_branch: org.default_branch || 'master',
                is_active: org.is_active,
                access_token: '' // 不显示已有的 Token
            });
        } else {
            setSelectedOrg(null);
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

    /* 测试连接功能已注释 - 保留代码以便日后使用
    // 测试连接
    const handleTestConnection = async (orgId) => {
        setTestingConnection(true);
        
        try {
            const response = await axios.post(`${GIT_ORG_URL}${orgId}/test-connection/`);
            
            if (response.data.success) {
                showToast(response.data.message || '连接测试成功');
            } else {
                showToast(response.data.message || '连接测试失败', 'error');
            }
        } catch (error) {
            console.error('测试连接失败:', error);
            
            let errorMsg = '测试连接失败';
            if (error.response?.data?.message) {
                errorMsg = error.response.data.message;
            } else if (error.response?.status === 404) {
                errorMsg = '接口不存在，请检查后端服务';
            } else if (error.response?.status === 400) {
                errorMsg = error.response?.data?.message || 'Token 无效或权限不足';
            } else if (error.message) {
                errorMsg = `网络错误: ${error.message}`;
            }
            
            showToast(errorMsg, 'error');
        } finally {
            setTestingConnection(false);
        }
    };
    */

    // 采集项目
    const handleDiscoverProjects = async (orgId) => {
        // 设置该组织为加载状态
        setDiscoveringOrgs(prev => ({ ...prev, [orgId]: true }));
        
        // 记录开始时间，用于轮询检查
        const startTime = Date.now();
        const maxWaitTime = 120000; // 最多等待2分钟
        
        try {
            const response = await axios.post(`${GIT_ORG_URL}${orgId}/discover-projects/`);
            
            if (!response.data.success) {
                showToast(response.data.message || '项目发现失败', 'error');
                // 移除加载状态
                setDiscoveringOrgs(prev => {
                    const newState = { ...prev };
                    delete newState[orgId];
                    return newState;
                });
                return;
            }
            
            // 后台任务已启动，开始轮询检查是否完成
            const checkCompletion = async () => {
                try {
                    // 获取最新的组织信息
                    const orgResponse = await axios.get(`${GIT_ORG_URL}${orgId}/`);
                    const updatedOrg = orgResponse.data;
                    
                    // 检查 last_discovery_at 是否更新（说明任务完成）
                    const originalOrg = organizations.find(o => o.id === orgId);
                    const hasUpdated = updatedOrg.last_discovery_at !== originalOrg?.last_discovery_at;
                    
                    if (hasUpdated) {
                        // 任务完成，判断是成功还是失败
                        const projectCount = updatedOrg.discovered_project_count || 0;
                        
                        if (projectCount > 0) {
                            // 采集了项目，成功
                            showToast(`项目采集成功，共采集 ${projectCount} 个项目`);
                        } else {
                            // 未采集到项目，可能是失败或真的没有项目
                            showToast('未采集到任何项目，请检查组织名称或网络连接', 'error');
                        }
                        
                        // 刷新组织列表以更新项目计数
                        await fetchOrganizations();
                        // 触发所有 OrganizationProjects 组件重新加载数据
                        setRefreshTrigger(prev => prev + 1);
                        // 移除加载状态
                        setDiscoveringOrgs(prev => {
                            const newState = { ...prev };
                            delete newState[orgId];
                            return newState;
                        });
                    } else if (Date.now() - startTime < maxWaitTime) {
                        // 还未完成，继续轮询（每2秒检查一次）
                        setTimeout(checkCompletion, 2000);
                    } else {
                        // 超时
                        showToast('项目发现超时，请手动刷新查看结果', 'error');
                        // 移除加载状态
                        setDiscoveringOrgs(prev => {
                            const newState = { ...prev };
                            delete newState[orgId];
                            return newState;
                        });
                    }
                } catch (error) {
                    console.error('检查发现状态失败:', error);
                    // 继续轮询，不中断
                    if (Date.now() - startTime < maxWaitTime) {
                        setTimeout(checkCompletion, 2000);
                    } else {
                        setDiscoveringOrgs(prev => {
                            const newState = { ...prev };
                            delete newState[orgId];
                            return newState;
                        });
                    }
                }
            };
            
            // 开始轮询
            setTimeout(checkCompletion, 2000);
            
        } catch (error) {
            console.error('采集项目失败:', error);
            const errorMsg = error.response?.data?.message || '采集项目失败';
            showToast(errorMsg, 'error');
            // 移除该组织的加载状态
            setDiscoveringOrgs(prev => {
                const newState = { ...prev };
                delete newState[orgId];
                return newState;
            });
        }
    };

    // 删除项目
    const handleDeleteProject = async () => {
        if (!projectToDelete) return;
        
        const projectName = projectToDelete.name;
        const projectId = projectToDelete.id;
        
        try {
            const hideLoading = message.loading('正在删除...', 0);
            await axios.delete(`${DISCOVERED_PROJECTS_URL}${projectId}/`);
            hideLoading();
            
            // 先关闭对话框
            setDeleteModalVisible(false);
            setProjectToDelete(null);
            
            // 显示成功提示
            setTimeout(() => {
                showToast(`项目 "${projectName}" 删除成功`);
                
                // 刷新数据
                fetchOrganizations();
                setRefreshTrigger(prev => prev + 1);
            }, 300);
            
        } catch (error) {
            console.error('删除项目失败:', error);
            
            let errorMsg = '删除项目失败';
            if (error.response?.data) {
                errorMsg = `${JSON.stringify(error.response.data)}`;
            } else if (error.message) {
                errorMsg = error.message;
            }
            
            showToast(`删除失败：${errorMsg}`, 'error');
        }
    };
    
    // 打开删除确认对话框
    const showDeleteConfirm = (record) => {
        setProjectToDelete({
            id: record.id,
            name: record.project_name
        });
        setDeleteModalVisible(true);
    };

    return (
        <div style={{ padding: '0 20px 20px 20px' }}>
            {/* Toast 提示 */}
            {toastMessage && (
                <div style={{
                    position: 'fixed',
                    top: '80px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: toastMessage.type === 'success' 
                        ? 'linear-gradient(135deg, #52c41a 0%, #73d13d 100%)'
                        : 'linear-gradient(135deg, #ff4d4f 0%, #ff7875 100%)',
                    color: '#ffffff',
                    padding: '16px 32px',
                    borderRadius: '8px',
                    boxShadow: '0 6px 16px rgba(0,0,0,0.2), 0 3px 6px rgba(0,0,0,0.12)',
                    zIndex: 9999,
                    fontSize: '15px',
                    fontWeight: '500',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    minWidth: '300px',
                    maxWidth: '500px',
                    animation: 'slideDown 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)',
                }}>
                    <span style={{ fontSize: '20px' }}>
                        {toastMessage.type === 'success' ? '✓' : '✕'}
                    </span>
                    <span>{toastMessage.message}</span>
                </div>
            )}

            {/* 顶部操作栏 */}
            <div style={{ 
                marginBottom: '20px', 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                backgroundColor: '#ffffff',
                padding: '16px',
                borderRadius: '8px',
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                border: '1px solid #e5e7eb'
            }}>
                <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 'bold', color: '#1f2937' }}>
                    <FolderOpenOutlined style={{ marginRight: '8px', color: '#3b82f6' }} />
                    项目集配置
                </h2>
                <Button 
                    type="primary" 
                    icon={<SettingOutlined />}
                    onClick={() => handleOpenConfigModal(null)}
                    size="large"
                    style={{
                        backgroundColor: '#1890ff',
                        borderColor: '#1890ff',
                        color: '#ffffff',
                        fontWeight: 'bold',
                        height: '40px',
                        minWidth: '120px',
                        fontSize: '14px'
                    }}
                >
                    新建配置
                </Button>
            </div>

            {/* 组织列表 - 每个组织一个卡片 */}
            {organizations.length === 0 ? (
                <Card>
                    <Alert
                        message="尚未配置 Git 组织"
                        description="请点击右上角的【新建配置】按钮，配置您的 Git 组织信息以启用自动发现功能。"
                        type="info"
                        showIcon
                        icon={<InfoCircleOutlined />}
                    />
                </Card>
            ) : (
                organizations.map(org => (
                    <Card 
                        key={org.id}
                        title={
                            <Space>
                                <FolderOpenOutlined style={{ color: '#3b82f6' }} />
                                <span style={{ fontWeight: 'bold' }}>{org.name}</span>
                                <Tag color="blue">{org.git_server_type.toUpperCase()}</Tag>
                                {(orgProjectCounts[org.id] !== undefined ? orgProjectCounts[org.id] : org.discovered_project_count) > 0 && (
                                    <Tag color="green">
                                        {orgProjectCounts[org.id] !== undefined ? orgProjectCounts[org.id] : org.discovered_project_count} 个项目
                                    </Tag>
                                )}
                            </Space>
                        }
                        extra={
                            <Space>
                                <Button 
                                    size="small"
                                    onClick={() => handleOpenConfigModal(org)}
                                >
                                    编辑
                                </Button>
                                {/* 测试连接功能已注释 - 保留代码以便日后使用
                                <Button 
                                    size="small"
                                    onClick={() => handleTestConnection(org.id)}
                                    loading={testingConnection}
                                >
                                    测试连接
                                </Button>
                                */}
                                <Button 
                                    type="primary"
                                    size="small"
                                    icon={<ReloadOutlined />}
                                    onClick={() => handleDiscoverProjects(org.id)}
                                    loading={discoveringOrgs[org.id]}
                                >
                                    {discoveringOrgs[org.id] ? '采集中...' : '采集项目'}
                                </Button>
                            </Space>
                        }
                        style={{ marginBottom: '20px' }}
                    >
                        <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Space size="large" style={{ fontSize: '13px' }}>
                                <span>
                                    <strong>Git 服务器:</strong> {org.git_server_url}
                                </span>
                                {org.last_discovery_at && (
                                    <span>
                                        <strong>上次采集:</strong> {new Date(org.last_discovery_at).toLocaleString('zh-CN')}
                                    </span>
                                )}
                            </Space>
                            <div>
                                <Input.Search
                                    placeholder="搜索项目名称..."
                                    allowClear
                                    value={orgSearchTexts[org.id] || ''}
                                    onChange={(e) => setOrgSearchTexts(prev => ({ ...prev, [org.id]: e.target.value }))}
                                    style={{ width: '250px' }}
                                    size="small"
                                />
                                {orgSearchTexts[org.id] && (
                                    <span style={{ marginLeft: '12px', color: '#666', fontSize: '13px' }}>
                                        找到 {orgProjectCounts[org.id] || 0} 个项目
                                    </span>
                                )}
                            </div>
                        </div>

                        {/* 该组织下的项目列表 */}
                        <OrganizationProjects 
                            orgId={org.id}
                            refreshTrigger={refreshTrigger}
                            searchText={orgSearchTexts[org.id] || ''}
                            onSearchChange={(text) => setOrgSearchTexts(prev => ({ ...prev, [org.id]: text }))}
                            onProjectCountChange={(count) => handleProjectCountChange(org.id, count)}
                            onDelete={(projectId, projectName) => {
                                showDeleteConfirm({ id: projectId, project_name: projectName });
                            }}
                        />
                    </Card>
                ))
            )}

            {/* 配置模态框 */}
            <Modal
                title={selectedOrg ? "编辑 Git 组织配置" : "新建 Git 组织配置"}
                open={isConfigModalOpen}
                onOk={handleSaveConfig}
                onCancel={() => setIsConfigModalOpen(false)}
                width={550}
                okText="保存"
                cancelText="取消"
            >
                <Form
                    form={form}
                    layout="vertical"
                    style={{ marginTop: '16px' }}
                >
                    <Form.Item
                        label="Git 服务器地址"
                        name="git_server_url"
                        rules={[{ required: true, message: '请输入 Git 服务器地址' }]}
                        tooltip="GitLab: https://git.hrlyit.com 或 https://gitlab.com | GitHub: https://api.github.com 或 https://github.com"
                        style={{ marginBottom: '16px' }}
                    >
                        <Input placeholder="https://git.hrlyit.com 或 https://github.com" size="middle" />
                    </Form.Item>

                    <Form.Item
                        label="组织/群组名称"
                        name="name"
                        rules={[{ required: true, message: '请输入组织名称' }]}
                        tooltip={
                            <div style={{ maxWidth: '300px', fontSize: '12px' }}>
                                <div style={{ marginBottom: '6px', fontWeight: 'bold' }}>填写 Git 组织或群组的名称</div>
                                <div style={{ marginBottom: '4px' }}>• GitLab: 填写 Group 名称（URL 中的组织路径）</div>
                                <div style={{ marginBottom: '4px' }}>• 示例: 如果项目地址是 https://git.hrlyit.com/beehive/project-name</div>
                                <div style={{ marginBottom: '8px' }}>• 则组织名称为: beehive</div>
                                <div style={{ marginBottom: '4px' }}>• GitHub: 填写 Organization 或 User 名称</div>
                                <div style={{ marginBottom: '4px' }}>• 示例: 如果项目地址是 https://github.com/zlbkkk/common-api</div>
                                <div>• 则组织名称为: zlbkkk</div>
                            </div>
                        }
                        style={{ marginBottom: '16px' }}
                    >
                        <Input placeholder="beehive 或 zlbkkk" size="middle" />
                    </Form.Item>

                    <Form.Item
                        label="Git 服务器类型"
                        name="git_server_type"
                        rules={[{ required: true, message: '请选择服务器类型' }]}
                        style={{ marginBottom: '16px' }}
                    >
                        <Select size="middle">
                            <Option value="gitlab">GitLab</Option>
                            <Option value="github">GitHub</Option>
                            <Option value="gitea">Gitea (暂不支持)</Option>
                        </Select>
                    </Form.Item>

                    <Form.Item
                        label="访问 Token"
                        name="access_token"
                        rules={[
                            { required: !selectedOrg, message: '请输入访问 Token' }
                        ]}
                        tooltip="GitLab: Personal Access Token (需要 read_api 和 read_repository 权限) | GitHub: Personal Access Token (需要 repo 权限)"
                        style={{ marginBottom: '16px' }}
                    >
                        <Input.Password 
                            placeholder={selectedOrg ? "留空则不修改" : "glpat-xxxxxxxxxxxx 或 ghp_xxxxxxxxxxxx"} 
                            size="middle"
                        />
                    </Form.Item>

                    <Form.Item
                        label="默认分支"
                        name="default_branch"
                        rules={[{ required: true, message: '请输入默认分支' }]}
                        style={{ marginBottom: '16px' }}
                    >
                        <Input placeholder="master" size="middle" />
                    </Form.Item>

                    <Alert
                        message="如何获取 Token？"
                        description={
                            <div style={{ fontSize: '12px', lineHeight: '1.5' }}>
                                <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>GitLab:</div>
                                <p style={{ margin: '4px 0' }}>1. 登录 GitLab → 点击头像 → Settings</p>
                                <p style={{ margin: '4px 0' }}>2. 左侧菜单选择 Access Tokens</p>
                                <p style={{ margin: '4px 0' }}>3. 创建新 Token，勾选权限: read_api, read_repository</p>
                                <p style={{ margin: '4px 0 8px 0' }}>4. 复制生成的 Token 并粘贴到上方输入框</p>
                                
                                <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>GitHub:</div>
                                <p style={{ margin: '4px 0' }}>1. 登录 GitHub → 点击头像 → Settings</p>
                                <p style={{ margin: '4px 0' }}>2. 左侧菜单选择 Developer settings → Personal access tokens → Tokens (classic)</p>
                                <p style={{ margin: '4px 0' }}>3. 创建新 Token，勾选权限: repo (Full control of private repositories)</p>
                                <p style={{ margin: '4px 0 0 0' }}>4. 复制生成的 Token 并粘贴到上方输入框</p>
                            </div>
                        }
                        type="info"
                        showIcon
                        style={{ marginBottom: '0', padding: '8px 12px' }}
                    />
                </Form>
            </Modal>

            {/* 删除确认对话框 */}
            <Modal
                open={deleteModalVisible}
                onOk={handleDeleteProject}
                onCancel={() => {
                    setDeleteModalVisible(false);
                    setProjectToDelete(null);
                }}
                footer={[
                    <Button 
                        key="cancel" 
                        onClick={() => {
                            setDeleteModalVisible(false);
                            setProjectToDelete(null);
                        }}
                        style={{
                            height: '36px',
                            fontSize: '14px',
                            fontWeight: '500'
                        }}
                    >
                        取消
                    </Button>,
                    <Button 
                        key="delete" 
                        type="primary" 
                        danger
                        onClick={handleDeleteProject}
                        style={{
                            height: '36px',
                            fontSize: '14px',
                            fontWeight: '500'
                        }}
                    >
                        确定删除
                    </Button>
                ]}
                width={460}
                centered
                closable={false}
                transitionName=""
                maskTransitionName=""
            >
                <div style={{ 
                    display: 'flex', 
                    alignItems: 'flex-start', 
                    gap: '16px',
                    padding: '8px 0'
                }}>
                    {/* 警告图标 */}
                    <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '50%',
                        backgroundColor: '#fff2e8',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0
                    }}>
                        <span style={{ 
                            fontSize: '24px',
                            color: '#fa8c16'
                        }}>⚠</span>
                    </div>
                    
                    {/* 文本内容 */}
                    <div style={{ flex: 1 }}>
                        <h3 style={{ 
                            margin: '0 0 12px 0', 
                            fontSize: '16px', 
                            fontWeight: '600',
                            color: '#262626'
                        }}>
                            确认删除
                        </h3>
                        <p style={{ 
                            margin: '0 0 8px 0', 
                            fontSize: '14px',
                            color: '#595959',
                            lineHeight: '1.6'
                        }}>
                            确定要删除项目 <strong style={{ color: '#262626' }}>"{projectToDelete?.name}"</strong> 吗？
                        </p>
                        <p style={{ 
                            margin: 0, 
                            fontSize: '13px',
                            color: '#ff4d4f',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px'
                        }}>
                            <span style={{ fontSize: '16px' }}>⚠</span>
                            <span>此操作不可恢复！</span>
                        </p>
                    </div>
                </div>
            </Modal>
        </div>
    );
};

export default AutoDiscoveryConfig;
