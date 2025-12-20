import React from 'react';
import { Modal, Button } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';

const LogModal = ({ visible, onClose, logContent }) => {
    return (
        <Modal
            title={<span className="flex items-center gap-2"><FileTextOutlined /> 任务执行日志</span>}
            open={visible}
            onCancel={onClose}
            width={800}
            footer={[
                <Button key="close" onClick={onClose}>关闭</Button>
            ]}
        >
            <div className="bg-slate-900 text-slate-300 p-4 rounded-lg font-mono text-xs h-[500px] overflow-y-auto whitespace-pre-wrap leading-relaxed">
                {logContent || '暂无日志信息'}
            </div>
        </Modal>
    );
};

export default LogModal;

