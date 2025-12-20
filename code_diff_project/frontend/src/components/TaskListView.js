import React, { useState } from 'react';
import { Button, Table } from 'antd';
import { ClockCircleOutlined } from '@ant-design/icons';
import LogModal from './LogModal';

const TaskListView = ({ tasks }) => {
    const [logModalVisible, setLogModalVisible] = useState(false);
    const [currentLog, setCurrentLog] = useState('');

    const getStatusColor = (status) => {
        switch(status) {
            case 'COMPLETED': return 'text-green-600 bg-green-50 border-green-100';
            case 'FAILED': return 'text-red-600 bg-red-50 border-red-100';
            case 'PROCESSING': return 'text-blue-600 bg-blue-50 border-blue-100';
            default: return 'text-orange-600 bg-orange-50 border-orange-100'; // PENDING
        }
    };

    const showLog = (log) => {
        setCurrentLog(log);
        setLogModalVisible(true);
    };

    return (
        <div className="max-w-6xl mx-auto">
            <div className="mb-6 flex items-center justify-between">
                <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-3">
                    <ClockCircleOutlined className="text-blue-500" />
                    任务管理中心
                </h1>
                <div className="flex gap-2">
                    <span className="px-3 py-1 bg-slate-100 text-slate-600 rounded-full text-xs font-bold border border-slate-200">总计: {tasks.length}</span>
                    <span className="px-3 py-1 bg-green-50 text-green-600 rounded-full text-xs font-bold border border-green-100">成功: {tasks.filter(t=>t.status==='COMPLETED').length}</span>
                    <span className="px-3 py-1 bg-blue-50 text-blue-600 rounded-full text-xs font-bold border border-blue-100">进行中: {tasks.filter(t=>['PENDING','PROCESSING'].includes(t.status)).length}</span>
                </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <Table 
                    dataSource={tasks} 
                    rowKey="id"
                    pagination={{ pageSize: 10 }}
                    size="middle"
                    columns={[
                        { title: 'ID', dataIndex: 'id', width: 80, render: t => <span className="text-slate-400 font-mono">#{t}</span> },
                        { title: '项目名称', dataIndex: 'project_name', render: t => <span className="font-bold text-slate-700">{t}</span> },
                        { title: '模式', dataIndex: 'mode', width: 100, render: t => <span className="px-2 py-0.5 bg-slate-100 text-slate-500 rounded text-xs uppercase tracking-wider">{t}</span> },
                        { title: '提交时间', dataIndex: 'created_at', width: 180, render: t => <span className="text-slate-500 text-xs font-mono">{new Date(t).toLocaleString()}</span> },
                        { title: '状态', dataIndex: 'status', width: 120, render: t => {
                            const colorClass = getStatusColor(t);
                            return <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${colorClass}`}>{t}</span>;
                        }},
                        { title: '最新日志', dataIndex: 'log_details', render: t => (
                            <div className="text-xs text-slate-400 font-mono truncate max-w-md" title={t}>
                                {t ? t.trim().split('\n').pop() : '-'}
                            </div>
                        )},
                        {
                            title: '操作',
                            key: 'action',
                            width: 100,
                            render: (_, record) => (
                                <Button type="link" size="small" onClick={() => showLog(record.log_details)}>查看日志</Button>
                            )
                        }
                    ]}
                />
            </div>
            <LogModal 
                visible={logModalVisible} 
                onClose={() => setLogModalVisible(false)} 
                logContent={currentLog} 
            />
        </div>
    );
};

export default TaskListView;

