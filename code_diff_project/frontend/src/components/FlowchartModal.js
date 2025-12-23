import React from 'react';
import { Modal, Tooltip } from 'antd';
import { 
    BranchesOutlined, DeploymentUnitOutlined, ApiOutlined, ArrowDownOutlined, 
    AppstoreOutlined, CodeOutlined, FileTextOutlined, BugOutlined, InfoCircleOutlined 
} from '@ant-design/icons';
import CollapsibleCodeSnippet from './CollapsibleCodeSnippet';

const FlowchartModal = ({ visible, onClose, data, sourceFile, providerService }) => {
  if (!visible || !data) return null;

  // 判断调用类型
  const normalize = (str) => (str || '').trim().toLowerCase();
  
  // Use extracted providerService if available, otherwise fallback to data.target_service
  const targetService = providerService || data.target_service;
  
  const isInternal = normalize(data.service_name) === normalize(targetService) || 
                     normalize(data.service_name) === normalize(targetService + '-provider') || 
                     normalize(data.service_name + '-provider') === normalize(targetService);

  const callTypeConfig = isInternal 
    ? { text: 'Process Internal (本地调用)', color: 'blue', bg: 'bg-blue-50', textCol: 'text-blue-600', border: 'border-blue-100' }
    : { text: 'RPC / HTTP (跨服务调用)', color: 'orange', bg: 'bg-orange-50', textCol: 'text-orange-600', border: 'border-orange-100' };

  const lineNumber = data.line_number && data.line_number > 0 ? data.line_number : 'N/A';

  return (
    <Modal
      title={<span className="flex items-center gap-2"><BranchesOutlined /> 依赖调用链路分析</span>}
      open={visible}
      onCancel={onClose}
      footer={null}
      width={750}
      centered
    >
      <div className="pt-12 pb-6 px-4 bg-slate-50 rounded-lg border border-slate-100 flex flex-col items-center justify-center gap-6 relative overflow-visible">
         <div className={`absolute top-0 left-0 w-full h-1 bg-gradient-to-r ${isInternal ? 'from-blue-400 to-indigo-500' : 'from-orange-400 to-red-500'} opacity-30 rounded-t-lg`}></div>
         
         {/* Callee Node (Current/Provider) */}
         <div className="flex flex-col items-center z-10 w-full">
            <div className="w-80 bg-white border border-blue-200 rounded-lg shadow-sm p-4 text-center relative hover:shadow-md transition-shadow">
                 <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-[10px] font-bold border border-blue-200 tracking-wider shadow-sm">
                    被调用方 (Provider)
                 </div>
                 <div className="text-sm font-bold text-slate-800 mt-2 flex justify-center items-center gap-2">
                    <DeploymentUnitOutlined className="text-blue-500"/>
                    {targetService || 'Current Service'}
                 </div>
                 <div className="text-xs text-slate-500 mt-1.5 font-mono bg-slate-50 rounded py-1.5 px-2 border border-slate-100 truncate">
                    {sourceFile}
                 </div>
            </div>
         </div>

         {/* Edge with Call Type Label */}
         <div className="flex flex-col items-center gap-0 z-10 w-full relative">
             <div className="h-6 w-px bg-slate-300"></div>
             
             {/* Call Type Label */}
             <div className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider mb-1 ${callTypeConfig.bg} ${callTypeConfig.textCol} border ${callTypeConfig.border} shadow-sm`}>
                {callTypeConfig.text}
             </div>

             <div className="h-4 w-px bg-slate-300"></div>

             {/* INVOKES Box (Keep Full Text as requested) */}
             <div className="bg-white px-4 py-2 rounded-lg border border-indigo-100 text-xs text-slate-600 flex flex-col items-center shadow-sm z-20 max-w-[95%]">
                 <span className="text-[10px] text-indigo-500 font-bold mb-1 uppercase tracking-wider flex items-center gap-1">
                    <ApiOutlined /> INVOKES
                 </span>
                 <Tooltip title={data.target_method}>
                    <span className="font-mono font-medium text-slate-800 text-[10px] break-all text-center leading-relaxed">
                        {data.target_method || 'API / Interface'}
                    </span>
                 </Tooltip>
             </div>
             
             <div className="h-6 w-px bg-slate-300"></div>
             <ArrowDownOutlined className="text-slate-300 text-lg" />
         </div>

         {/* Caller Node (Consumer) */}
         <div className="flex flex-col items-center z-10 w-full">
            <div className={`w-80 bg-white border ${isInternal ? 'border-green-200' : 'border-orange-200'} rounded-lg shadow-sm p-4 text-center relative hover:shadow-md transition-shadow`}>
                 <div className={`absolute -top-3 left-1/2 transform -translate-x-1/2 ${isInternal ? 'bg-green-100 text-green-700 border-green-200' : 'bg-orange-100 text-orange-700 border-orange-200'} px-3 py-1 rounded-full text-[10px] font-bold border tracking-wider shadow-sm`}>
                    调用方 (Consumer)
                 </div>
                 
                 {/* Line Number Badge */}
                 {lineNumber !== 'N/A' && (
                    <div className="absolute -right-2 -top-2 bg-slate-800 text-white text-[10px] font-mono font-bold px-2 py-0.5 rounded-md shadow-sm border border-slate-600">
                        Line: {lineNumber}
                    </div>
                 )}

                 <div className="text-sm font-bold text-slate-800 mt-2 flex justify-center items-center gap-2">
                    <AppstoreOutlined className={isInternal ? 'text-green-500' : 'text-orange-500'} />
                    {data.service_name || 'Unknown Service'}
                 </div>
                 <div className="text-xs text-slate-600 mt-1.5 font-mono bg-slate-50 rounded py-1.5 px-2 border border-slate-100 break-all">
                    {data.caller_class || data.file_path || 'Unknown Class'}
                 </div>
                 <div className="text-[10px] text-slate-400 mt-2 pt-2 border-t border-slate-50 flex items-center justify-center gap-1">
                    <CodeOutlined /> 方法: {data.caller_method || 'Method Call'}
                 </div>
            </div>
         </div>

         {/* Call Snippet - 使用新的可折叠组件 */}
         {(data.call_snippet_data || data.call_snippet) && (
             <CollapsibleCodeSnippet 
                 snippetData={data.call_snippet_data || data.call_snippet}
                 fileName={data.file_path ? data.file_path.split(/[/\\]/).pop() : 'Snippet'}
                 lineNumber={data.line_number}
             />
         )}

         {/* Impact Box (Risk Analysis) */}
         <div className="mt-4 w-full max-w-xl bg-white p-0 rounded-lg border border-red-100 shadow-sm overflow-hidden">
            <div className="bg-red-50/50 px-4 py-2 border-b border-red-50 flex items-center gap-2">
                <BugOutlined className="text-red-500" />
                <span className="font-bold text-xs text-red-800">潜在风险诊断</span>
            </div>
            <div className="p-4 text-xs text-slate-600 leading-relaxed">
                <div className="flex gap-3">
                    <div className="shrink-0 mt-0.5">
                        <InfoCircleOutlined className="text-red-400" />
                    </div>
                    <div>
                        <div className="font-medium text-slate-700 mb-1">变更影响分析：</div>
                        {data.impact_description || '暂无详细描述'}
                    </div>
                </div>
            </div>
         </div>
      </div>
    </Modal>
  );
};

export default FlowchartModal;

