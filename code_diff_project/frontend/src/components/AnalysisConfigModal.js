import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, Button, Select, message, Switch, Tag } from 'antd';
import { 
    PlayCircleOutlined, GithubOutlined, BranchesOutlined, 
    ClockCircleOutlined, ArrowDownOutlined, InfoCircleOutlined,
    ApiOutlined
} from '@ant-design/icons';
import axios from 'axios';
import { REPORTS_URL, PROJECT_RELATIONS_URL } from '../utils/api';

const AnalysisConfigModal = ({ open, onClose, onSuccess }) => {
    const [form] = Form.useForm();
    const [loading, setLoading] = useState(false);
    const [branches, setBranches] = useState([]);
    const [fetchingBranches, setFetchingBranches] = useState(false);
    const [commits, setCommits] = useState([]);
    const [fetchingCommits, setFetchingCommits] = useState(false);
    const [enableCrossProject, setEnableCrossProject] = useState(false);
    const [relatedProjects, setRelatedProjects] = useState([]);
    const [fetchingRelatedProjects, setFetchingRelatedProjects] = useState(false);

    // Reset form when modal opens
    useEffect(() => {
        if (open) {
            form.resetFields();
            setBranches([]);
            setCommits([]);
            setEnableCrossProject(false);
            setRelatedProjects([]);
        }
    }, [open, form]);

    // 当跨项目分析开关变化时，查询关联项目
    useEffect(() => {
        if (enableCrossProject) {
            const gitUrl = form.getFieldValue('gitUrl');
            if (gitUrl) {
                fetchRelatedProjects(gitUrl);
            }
        } else {
            setRelatedProjects([]);
        }
    }, [enableCrossProject]);

    const fetchRelatedProjects = async (gitUrl) => {
        if (!gitUrl || !enableCrossProject) {
            setRelatedProjects([]);
            return;
        }
        
        try {
            setFetchingRelatedProjects(true);
            const res = await axios.get(`${PROJECT_RELATIONS_URL}by-main-project/`, {
                params: { main_git_url: gitUrl }
            });
            if (res.data && Array.isArray(res.data)) {
                const activeProjects = res.data.filter(p => p.is_active);
                setRelatedProjects(activeProjects);
                if (activeProjects.length > 0) {
                    message.success(`找到 ${activeProjects.length} 个关联项目`);
                }
            }
        } catch (error) {
            console.error('获取关联项目失败:', error);
            setRelatedProjects([]);
            // 不显示错误消息，因为可能只是没有配置关联项目
        } finally {
            setFetchingRelatedProjects(false);
        }
    };

    const handleGitUrlChange = (e) => {
        const gitUrl = e.target.value;
        if (enableCrossProject && gitUrl) {
            // 延迟查询，避免频繁请求
            const timer = setTimeout(() => {
                fetchRelatedProjects(gitUrl);
            }, 500);
            return () => clearTimeout(timer);
        }
    };

    const fetchGitBranches = async () => {
        try {
            const values = await form.validateFields(['gitUrl']);
            setFetchingBranches(true);
            const res = await axios.post(`${REPORTS_URL}git-branches/`, {
                git_url: values.gitUrl
            });
            if (res.data.branches) {
                setBranches(res.data.branches);
                message.success(`成功获取 ${res.data.branches.length} 个分支`);
            }
            
            // 如果启用了跨项目分析，同时获取关联项目
            if (enableCrossProject) {
                await fetchRelatedProjects(values.gitUrl);
            }
        } catch (error) {
            message.error('获取分支失败: ' + (error.response?.data?.error || error.message));
        } finally {
            setFetchingBranches(false);
        }
    };

    const fetchGitCommits = async (branch) => {
        try {
            const values = await form.validateFields(['gitUrl']);
            
            // Visual feedback: Clear current selection and show loading state
            setFetchingCommits(true);
            setCommits([]); 
            form.setFieldsValue({ baseCommit: undefined, targetCommit: undefined });

            const res = await axios.post(`${REPORTS_URL}git-commits/`, {
                git_url: values.gitUrl,
                branch: branch
            });
            if (res.data.commits) {
                setCommits(res.data.commits);
                message.success(`已加载 ${branch} 分支的 ${res.data.commits.length} 条提交记录`);
                
                // Smart defaults: Target=Latest, Base=Previous
                if (res.data.commits.length > 0) {
                    const latest = res.data.commits[0].hash;
                    const previous = res.data.commits.length > 1 ? res.data.commits[1].hash : latest;
                    form.setFieldsValue({ 
                        targetCommit: latest,
                        baseCommit: previous
                    });
                }
            }
        } catch (error) {
            message.error('获取提交记录失败: ' + (error.response?.data?.error || error.message));
        } finally {
            setFetchingCommits(false);
        }
    };

    const handleOk = async () => {
        try {
            const values = await form.validateFields();
            setLoading(true);
            // Close immediately to improve UX, let background handle it
            // Actually, we wait for the trigger response (fast) to confirm task creation
            const res = await axios.post(`${REPORTS_URL}trigger/`, {
                mode: 'git', 
                gitUrl: values.gitUrl,
                targetBranch: values.targetBranch,
                baseCommit: values.baseCommit,
                targetCommit: values.targetCommit,
                enableCrossProject: enableCrossProject  // 添加跨项目分析参数
            });
            
            if (res.data.status === 'Analysis started') {
                const successMsg = enableCrossProject && relatedProjects.length > 0
                    ? `任务已提交至后台队列（将扫描 ${relatedProjects.length} 个关联项目）`
                    : '任务已提交至后台队列';
                message.success(successMsg);
                onSuccess(); // Trigger task list refresh
                onClose();   // Close modal
            }
        } catch (error) {
            message.error('启动失败: ' + error.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Modal
            title={<span className="flex items-center gap-2"><PlayCircleOutlined className="text-blue-600"/> 新建分析任务</span>}
            open={open}
            onCancel={onClose}
            onOk={handleOk}
            confirmLoading={loading}
            okText="开始分析"
            cancelText="取消"
            okButtonProps={{ className: 'bg-blue-600 text-white hover:bg-blue-700 border-none' }}
            width={600}
        >
            <Form form={form} layout="vertical" initialValues={{ sourceBranch: undefined, targetBranch: undefined, gitUrl: '' }} className="space-y-3">
                
                <Form.Item name="gitUrl" label="Git 仓库地址" rules={[{ required: true, message: '请输入 Git 地址' }]} className="mb-2">
                    <Input 
                        prefix={<GithubOutlined className="text-slate-400"/>} 
                        placeholder="https://github.com/username/repo.git"
                        onChange={handleGitUrlChange}
                    />
                </Form.Item>
                <div className="flex gap-2 mb-2">
                        <Button onClick={fetchGitBranches} loading={fetchingBranches} icon={<BranchesOutlined />} size="small">
                        {fetchingBranches ? '获取中...' : '获取分支列表'}
                        </Button>
                </div>

                {/* 跨项目分析开关 */}
                <div className="bg-purple-50 p-3 rounded-lg border border-purple-200 mb-3">
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                            <ApiOutlined className="text-purple-600" />
                            <span className="font-semibold text-slate-700">跨项目影响分析</span>
                        </div>
                        <Switch 
                            checked={enableCrossProject}
                            onChange={setEnableCrossProject}
                            checkedChildren="启用"
                            unCheckedChildren="禁用"
                        />
                    </div>
                    <div className="text-xs text-slate-600 leading-relaxed">
                        启用后，系统将扫描所有关联项目，检测跨项目的 API 调用和类引用，帮助您全面了解代码变更的影响范围。
                    </div>
                    {enableCrossProject && relatedProjects.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-purple-200">
                            <div className="text-xs font-semibold text-slate-600 mb-2">
                                将扫描以下关联项目 ({relatedProjects.length}):
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {relatedProjects.map((project, index) => (
                                    <Tag key={index} color="purple" className="text-xs">
                                        {project.related_project_name}
                                        <span className="text-slate-400 ml-1">({project.related_project_branch})</span>
                                    </Tag>
                                ))}
                            </div>
                        </div>
                    )}
                    {enableCrossProject && relatedProjects.length === 0 && !fetchingRelatedProjects && (
                        <div className="mt-3 pt-3 border-t border-purple-200 text-xs text-orange-600">
                            <InfoCircleOutlined className="mr-1" />
                            未找到关联项目，请先在"项目关联管理"中配置关联关系。
                        </div>
                    )}
                </div>

                <div className="mb-2">
                    <Form.Item name="targetBranch" label="工作分支 (Working Branch)" rules={[{ required: true, message: '请选择工作分支' }]} className="mb-0">
                        <Select 
                            placeholder="选择要分析的分支"
                            showSearch 
                            allowClear
                            disabled={branches.length === 0 || fetchingBranches}
                            onChange={fetchGitCommits}
                        >
                            {branches.map(b => <Select.Option key={b} value={b}>{b}</Select.Option>)}
                        </Select>
                    </Form.Item>
                </div>

                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 mb-2">
                    <div className="text-xs font-bold text-slate-500 mb-2 flex items-center gap-2">
                        <ClockCircleOutlined /> 选择比对范围 (Commit Range)
                    </div>
                    <Form.Item name="baseCommit" label="起始提交 (Base Commit)" rules={[{ required: true, message: '请选择起始 Commit' }]} className="mb-2">
                        <Select 
                            placeholder={fetchingCommits ? "加载提交记录中..." : "选择起始提交"}
                            showSearch 
                            loading={fetchingCommits}
                            disabled={commits.length === 0}
                            optionLabelProp="label"
                            size="middle"
                        >
                            {commits.map(c => (
                                <Select.Option key={c.hash} value={c.hash} label={c.hash.substring(0,7)}>
                                    <div className="flex flex-col border-b border-slate-100 pb-1 mb-1 last:border-0">
                                        <div className="flex justify-between">
                                            <span className="font-mono font-bold text-blue-600">{c.hash.substring(0,7)}</span>
                                            <span className="text-xs text-slate-400">{c.date}</span>
                                        </div>
                                        <div className="text-xs text-slate-600 truncate" title={c.message}>{c.message}</div>
                                        <div className="text-[10px] text-slate-400">{c.author}</div>
                                    </div>
                                </Select.Option>
                            ))}
                        </Select>
                    </Form.Item>
                    <div className="flex justify-center -my-3 relative z-10">
                        <div className="bg-slate-50 p-1 rounded-full text-slate-300 text-sm"><ArrowDownOutlined /></div>
                    </div>
                    <Form.Item name="targetCommit" label="结束提交 (Target Commit)" rules={[{ required: true, message: '请选择结束 Commit' }]} className="mb-0">
                        <Select 
                            placeholder={fetchingCommits ? "加载提交记录中..." : "选择结束提交"}
                            showSearch 
                            loading={fetchingCommits}
                            disabled={commits.length === 0}
                            optionLabelProp="label"
                            size="middle"
                        >
                            {commits.map(c => (
                                <Select.Option key={c.hash} value={c.hash} label={c.hash.substring(0,7)}>
                                    <div className="flex flex-col border-b border-slate-100 pb-1 mb-1 last:border-0">
                                        <div className="flex justify-between">
                                            <span className="font-mono font-bold text-green-600">{c.hash.substring(0,7)}</span>
                                            <span className="text-xs text-slate-400">{c.date}</span>
                                        </div>
                                        <div className="text-xs text-slate-600 truncate" title={c.message}>{c.message}</div>
                                        <div className="text-[10px] text-slate-400">{c.author}</div>
                                    </div>
                                </Select.Option>
                            ))}
                        </Select>
                    </Form.Item>
                </div>

                <div className="bg-blue-50 p-2.5 rounded-lg text-xs text-blue-700 leading-relaxed">
                    <InfoCircleOutlined className="mr-1" /> 
                    系统将分析 <b>[工作分支]</b> 上，从 <b>[起始提交]</b> 到 <b>[结束提交]</b> 期间的代码变更。
                </div>
            </Form>
        </Modal>
    );
};

export default AnalysisConfigModal;

