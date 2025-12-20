import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, Switch, message, Popconfirm, Space, Tag } from 'antd';
import { 
    PlusOutlined, DeleteOutlined, EditOutlined, LinkOutlined, 
    CheckCircleOutlined, CloseCircleOutlined, FolderOpenOutlined 
} from '@ant-design/icons';
import axios from 'axios';
import { API_BASE } from '../utils/api';

const PROJECT_RELATIONS_URL = `${API_BASE}project-relations/`;

const ProjectRelations = () => {
    const [relations, setRelations] = useState([]);
    const [loading, setLoading] = useState(false);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingRelation, setEditingRelation] = useState(null);
    const [form] = Form.useForm();

    // 加载项目关联列表
    const fetchRelations = async () => {
        setLoading(true);
        try {
            const response = await axios.get(PROJECT_RELATIONS_URL);
            setRelations(response.data);
        } catch (error) {
            console.error('加载项目关联失败:', error);
            message.error('加载项目关联失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchRelations();
    }, []);

    // 打开添加/编辑模态框
    const handleOpenModal = (relation = null) => {
        setEditingRelation(relation);
        if (relation) {
            form.setFieldsValue(relation);
        } else {
            form.resetFields();
            form.setFieldsValue({ 
                related_project_branch: 'master',
                is_active: true 
            });
        }
        setIsModalOpen(true);
    };

    // 关闭模态框
    const handleCloseModal = () => {
        setIsModalOpen(false);
        setEditingRelation(null);
        form.resetFields();
    };

    // 提交表单（创建或更新）
    const handleSubmit = async () => {
        try {
            const values = await form.validateFields();
            
            if (editingRelation) {
                // 更新
                await axios.put(`${PROJECT_RELATIONS_URL}${editingRelation.id}/`, values);
                message.success('更新项目关联成功');
            } else {
                // 创建
                await axios.post(PROJECT_RELATIONS_URL, values);
                message.success('创建项目关联成功');
            }
            
            handleCloseModal();
            fetchRelations();
        } catch (error) {
            console.error('保存项目关联失败:', error);
            if (error.response?.data) {
                // 显示后端返回的错误信息
                const errorMsg = Object.values(error.response.data).flat().join(', ');
                message.error(`保存失败: ${errorMsg}`);
            } else {
                message.error('保存项目关联失败');
            }
        }
    };

    // 删除项目关联
    const handleDelete = async (id) => {
        try {
            await axios.delete(`${PROJECT_RELATIONS_URL}${id}/`);
            message.success('删除项目关联成功');
            fetchRelations();
        } catch (error) {
            console.error('删除项目关联失败:', error);
            message.error('删除项目关联失败');
        }
    };

    // 切换启用/禁用状态
    const handleToggleActive = async (relation) => {
        try {
            await axios.patch(`${PROJECT_RELATIONS_URL}${relation.id}/`, {
                is_active: !relation.is_active
            });
            message.success(`已${relation.is_active ? '禁用' : '启用'}项目关联`);
            fetchRelations();
        } catch (error) {
            console.error('切换状态失败:', error);
            message.error('切换状态失败');
        }
    };

    // 表格列定义
    const columns = [
        {
            title: 'ID',
            dataIndex: 'id',
            key: 'id',
            width: 50,
            fixed: 'left',
            render: (text) => <span className="font-mono text-slate-400 text-xs">#{text}</span>
        },
        {
            title: '主项目',
            dataIndex: 'main_project_name',
            key: 'main_project_name',
            width: 100,
            ellipsis: true,
            render: (text) => <span className="font-medium text-xs" title={text}>{text}</span>
        },
        {
            title: '主项目 Git',
            dataIndex: 'main_project_git_url',
            key: 'main_project_git_url',
            width: 180,
            ellipsis: true,
            render: (text) => (
                <span className="font-mono text-xs text-slate-600" title={text}>
                    {text}
                </span>
            )
        },
        {
            title: '关联项目',
            dataIndex: 'related_project_name',
            key: 'related_project_name',
            width: 100,
            ellipsis: true,
            render: (text) => <span className="font-medium text-xs" title={text}>{text}</span>
        },
        {
            title: '关联 Git',
            dataIndex: 'related_project_git_url',
            key: 'related_project_git_url',
            width: 180,
            ellipsis: true,
            render: (text) => (
                <span className="font-mono text-xs text-slate-600" title={text}>
                    {text}
                </span>
            )
        },
        {
            title: '分支',
            dataIndex: 'related_project_branch',
            key: 'related_project_branch',
            width: 70,
            render: (text) => <Tag color="blue" className="text-xs">{text}</Tag>
        },
        {
            title: '状态',
            dataIndex: 'is_active',
            key: 'is_active',
            width: 60,
            render: (isActive) => (
                <Tag 
                    icon={isActive ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                    color={isActive ? 'success' : 'default'}
                    className="text-xs"
                >
                    {isActive ? '启用' : '禁用'}
                </Tag>
            )
        },
        {
            title: '创建时间',
            dataIndex: 'created_at',
            key: 'created_at',
            width: 110,
            render: (text) => (
                <span className="text-xs text-slate-400">
                    {new Date(text).toLocaleString('zh-CN', { 
                        month: '2-digit', 
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit'
                    })}
                </span>
            )
        },
        {
            title: '操作',
            key: 'action',
            width: 170,
            fixed: 'right',
            render: (_, record) => (
                <Space size="small">
                    <Button 
                        type="link" 
                        size="small" 
                        icon={<EditOutlined />}
                        onClick={() => handleOpenModal(record)}
                        style={{ padding: '0 4px' }}
                    >
                        编辑
                    </Button>
                    <Switch 
                        size="small"
                        checked={record.is_active}
                        onChange={() => handleToggleActive(record)}
                    />
                    <Popconfirm
                        title="确认删除"
                        description="确定要删除这个项目关联吗？"
                        onConfirm={() => handleDelete(record.id)}
                        okText="确定"
                        cancelText="取消"
                    >
                        <Button 
                            type="link" 
                            danger 
                            size="small" 
                            icon={<DeleteOutlined />}
                            style={{ padding: '0 4px' }}
                        >
                            删除
                        </Button>
                    </Popconfirm>
                </Space>
            )
        }
    ];

    return (
        <div style={{ width: '100%', padding: '0', overflow: 'visible' }}>
            {/* 添加按钮 - 独立行 */}
            <div style={{ 
                marginBottom: '16px', 
                display: 'flex', 
                justifyContent: 'flex-end',
                padding: '0 16px'
            }}>
                <Button 
                    type="primary" 
                    icon={<PlusOutlined />}
                    onClick={() => handleOpenModal()}
                    size="large"
                    style={{
                        backgroundColor: '#1890ff',
                        borderColor: '#1890ff',
                        fontSize: '16px',
                        height: '40px',
                        padding: '0 24px'
                    }}
                >
                    添加项目关联
                </Button>
            </div>

            {/* 表格区域 */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm" style={{ overflow: 'auto' }}>
                {/* 表格标题栏 */}
                <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
                    <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                        <LinkOutlined className="text-blue-500" />
                        项目关联列表
                    </h2>
                    <p className="text-xs text-slate-500 mt-1">
                        配置主项目与关联项目的依赖关系，用于跨项目影响分析
                    </p>
                </div>
                
                {/* 表格内容 */}
                <div style={{ overflowX: 'auto', width: '100%' }}>
                    <Table 
                        columns={columns}
                        dataSource={relations}
                        rowKey="id"
                        loading={loading}
                        pagination={{
                            pageSize: 10,
                            showSizeChanger: true,
                            showQuickJumper: true,
                            showTotal: (total) => `共 ${total} 条记录`
                        }}
                        scroll={{ x: 1020 }}
                        size="small"
                    />
                </div>
            </div>

            {/* 添加/编辑模态框 */}
            <Modal
                title={
                    <div className="flex items-center gap-2">
                        <LinkOutlined className="text-blue-500" />
                        <span>{editingRelation ? '编辑项目关联' : '添加项目关联'}</span>
                    </div>
                }
                open={isModalOpen}
                onOk={handleSubmit}
                onCancel={handleCloseModal}
                width={700}
                okText="保存"
                cancelText="取消"
            >
                <Form
                    form={form}
                    layout="vertical"
                    className="mt-4"
                >
                    <Form.Item
                        label="主项目名称"
                        name="main_project_name"
                        rules={[
                            { required: true, message: '请输入主项目名称' },
                            { max: 255, message: '名称不能超过255个字符' }
                        ]}
                    >
                        <Input 
                            placeholder="例如: beehive-order-finance" 
                            prefix={<FolderOpenOutlined className="text-slate-400" />}
                        />
                    </Form.Item>

                    <Form.Item
                        label="主项目 Git 地址"
                        name="main_project_git_url"
                        rules={[
                            { required: true, message: '请输入主项目 Git 地址' },
                            { max: 500, message: 'Git 地址不能超过500个字符' }
                        ]}
                    >
                        <Input 
                            placeholder="例如: git@git.example.com:org/main-project.git" 
                            className="font-mono text-xs"
                        />
                    </Form.Item>

                    <Form.Item
                        label="关联项目名称"
                        name="related_project_name"
                        rules={[
                            { required: true, message: '请输入关联项目名称' },
                            { max: 255, message: '名称不能超过255个字符' }
                        ]}
                    >
                        <Input 
                            placeholder="例如: cloudE-master" 
                            prefix={<LinkOutlined className="text-slate-400" />}
                        />
                    </Form.Item>

                    <Form.Item
                        label="关联项目 Git 地址"
                        name="related_project_git_url"
                        rules={[
                            { required: true, message: '请输入关联项目 Git 地址' },
                            { max: 500, message: 'Git 地址不能超过500个字符' }
                        ]}
                    >
                        <Input 
                            placeholder="例如: git@git.example.com:org/related-project.git" 
                            className="font-mono text-xs"
                        />
                    </Form.Item>

                    <Form.Item
                        label="关联项目分支"
                        name="related_project_branch"
                        rules={[
                            { required: true, message: '请输入分支名称' },
                            { max: 100, message: '分支名称不能超过100个字符' }
                        ]}
                    >
                        <Input 
                            placeholder="例如: master 或 develop" 
                            className="font-mono text-xs"
                        />
                    </Form.Item>

                    <Form.Item
                        label="启用状态"
                        name="is_active"
                        valuePropName="checked"
                    >
                        <Switch 
                            checkedChildren="启用" 
                            unCheckedChildren="禁用"
                        />
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    );
};

export default ProjectRelations;
