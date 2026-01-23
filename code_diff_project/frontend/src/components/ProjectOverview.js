import React, { useState, useMemo } from 'react';
import { Button, Table, Pagination, Tooltip } from 'antd';
import { 
    FolderOpenOutlined, BranchesOutlined, DeploymentUnitOutlined, InfoCircleOutlined, 
    FileTextOutlined, ClockCircleOutlined 
} from '@ant-design/icons';

const ProjectOverview = ({ projectName, reports = [], onSelectReport }) => {
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);

    // Group reports by Task ID (preferred) or time
    const groupedReports = useMemo(() => {
        const groups = {};
        reports.forEach(r => {
            let key;
            if (r.task && r.task.id) {
                // Group by Task ID ONLY to avoid splitting due to analysis time diff
                // task 现在是一个对象，需要使用 task.id
                key = `Task #${r.task.id}`;
            } else {
                // Fallback to fuzzy time grouping
                const date = new Date(r.created_at);
                key = `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')} ${String(date.getHours()).padStart(2,'0')}:${String(date.getMinutes()).padStart(2,'0')}`;
            }
            
            if (!groups[key]) groups[key] = [];
            groups[key].push(r);
        });
        
        // Debug: Log grouping results
        console.log('[ProjectOverview] Grouped reports:', groups);
        
        // Sort keys: Task IDs desc, then time strings desc
        return Object.entries(groups).sort((a, b) => {
            // Extract numbers if Task ID
            const taskMatchA = a[0].match(/Task #(\d+)/);
            const taskMatchB = b[0].match(/Task #(\d+)/);
            
            if (taskMatchA && taskMatchB) {
                return parseInt(taskMatchB[1]) - parseInt(taskMatchA[1]);
            }
            return b[0].localeCompare(a[0]);
        });
    }, [reports]);

    // Calculate pagination
    const totalTasks = groupedReports.length;
    const currentTasks = groupedReports.slice((currentPage - 1) * pageSize, currentPage * pageSize);

    return (
        <div className="max-w-6xl mx-auto">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-3">
                    <FolderOpenOutlined className="text-blue-500" />
                    {projectName}
                </h1>
                <p className="text-slate-500 mt-2">该项目共检测到 {reports.length} 个文件变更记录，共 {totalTasks} 个分析批次。</p>
            </div>
            
            <div className="space-y-4 pb-10">
                {currentTasks.map(([batchKey, groupReports], idx) => {
                    // Global index for display
                    const globalIdx = (currentPage - 1) * pageSize + idx;
                    
                    // Calculate representative time for the batch (use the first/earliest file time)
                    const firstTime = new Date(Math.min(...groupReports.map(r => new Date(r.created_at))));
                    const timeDisplay = firstTime.toLocaleString();

                    // Get task info from the first report
                    const firstReport = groupReports[0] || {};
                    const branchName = firstReport.source_branch;
                    const commitRange = firstReport.target_branch;

                    return (
                    <div key={batchKey} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden hover:shadow-md transition-shadow">
                        <div className="bg-slate-50 px-5 py-3 border-b border-slate-100 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center text-sm font-bold">
                                    {globalIdx + 1}
                                </div>
                                <div>
                                    <span className="font-bold text-slate-700 text-sm flex items-center flex-wrap gap-2">
                                        <span>分析批次: {batchKey}</span>
                                        {(branchName || commitRange) && (
                                            <span className="inline-flex items-center gap-2 px-2 py-0.5 bg-indigo-50 border border-indigo-100 rounded text-xs text-indigo-600 font-mono font-normal">
                                                {branchName && (
                                                    <span className="flex items-center gap-1">
                                                        <BranchesOutlined /> {branchName}
                                                    </span>
                                                )}
                                                {branchName && commitRange && <span className="text-indigo-700">/</span>}
                                                {commitRange && (() => {
                                                    // Parse commit range: "hash1 -> hash2"
                                                    const parts = commitRange.split(' -> ');
                                                    const baseCommit = parts[0] ? parts[0].trim() : '';
                                                    const targetCommit = parts[1] ? parts[1].trim() : '';
                                                    
                                                    // 从 task 中获取 commit 详细信息
                                                    const baseCommitMessage = groupReports[0]?.task?.base_commit_message || '';
                                                    const baseCommitAuthor = groupReports[0]?.task?.base_commit_author || '';
                                                    const baseCommitDate = groupReports[0]?.task?.base_commit_date || '';
                                                    const targetCommitMessage = groupReports[0]?.task?.target_commit_message || '';
                                                    const targetCommitAuthor = groupReports[0]?.task?.target_commit_author || '';
                                                    const targetCommitDate = groupReports[0]?.task?.target_commit_date || '';
                                                    
                                                    // 构建详细的 tooltip 内容
                                                    const tooltipContent = (
                                                        <div className="space-y-3 text-xs">
                                                            <div className="font-bold text-sm border-b border-slate-200 pb-2">提交对比信息</div>
                                                            
                                                            {/* 基准提交 */}
                                                            <div className="space-y-1">
                                                                <div className="font-semibold text-orange-400">基准提交 ({baseCommit})</div>
                                                                {baseCommitMessage && (
                                                                    <div className="pl-2 border-l-2 border-orange-200">
                                                                        <div className="text-slate-200">
                                                                            <span className="text-slate-400">提交信息：</span>{baseCommitMessage}
                                                                        </div>
                                                                        {baseCommitAuthor && (
                                                                            <div className="text-slate-300">
                                                                                <span className="text-slate-400">作者：</span>{baseCommitAuthor}
                                                                            </div>
                                                                        )}
                                                                        {baseCommitDate && (
                                                                            <div className="text-slate-300">
                                                                                <span className="text-slate-400">时间：</span>{baseCommitDate}
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                )}
                                                            </div>
                                                            
                                                            {/* 目标提交 */}
                                                            <div className="space-y-1">
                                                                <div className="font-semibold text-green-400">目标提交 ({targetCommit})</div>
                                                                {targetCommitMessage && (
                                                                    <div className="pl-2 border-l-2 border-green-200">
                                                                        <div className="text-slate-200">
                                                                            <span className="text-slate-400">提交信息：</span>{targetCommitMessage}
                                                                        </div>
                                                                        {targetCommitAuthor && (
                                                                            <div className="text-slate-300">
                                                                                <span className="text-slate-400">作者：</span>{targetCommitAuthor}
                                                                            </div>
                                                                        )}
                                                                        {targetCommitDate && (
                                                                            <div className="text-slate-300">
                                                                                <span className="text-slate-400">时间：</span>{targetCommitDate}
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                )}
                                                            </div>
                                                            
                                                            {!baseCommitMessage && !targetCommitMessage && (
                                                                <div className="text-slate-400 text-center py-2">
                                                                    暂无详细提交信息
                                                                </div>
                                                            )}
                                                        </div>
                                                    );

                                                    return (
                                                        <span className="flex items-center gap-1">
                                                            <DeploymentUnitOutlined /> 
                                                            {commitRange}
                                                            <Tooltip 
                                                                title={tooltipContent}
                                                                placement="bottomRight"
                                                                overlayInnerStyle={{ 
                                                                    width: 'max-content', 
                                                                    maxWidth: '500px',
                                                                    backgroundColor: '#1e293b',
                                                                    borderRadius: '8px',
                                                                    padding: '12px'
                                                                }}
                                                                overlayStyle={{
                                                                    zIndex: 9999
                                                                }}
                                                                color="#1e293b"
                                                                getPopupContainer={(trigger) => document.body}
                                                            >
                                                                <InfoCircleOutlined className="text-indigo-700 cursor-help hover:text-indigo-900 ml-1" />
                                                            </Tooltip>
                                                        </span>
                                                    );
                                                })()}
                                            </span>
                                        )}
                                    </span>
                                    <span className="text-[10px] text-slate-400">批次生成时间: {timeDisplay}</span>
                                </div>
                            </div>
                            <span className="text-xs font-medium text-blue-600 bg-blue-50 px-3 py-1 rounded-full border border-blue-100">
                                {groupReports.length} 个变更文件
                            </span>
                        </div>
                        
                        <div className="p-0">
                        <Table 
                            dataSource={groupReports} 
                            rowKey="id"
                            pagination={{ pageSize: 10 }}
                            size="middle"
                            className="no-border-table"
                            columns={[
                                {
                                    title: 'ID',
                                    dataIndex: 'id',
                                    width: 80,
                                    render: (text) => <span className="font-mono text-slate-400">#{text}</span>
                                },
                                {
                                    title: '风险等级',
                                    dataIndex: 'risk_level',
                                    width: 100,
                                    render: (level) => {
                                        const colors = { 
                                            'CRITICAL': 'bg-red-500 text-white border-red-600', 
                                            'HIGH': 'bg-orange-500 text-white border-orange-600', 
                                            'MEDIUM': 'bg-yellow-500 text-white border-yellow-600', 
                                            'LOW': 'bg-green-500 text-white border-green-600',
                                            '严重': 'bg-red-500 text-white border-red-600', 
                                            '高': 'bg-orange-500 text-white border-orange-600', 
                                            '中': 'bg-yellow-500 text-white border-yellow-600', 
                                            '低': 'bg-green-500 text-white border-green-600'
                                        };
                                        const colorClass = colors[level] || 'bg-slate-500 text-white border-slate-600';
                                        return (
                                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${colorClass} shadow-sm`}>
                                                {level}
                                            </span>
                                        );
                                    }
                                },
                                {
                                    title: '变更文件',
                                    dataIndex: 'file_name',
                                    width: 250,
                                    render: (text, record) => (
                                        <a onClick={() => onSelectReport(record.id)} className="font-medium text-blue-600 hover:underline flex items-center gap-2">
                                            <FileTextOutlined /> {text}
                                        </a>
                                    )
                                },
                                {
                                    title: '变更详情',
                                    dataIndex: 'change_intent',
                                    render: (text) => {
                                        if (!text) {
                                            return <span className="text-slate-300 italic text-xs">暂无描述</span>;
                                        }
                                        
                                        // 尝试解析JSON
                                        try {
                                            const data = typeof text === 'string' ? JSON.parse(text) : text;
                                            
                                            // 如果是数组（符合后端定义）
                                            if (Array.isArray(data) && data.length > 0) {
                                                // 显示所有变更点的摘要
                                                return (
                                                    <div className="text-xs text-slate-600 max-w-xl space-y-1">
                                                        {data.map((item, index) => {
                                                            const summary = item.summary || '';
                                                            if (!summary) return null;
                                                            
                                                            return (
                                                                <div key={index} className="flex items-start gap-1">
                                                                    <span className="text-slate-400 mt-0.5">•</span>
                                                                    <span className="flex-1 line-clamp-1" title={summary}>
                                                                        {summary}
                                                                    </span>
                                                                </div>
                                                            );
                                                        })}
                                                        {data.every(item => !item.summary) && (
                                                            <span className="text-slate-400 italic">无详细描述</span>
                                                        )}
                                                    </div>
                                                );
                                            }
                                            
                                            // 如果是对象（兼容旧格式）
                                            if (typeof data === 'object' && data !== null) {
                                                const summary = data.summary || data.description || data.intent || '';
                                                const details = data.details || '';
                                                
                                                return (
                                                    <div className="text-xs text-slate-600 max-w-xl">
                                                        {summary && (
                                                            <div className="line-clamp-2" title={summary}>
                                                                {summary}
                                                            </div>
                                                        )}
                                                        {!summary && details && (
                                                            <div className="line-clamp-2" title={details}>
                                                                {details}
                                                            </div>
                                                        )}
                                                        {!summary && !details && (
                                                            <span className="text-slate-400 italic">无详细描述</span>
                                                        )}
                                                    </div>
                                                );
                                            }
                                            
                                            // 如果是字符串，直接显示
                                            return (
                                                <div className="text-xs text-slate-600 line-clamp-2 max-w-xl" title={String(data)}>
                                                    {String(data)}
                                                </div>
                                            );
                                        } catch (e) {
                                            // 如果不是JSON，直接显示原文本
                                            return (
                                                <div className="text-xs text-slate-600 line-clamp-2 max-w-xl" title={text}>
                                                    {text}
                                                </div>
                                            );
                                        }
                                    }
                                },
                                {
                                    title: '操作',
                                    key: 'action',
                                    width: 100,
                                    render: (_, record) => (
                                        <Button type="link" size="small" onClick={() => onSelectReport(record.id)}>查看详情</Button>
                                    )
                                }
                            ]}
                        />
                    </div>
                </div>
                );
            })}
            </div>
            
            {/* Pagination for Tasks */}
            {totalTasks > 0 && (
                <div className="flex justify-end mt-6 pb-8 px-4">
                    <Pagination 
                        current={currentPage} 
                        total={totalTasks} 
                        pageSize={pageSize}
                        showSizeChanger={true}
                        showQuickJumper
                        pageSizeOptions={['10', '20', '50', '100']}
                        onChange={(page, size) => {
                            setCurrentPage(page);
                            setPageSize(size);
                            window.scrollTo({ top: 0, behavior: 'smooth' });
                        }} 
                        showTotal={(total, range) => `显示 ${range[0]}-${range[1]} 条，共 ${total} 条`}
                    />
                </div>
            )}
        </div>
    );
};

export default ProjectOverview;

