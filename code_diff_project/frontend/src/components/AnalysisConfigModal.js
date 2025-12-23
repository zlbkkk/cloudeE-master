import React, { useState, useEffect, useRef } from 'react';
import { Modal, Form, Input, Select, message, Switch } from 'antd';
import { 
    PlayCircleOutlined, GithubOutlined, BranchesOutlined, 
    ClockCircleOutlined, ArrowDownOutlined, InfoCircleOutlined,
    ApiOutlined  // 启用跨项目分析功能
} from '@ant-design/icons';
import axios from 'axios';
import { REPORTS_URL, API_BASE } from '../utils/api';

const DISCOVERED_PROJECTS_URL = `${API_BASE}discovered-projects/`;

const AnalysisConfigModal = ({ open, onClose, onSuccess }) => {
    const [form] = Form.useForm();
    const [loading, setLoading] = useState(false);
    const [branches, setBranches] = useState([]);
    const [fetchingBranches, setFetchingBranches] = useState(false);
    const [commits, setCommits] = useState([]);
    const [fetchingCommits, setFetchingCommits] = useState(false);
    const [enableCrossProject, setEnableCrossProject] = useState(false);
    const [allProjects, setAllProjects] = useState([]);
    const [selectedProjects, setSelectedProjects] = useState([]);
    const [fetchingProjects, setFetchingProjects] = useState(false);
    const debounceTimerRef = useRef(null);

    // Reset form when modal opens
    useEffect(() => {
        if (open) {
            form.resetFields();
            setBranches([]);
            setCommits([]);
            setEnableCrossProject(false);
            setSelectedProjects([]);
            // 加载所有可用项目
            fetchAllProjects();
        }
        
        // 清理防抖定时器
        return () => {
            if (debounceTimerRef.current) {
                clearTimeout(debounceTimerRef.current);
            }
        };
    }, [open, form]);

    // 获取所有已发现的项目
    const fetchAllProjects = async () => {
        try {
            setFetchingProjects(true);
            const res = await axios.get(DISCOVERED_PROJECTS_URL);
            if (res.data && Array.isArray(res.data)) {
                const activeProjects = res.data.filter(p => p.is_active);
                console.log('加载的项目列表:', activeProjects);
                setAllProjects(activeProjects);
            }
        } catch (error) {
            console.error('获取项目列表失败:', error);
            message.error('获取项目列表失败');
        } finally {
            setFetchingProjects(false);
        }
    };

    // 验证 Git URL 是否完整
    const isValidGitUrl = (url) => {
        if (!url || url.trim() === '') return false;
        
        // 支持的格式:
        // https://github.com/username/repo.git
        // https://github.com/username/repo
        // git@github.com:username/repo.git
        // https://gitlab.com/username/repo.git
        
        const httpsPattern = /^https?:\/\/[^\s/$.?#].[^\s]*\/[^\s/]+\/[^\s/]+/;
        const sshPattern = /^git@[^\s:]+:[^\s/]+\/[^\s/]+/;
        
        return httpsPattern.test(url) || sshPattern.test(url);
    };

    // 监听 Git 地址变化，清空分支和提交列表，并过滤掉当前项目
    const handleGitUrlChange = (e) => {
        const newGitUrl = e.target.value;
        const oldGitUrl = form.getFieldValue('gitUrl');
        
        // 立即清空分支、提交和表单字段（无论 URL 是否真的变化）
        setBranches([]);
        setCommits([]);
        form.setFieldsValue({
            targetBranch: undefined,
            baseCommit: undefined,
            targetCommit: undefined
        });
        
        // 如果 Git 地址发生变化，清空所有已选择的关联项目
        // 采用保守策略：URL 变化就清空，避免用户混淆
        if (newGitUrl !== oldGitUrl) {
            setSelectedProjects([]);
        }
        
        // 清除之前的防抖定时器
        if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current);
        }
        
        // 设置新的防抖定时器
        debounceTimerRef.current = setTimeout(() => {
            // 验证 URL 格式
            if (isValidGitUrl(newGitUrl)) {
                // 自动触发获取分支列表
                fetchGitBranches();
            }
        }, 800); // 800ms 防抖延迟
    };

    // 从Git URL中提取组织名称
    const extractOrgFromGitUrl = (gitUrl) => {
        if (!gitUrl) return null;
        
        try {
            // 支持多种格式:
            // https://github.com/zlbkkk/service-b.git
            // https://git.hrlyit.com/beehive/project-name.git
            // git@github.com:zlbkkk/service-b.git
            
            // 移除 .git 后缀
            let url = gitUrl.replace(/\.git$/, '');
            
            // 处理 SSH 格式 (git@github.com:org/repo)
            if (url.includes('@')) {
                const parts = url.split(':');
                if (parts.length >= 2) {
                    const pathParts = parts[1].split('/');
                    return pathParts[0];
                }
            }
            
            // 处理 HTTPS 格式 (https://github.com/org/repo)
            const urlObj = new URL(url);
            const pathParts = urlObj.pathname.split('/').filter(p => p);
            
            // 通常组织名是路径的第一部分
            if (pathParts.length >= 1) {
                return pathParts[0];
            }
        } catch (error) {
            console.error('解析Git URL失败:', error);
        }
        
        return null;
    };

    // 标准化 Git URL（移除 .git 后缀，用于比较）
    const normalizeGitUrl = (url) => {
        if (!url) return '';
        return url.trim().replace(/\.git$/i, '').toLowerCase();
    };

    // 获取同组织的项目列表
    const getSameOrgProjects = () => {
        const currentGitUrl = form.getFieldValue('gitUrl');
        if (!currentGitUrl) return allProjects;
        
        const currentOrg = extractOrgFromGitUrl(currentGitUrl);
        if (!currentOrg) return allProjects;
        
        // 标准化当前 URL 用于比较
        const normalizedCurrentUrl = normalizeGitUrl(currentGitUrl);
        
        // 过滤出同组织的项目（排除当前项目）
        return allProjects.filter(p => {
            // 标准化后比较，忽略 .git 后缀和大小写
            if (normalizeGitUrl(p.git_url) === normalizedCurrentUrl) return false;
            const projectOrg = extractOrgFromGitUrl(p.git_url);
            return projectOrg === currentOrg;
        });
    };

    const fetchGitBranches = async () => {
        try {
            const values = await form.validateFields(['gitUrl']);
            setFetchingBranches(true);
            
            // 设置 30 秒超时
            const timeout = 30000;
            const timeoutPromise = new Promise((_, reject) => 
                setTimeout(() => reject(new Error('请求超时')), timeout)
            );
            
            const fetchPromise = axios.post(`${REPORTS_URL}git-branches/`, {
                git_url: values.gitUrl
            });
            
            // 使用 Promise.race 实现超时
            const res = await Promise.race([fetchPromise, timeoutPromise]);
            
            if (res.data.branches) {
                setBranches(res.data.branches);
                message.success(`成功获取 ${res.data.branches.length} 个分支`);
            }
        } catch (error) {
            // 先显示错误提示，再清空数据
            if (error.message === '请求超时') {
                message.error({
                    content: '获取分支超时，请检查 Git 地址是否正确或网络连接',
                    duration: 5 // 显示 5 秒
                });
            } else {
                message.error({
                    content: '获取分支失败，请检查 Git 地址: ' + (error.response?.data?.error || error.message),
                    duration: 5 // 显示 5 秒
                });
            }
            
            // 延迟清空，让用户先看到提示
            setTimeout(() => {
                setSelectedProjects([]);
            }, 300);
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
            
            // 准备跨项目分析的项目列表
            const crossProjectList = enableCrossProject && selectedProjects.length > 0
                ? selectedProjects.map(id => {
                    const project = allProjects.find(p => p.id === id);
                    if (!project) {
                        console.error(`未找到ID为 ${id} 的项目`);
                        return null;
                    }
                    if (!project.git_url) {
                        console.error(`项目 ${project.project_name} 缺少 git_url`);
                        return null;
                    }
                    // 使用后端期望的字段名
                    return {
                        related_project_name: project.project_name,
                        related_project_git_url: project.git_url,
                        related_project_branch: project.default_branch || 'master'
                    };
                }).filter(p => p !== null)  // 过滤掉无效的项目
                : [];
            
            console.log('准备提交的跨项目列表:', crossProjectList);
            
            const res = await axios.post(`${REPORTS_URL}trigger/`, {
                mode: 'git', 
                gitUrl: values.gitUrl,
                targetBranch: values.targetBranch,
                baseCommit: values.baseCommit,
                targetCommit: values.targetCommit,
                enableCrossProject: enableCrossProject,
                crossProjectList: crossProjectList
            });
            
            if (res.data.status === 'Analysis started') {
                const successMsg = enableCrossProject && crossProjectList.length > 0
                    ? `任务已提交至后台队列（将扫描 ${crossProjectList.length} 个关联项目）`
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
                        suffix={
                            fetchingBranches && (
                                <span className="text-xs text-blue-600 flex items-center gap-1">
                                    <BranchesOutlined className="animate-pulse" />
                                    获取分支中...
                                </span>
                            )
                        }
                    />
                </Form.Item>

                {/* 跨项目分析功能 */}
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
                    <div className="text-xs text-slate-600 leading-relaxed mb-2">
                        启用后，系统将扫描选中的关联项目，检测跨项目的 API 调用和类引用，帮助您全面了解代码变更的影响范围。
                    </div>
                    {enableCrossProject && (
                        <div className="mt-3 pt-3 border-t border-purple-200">
                            <div className="text-xs font-semibold text-slate-600 mb-2">
                                选择要扫描的关联项目 (同组织):
                            </div>
                            <Select
                                mode="multiple"
                                style={{ width: '100%' }}
                                placeholder={fetchingBranches ? "等待 Git URL 验证..." : "请选择关联项目"}
                                value={selectedProjects}
                                onChange={setSelectedProjects}
                                loading={fetchingProjects}
                                disabled={fetchingBranches || !isValidGitUrl(form.getFieldValue('gitUrl'))}
                                optionFilterProp="children"
                                filterOption={(input, option) =>
                                    option.children.toLowerCase().includes(input.toLowerCase())
                                }
                            >
                                {getSameOrgProjects().map(project => (
                                    <Select.Option key={project.id} value={project.id}>
                                        {project.project_name} ({project.default_branch || 'master'})
                                    </Select.Option>
                                ))}
                            </Select>
                            {fetchingBranches && (
                                <div className="mt-2 text-xs text-blue-600">
                                    <InfoCircleOutlined className="mr-1" />
                                    正在验证 Git 地址，请稍候...
                                </div>
                            )}
                            {!isValidGitUrl(form.getFieldValue('gitUrl')) && !fetchingBranches && form.getFieldValue('gitUrl') && (
                                <div className="mt-2 text-xs text-orange-600">
                                    <InfoCircleOutlined className="mr-1" />
                                    请输入完整的 Git 地址
                                </div>
                            )}
                            {selectedProjects.length > 0 && (
                                <div className="mt-2 text-xs text-slate-600">
                                    已选择 {selectedProjects.length} 个项目
                                </div>
                            )}
                            {getSameOrgProjects().length === 0 && form.getFieldValue('gitUrl') && isValidGitUrl(form.getFieldValue('gitUrl')) && !fetchingBranches && (
                                <div className="mt-2 text-xs text-orange-600">
                                    <InfoCircleOutlined className="mr-1" />
                                    未找到同组织的其他项目
                                </div>
                            )}
                        </div>
                    )}
                    {enableCrossProject && allProjects.length === 0 && !fetchingProjects && (
                        <div className="mt-3 pt-3 border-t border-purple-200 text-xs text-orange-600">
                            <InfoCircleOutlined className="mr-1" />
                            未找到可用项目，请先在"项目集配置"中采集项目。
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

