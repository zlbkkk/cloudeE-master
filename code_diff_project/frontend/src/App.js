import React, { useState, useEffect } from 'react';
// Re-build trigger
import axios from 'axios';
import { Table, Empty, Spin, Button, message, Modal, Form, Input, Select, Tabs, Radio } from 'antd';
import { FileTextOutlined, ClockCircleOutlined, SafetyCertificateOutlined, BugOutlined, PlayCircleOutlined, CodeOutlined, ExpandOutlined, InfoCircleOutlined, CheckCircleOutlined, ProjectOutlined, BranchesOutlined, FolderOpenOutlined, ArrowRightOutlined, DownOutlined, RightOutlined, GithubOutlined, LaptopOutlined, ApiOutlined, AppstoreOutlined, ArrowDownOutlined, ArrowUpOutlined } from '@ant-design/icons';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vs, vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const API_BASE = 'http://127.0.0.1:8000/api/';
const REPORTS_URL = `${API_BASE}reports/`;
const TASKS_URL = `${API_BASE}tasks/`;

const FlowchartModal = ({ visible, onClose, data, sourceFile }) => {
  if (!visible || !data) return null;

  return (
    <Modal
      title={<span className="flex items-center gap-2"><BranchesOutlined /> 依赖调用链路分析</span>}
      open={visible}
      onCancel={onClose}
      footer={null}
      width={700}
      centered
    >
      <div className="pt-12 pb-6 px-4 bg-slate-50 rounded-lg border border-slate-100 flex flex-col items-center justify-center gap-5 relative overflow-visible">
         <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-green-500 via-blue-500 to-indigo-500 opacity-20 rounded-t-lg"></div>
         
         {/* Callee Node (Current/Provider) - Moved to Top */}
         <div className="flex flex-col items-center z-10">
            <div className="w-72 bg-white border border-blue-200 rounded-lg shadow-sm p-4 text-center relative">
                 <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-[10px] font-bold border border-blue-200 tracking-wider shadow-sm">被调用方 (Provider)</div>
                 <div className="text-sm font-bold text-slate-800 mt-2">{data.target_service || 'Current Service'}</div>
                 <div className="text-xs text-slate-600 mt-1.5 font-mono bg-slate-50 rounded py-1 px-2 border border-slate-100">
                    {sourceFile}
                 </div>
            </div>
         </div>

         {/* Edge */}
         <div className="flex flex-col items-center gap-0 z-10">
             <div className="h-8 w-px bg-slate-300"></div>
             <div className="bg-white px-3 py-1 rounded-full border border-blue-200 text-xs text-slate-600 flex flex-col items-center shadow-sm z-20 my-1">
                 <span className="text-[10px] text-blue-500 font-bold mb-0.5">INVOKES</span>
                 <span className="font-mono font-medium max-w-[200px] truncate text-slate-800 text-[10px]" title={data.target_method}>{data.target_method || 'API / Interface'}</span>
             </div>
             <ArrowDownOutlined className="text-slate-300 text-lg" />
         </div>

         {/* Caller Node (Downstream/Consumer) - Moved to Bottom */}
         <div className="flex flex-col items-center z-10">
            <div className="w-72 bg-white border border-green-200 rounded-lg shadow-sm p-4 text-center relative">
                 <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-green-100 text-green-700 px-3 py-1 rounded-full text-[10px] font-bold border border-green-200 tracking-wider shadow-sm">调用方 (Consumer)</div>
                 <div className="text-sm font-bold text-slate-800 mt-2">{data.service_name || 'Unknown Service'}</div>
                 <div className="text-xs text-slate-600 mt-1.5 font-mono bg-slate-50 rounded py-1 px-2 border border-slate-100 break-all">
                    {data.caller_class || data.file_path || 'Unknown Class'}
                 </div>
                 <div className="text-[10px] text-slate-400 mt-1 flex items-center justify-center gap-1">
                    <CodeOutlined /> {data.caller_method || 'Method Call'}
                 </div>
            </div>
         </div>

         {/* Call Snippet */}
         {data.call_snippet && (
             <div className="w-full max-w-lg bg-slate-800 rounded-lg p-3 border border-slate-700 shadow-md font-mono text-[10px] text-slate-300 overflow-x-auto z-10">
                 <div className="text-slate-500 mb-1 uppercase tracking-wider text-[9px] font-bold flex items-center gap-1">
                     <CodeOutlined /> 调用点代码预览
                 </div>
                 <pre className="whitespace-pre-wrap break-all">{data.call_snippet}</pre>
             </div>
         )}

         {/* Impact Box */}
         <div className="mt-6 w-full max-w-lg bg-orange-50/60 p-4 rounded-lg border border-orange-100 text-xs text-orange-900 flex gap-3 items-start">
            <BugOutlined className="mt-0.5 text-orange-600 text-base" />
            <div>
                <div className="font-bold mb-1 text-orange-800">潜在风险分析</div>
                <div className="leading-relaxed opacity-90">{data.impact_description}</div>
            </div>
         </div>
      </div>
    </Modal>
  );
};

const getLanguage = (fileName) => {
  if (!fileName) return 'text';
  const lower = fileName.toLowerCase();
  if (lower.endsWith('.java')) return 'java';
  if (lower.endsWith('.xml')) return 'xml';
  if (lower.endsWith('.sql')) return 'sql';
  if (lower.endsWith('.py')) return 'python';
  if (lower.endsWith('.js') || lower.endsWith('.jsx')) return 'javascript';
  if (lower.endsWith('.json')) return 'json';
  if (lower.endsWith('.properties') || lower.endsWith('.yml') || lower.endsWith('.yaml')) return 'ini';
  return 'text';
};

const parseDiff = (text) => {
  const lines = text.split('\n');
  const rows = [];
  let leftLine = 0;
  let rightLine = 0;
  let bufferDelete = [];
  let bufferAdd = [];

  const flushBuffer = () => {
    const maxLen = Math.max(bufferDelete.length, bufferAdd.length);
    for (let i = 0; i < maxLen; i++) {
      const delItem = bufferDelete[i] || null;
      const addItem = bufferAdd[i] || null;
      rows.push({
        leftNum: delItem ? delItem.line : '',
        leftCode: delItem ? delItem.content : '',
        leftType: delItem ? 'delete' : 'empty',
        rightNum: addItem ? addItem.line : '',
        rightCode: addItem ? addItem.content : '',
        rightType: addItem ? 'add' : 'empty',
      });
    }
    bufferDelete = [];
    bufferAdd = [];
  };

  lines.forEach(line => {
    // Ignore git metadata header lines
    if (line.startsWith('diff ') || 
        line.startsWith('index ') || 
        line.startsWith('new file mode') || 
        line.startsWith('deleted file mode') ||
        line.startsWith('similarity index') ||
        line.startsWith('rename from') ||
        line.startsWith('rename to') ||
        line.startsWith('--- ') || 
        line.startsWith('+++ ') || 
        line.startsWith('\\')) {
        return;
    }

    if (line.startsWith('@@')) {
      flushBuffer();
      rows.push({ type: 'header', content: line });
      const match = line.match(/@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@/);
      if (match) {
        // If left line is 0 (new file), keep it 0. Otherwise adjust index.
        const lLine = parseInt(match[1], 10);
        leftLine = lLine === 0 ? 0 : lLine - 1;
        
        const rLine = parseInt(match[3], 10);
        rightLine = rLine === 0 ? 0 : rLine - 1;
      }
      return;
    }

    if (line.startsWith('-')) {
      leftLine++;
      bufferDelete.push({ line: leftLine, content: line.substring(1) });
    } else if (line.startsWith('+')) {
      rightLine++;
      bufferAdd.push({ line: rightLine, content: line.substring(1) });
    } else {
      flushBuffer();
      // Only increment if line number is > 0 (handle empty file cases)
      if (leftLine >= 0) leftLine++;
      if (rightLine >= 0) rightLine++;
      rows.push({
        leftNum: leftLine,
        leftCode: line.substring(1),
        leftType: 'normal',
        rightNum: rightLine,
        rightCode: line.substring(1),
        rightType: 'normal',
      });
    }
  });
  flushBuffer();
  return rows;
};

const DiffModal = ({ visible, onClose, diffContent, fileName }) => {
  const [diffRows, setDiffRows] = useState([]);
  const language = getLanguage(fileName);

  useEffect(() => {
    if (diffContent) {
      setDiffRows(parseDiff(diffContent));
    }
  }, [diffContent]);

  return (
    <Modal
      title={<span style={{ color: '#d4d4d4' }}><CodeOutlined className="mr-2"/>代码变更详情: {fileName}</span>}
      open={visible}
      onCancel={onClose}
      width="95%"
      style={{ top: 20 }}
      footer={[
        <Button key="close" onClick={onClose} type="primary" ghost style={{ marginRight: 16 }}>
          关闭视图
        </Button>
      ]}
      closeIcon={<span style={{ color: '#d4d4d4', fontSize: '16px' }}>×</span>}
      styles={{ 
        content: { backgroundColor: '#1e1e1e', color: '#d4d4d4', borderRadius: '8px', overflow: 'hidden' },
        header: { backgroundColor: '#1e1e1e', color: '#d4d4d4', borderBottom: '1px solid #333', padding: '16px 24px' },
        body: { padding: 0, height: '85vh', overflow: 'hidden', backgroundColor: '#1e1e1e' },
        footer: { backgroundColor: '#1e1e1e', borderTop: '1px solid #333', padding: '20px 24px' },
        mask: { backgroundColor: 'rgba(0, 0, 0, 0.85)', backdropFilter: 'blur(4px)' }
      }}
    >
      <div className="h-full overflow-auto font-mono text-xs custom-scrollbar" style={{ backgroundColor: '#1e1e1e' }}>
        <table className="w-full border-collapse" style={{ color: '#d4d4d4' }}>
          <thead>
            <tr style={{ backgroundColor: '#252526', borderBottom: '1px solid #333', color: '#858585' }}>
              <th className="w-12 p-1 text-right border-r border-[#333] select-none">旧行</th>
              <th className="w-1/2 p-1 text-left border-r border-[#333] pl-2 select-none">变更前</th>
              <th className="w-12 p-1 text-right border-r border-[#333] select-none">新行</th>
              <th className="w-1/2 p-1 text-left pl-2 select-none">变更后</th>
            </tr>
          </thead>
          <tbody>
            {diffRows.map((row, idx) => {
              if (row.type === 'header') return null;

              return (
                <tr key={idx} className="hover:bg-[#2a2d2e]">
                  <td className="text-right pr-2 text-[#6e7681] select-none border-r border-[#333]" 
                      style={{ backgroundColor: row.leftType === 'delete' ? 'rgba(248, 81, 73, 0.15)' : 'transparent' }}>
                    {row.leftNum}
                  </td>
                  <td className="pl-0 border-r border-[#333]" 
                      style={{ backgroundColor: row.leftType === 'delete' ? 'rgba(248, 81, 73, 0.15)' : 'transparent', verticalAlign: 'top' }}>
                    {row.leftCode && (
                       <SyntaxHighlighter 
                         language={language} 
                         style={vscDarkPlus} 
                         customStyle={{ margin: 0, padding: '0 0 0 8px', background: 'transparent', fontSize: '12px', lineHeight: '1.5' }}
                         codeTagProps={{ style: { fontFamily: 'inherit' } }}
                       >
                         {row.leftCode}
                       </SyntaxHighlighter>
                    )}
                  </td>
                  <td className="text-right pr-2 text-[#6e7681] select-none border-r border-[#333]" 
                      style={{ backgroundColor: row.rightType === 'add' ? 'rgba(46, 160, 67, 0.15)' : 'transparent' }}>
                    {row.rightNum}
                  </td>
                  <td className="pl-0" 
                      style={{ backgroundColor: row.rightType === 'add' ? 'rgba(46, 160, 67, 0.15)' : 'transparent', verticalAlign: 'top' }}>
                    {row.rightCode && (
                       <SyntaxHighlighter 
                         language={language} 
                         style={vscDarkPlus} 
                         customStyle={{ margin: 0, padding: '0 0 0 8px', background: 'transparent', fontSize: '12px', lineHeight: '1.5' }}
                         codeTagProps={{ style: { fontFamily: 'inherit' } }}
                       >
                         {row.rightCode}
                       </SyntaxHighlighter>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Modal>
  );
};

const AnalysisConfigModal = ({ open, onClose, onSuccess }) => {
    const [form] = Form.useForm();
    const [loading, setLoading] = useState(false);
    // Default to 'git' mode and remove tab switching
    const [mode, setMode] = useState('git');
    const [branches, setBranches] = useState([]);
    const [fetchingBranches, setFetchingBranches] = useState(false);
    const [commits, setCommits] = useState([]);
    const [fetchingCommits, setFetchingCommits] = useState(false);

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
                targetCommit: values.targetCommit
            });
            
            if (res.data.status === 'Analysis started') {
                message.success('任务已提交至后台队列');
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
            <Form form={form} layout="vertical" initialValues={{ sourceBranch: undefined, targetBranch: undefined, gitUrl: '' }}>
                
                <Form.Item name="gitUrl" label="Git 仓库地址" rules={[{ required: true, message: '请输入 Git 地址' }]}>
                    <Input prefix={<GithubOutlined className="text-slate-400"/>} placeholder="https://github.com/username/repo.git" />
                </Form.Item>
                <div className="flex gap-2 mb-4">
                        <Button onClick={fetchGitBranches} loading={fetchingBranches} icon={<BranchesOutlined />}>
                        {fetchingBranches ? '获取中...' : '获取分支列表'}
                        </Button>
                </div>

                <div className="grid grid-cols-1 gap-4 mb-4">
                    <Form.Item name="targetBranch" label="工作分支 (Working Branch)" rules={[{ required: true, message: '请选择工作分支' }]}>
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

                <div className="grid grid-cols-1 gap-4 bg-slate-50 p-4 rounded-lg border border-slate-200 mb-4">
                    <div className="text-xs font-bold text-slate-500 mb-2 flex items-center gap-2">
                        <ClockCircleOutlined /> 选择比对范围 (Commit Range)
                    </div>
                    <Form.Item name="baseCommit" label="起始提交 (Base Commit)" rules={[{ required: true, message: '请选择起始 Commit' }]}>
                        <Select 
                            placeholder={fetchingCommits ? "加载提交记录中..." : "选择起始提交"}
                            showSearch 
                            loading={fetchingCommits}
                            disabled={commits.length === 0}
                            optionLabelProp="label"
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
                    <div className="flex justify-center -my-2 text-slate-300 text-lg"><ArrowDownOutlined /></div>
                    <Form.Item name="targetCommit" label="结束提交 (Target Commit)" rules={[{ required: true, message: '请选择结束 Commit' }]}>
                        <Select 
                            placeholder={fetchingCommits ? "加载提交记录中..." : "选择结束提交"}
                            showSearch 
                            loading={fetchingCommits}
                            disabled={commits.length === 0}
                            optionLabelProp="label"
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

                <div className="bg-blue-50 p-3 rounded-lg text-xs text-blue-700 mt-2 leading-relaxed">
                    <InfoCircleOutlined className="mr-1" /> 
                    系统将分析 <b>[工作分支]</b> 上，从历史节点 <b>[起始提交]</b> 演进到 <b>[结束提交]</b> 期间产生的所有代码变更（增量分析）。<br/>
                    <span className="ml-4 opacity-80">适用于精准评估两次发版之间、或某段开发周期内的代码改动风险。</span>
                </div>
            </Form>
        </Modal>
    );
};

// New Component: Task List View
const TaskListView = ({ tasks }) => {
    const getStatusColor = (status) => {
        switch(status) {
            case 'COMPLETED': return 'text-green-600 bg-green-50 border-green-100';
            case 'FAILED': return 'text-red-600 bg-red-50 border-red-100';
            case 'PROCESSING': return 'text-blue-600 bg-blue-50 border-blue-100';
            default: return 'text-orange-600 bg-orange-50 border-orange-100'; // PENDING
        }
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
                        )}
                    ]}
                />
            </div>
        </div>
    );
};

function App() {
  const [reports, setReports] = useState([]);
  const [tasks, setTasks] = useState([]); 
  const [activeTab, setActiveTab] = useState('reports'); // 'reports' | 'tasks'
  const [selectedReportId, setSelectedReportId] = useState(null);
  const [selectedProject, setSelectedProject] = useState(null); 
  const [expandedProjects, setExpandedProjects] = useState([]); 
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [isAnalysisModalOpen, setIsAnalysisModalOpen] = useState(false);

  const fetchReports = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(REPORTS_URL);
      setReports(res.data);
      
      // Auto-select logic only if viewing reports
      if (res.data.length > 0 && !selectedProject && !selectedReportId) {
         const firstProj = res.data[0].project_name || 'Unknown Project';
         setExpandedProjects([firstProj]);
         setSelectedProject(firstProj);
      }
    } catch (error) {
      console.error("Failed to fetch reports:", error);
    } finally {
      setLoading(false);
    }
  }, [selectedReportId, selectedProject]);

  const isPollingRef = React.useRef(false);

  const startPolling = React.useCallback(async () => {
      if (isPollingRef.current) return; // Avoid duplicate loops
      isPollingRef.current = true;

      const poll = async () => {
          try {
              const res = await axios.get(TASKS_URL);
              const allTasks = res.data;
              setTasks(allTasks);

              const activeTasks = allTasks.filter(t => ['PENDING', 'PROCESSING'].includes(t.status));
              
              if (activeTasks.length > 0) {
                  // Continue polling if active tasks exist
                  setTimeout(poll, 3000);
              } else {
                  // Stop polling
                  isPollingRef.current = false;
                  // Optional: Refresh reports once when all tasks finish
                  fetchReports();
              }
          } catch (error) {
              console.error("Polling error:", error);
              isPollingRef.current = false; // Stop on error to avoid infinite spam
          }
      };
      poll();
  }, [fetchReports]); // TASKS_URL is constant

  useEffect(() => {
    // Initial load
    fetchReports();
    startPolling(); // Start check, will auto-stop if no tasks
  }, [fetchReports, startPolling]);

  // Manual refresh helper
  const refreshData = React.useCallback(() => {
      fetchReports();
      startPolling(); // Restart polling incase it stopped
  }, [fetchReports, startPolling]);

  // Update AnalysisConfigModal success handler
  const onAnalysisStart = () => {
      setActiveTab('tasks');
      refreshData(); // This triggers fetchReports and restarts task polling
  };

  // Group reports by project and then by task (preferred) or fuzzy timestamp
  const projectGroups = React.useMemo(() => {
      const groups = {};
      
      // 1. Sort reports by creation time descending
      const sortedReports = [...reports].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

      sortedReports.forEach(r => {
          const pName = r.project_name || 'Unknown Project';
          if (!groups[pName]) groups[pName] = {};
          
          let batchKey = null;

          // Priority 1: Group by Task ID if available
          if (r.task) {
              const rDate = new Date(r.created_at);
              // Use Task ID combined with date for display text, but grouping relies on ID
              // To make it look nice in UI: "YYYY-MM-DD HH:mm (Task #ID)"
              const timeStr = `${rDate.getFullYear()}-${String(rDate.getMonth()+1).padStart(2, '0')}-${String(rDate.getDate()).padStart(2, '0')} ${String(rDate.getHours()).padStart(2, '0')}:${String(rDate.getMinutes()).padStart(2, '0')}`;
              batchKey = `${timeStr} (Task #${r.task})`;
          } else {
              // Priority 2: Legacy Fuzzy Timestamp grouping
              const rDate = new Date(r.created_at);
              const existingKeys = Object.keys(groups[pName]);
              
              for (const key of existingKeys) {
                  // Skip task-based keys for fuzzy matching to avoid mixing
                  if (key.includes('(Task #')) continue;

                  const batchReports = groups[pName][key];
                  if (batchReports.length > 0) {
                      const firstDate = new Date(batchReports[0].created_at);
                      const diffMinutes = Math.abs((firstDate - rDate) / (1000 * 60));
                      if (diffMinutes <= 5) { 
                          batchKey = key;
                          break;
                      }
                  }
              }
              
              if (!batchKey) {
                   const timeKey = `${rDate.getFullYear()}-${String(rDate.getMonth()+1).padStart(2, '0')}-${String(rDate.getDate()).padStart(2, '0')} ${String(rDate.getHours()).padStart(2, '0')}:${String(rDate.getMinutes()).padStart(2, '0')}`;
                   batchKey = timeKey;
              }
          }

          if (!groups[pName][batchKey]) {
              groups[pName][batchKey] = [];
          }
          groups[pName][batchKey].push(r);
      });
      return groups;
  }, [reports]);

  const [expandedBatches, setExpandedBatches] = useState([]);

  const handleProjectClick = (projName) => {
      if (expandedProjects.includes(projName)) {
          setExpandedProjects(prev => prev.filter(p => p !== projName));
      } else {
          setExpandedProjects(prev => [...prev, projName]);
          const batches = Object.keys(projectGroups[projName]).sort().reverse();
          if (batches.length > 0) {
              const latestBatch = batches[0];
              setExpandedBatches(prev => [...prev, `${projName}-${latestBatch}`]);
          }
      }
      setSelectedProject(projName);
      setSelectedReportId(null);
  };

  const handleBatchClick = (e, batchKey) => {
      e.stopPropagation();
      if (expandedBatches.includes(batchKey)) {
          setExpandedBatches(prev => prev.filter(b => b !== batchKey));
      } else {
          setExpandedBatches(prev => [...prev, batchKey]);
      }
  };
  
  const currentReport = reports.find(r => r.id === selectedReportId);
  
  const currentProjectReports = React.useMemo(() => {
      if (!selectedProject || !projectGroups[selectedProject]) return [];
      return Object.values(projectGroups[selectedProject]).flat().sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }, [selectedProject, projectGroups]);
  
  // Render Sidebar
  const renderSidebar = () => (
    <div className="w-64 bg-white border-r border-slate-200 flex flex-col h-full flex-shrink-0 transition-all duration-300 z-20 relative">
      <div className="p-4 border-b border-slate-100">
        <h1 className="text-base font-bold tracking-wide text-slate-800 leading-tight flex items-center gap-2 mb-4">
            <div className="bg-blue-600 text-white p-1.5 rounded-lg shadow-md shadow-blue-600/20">
                <ProjectOutlined className="text-lg" />
            </div>
            <span>精准测试<br/><span className="text-[10px] text-slate-400 font-normal">分析报告中心</span></span>
        </h1>
        
        {/* Main Navigation Tabs */}
        <div className="flex p-1 bg-slate-100 rounded-lg">
            <button 
                onClick={() => setActiveTab('reports')}
                className={`flex-1 py-1.5 text-xs font-bold rounded-md transition-all flex items-center justify-center gap-1.5 ${activeTab === 'reports' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
            >
                <AppstoreOutlined /> 服务分析
            </button>
            <button 
                onClick={() => setActiveTab('tasks')}
                className={`flex-1 py-1.5 text-xs font-bold rounded-md transition-all flex items-center justify-center gap-1.5 ${activeTab === 'tasks' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
            >
                <ClockCircleOutlined /> 任务管理
            </button>
        </div>
      </div>

      {/* Active Tasks Mini-View (Always show if tasks running) */}
      {tasks.some(t => ['PENDING', 'PROCESSING'].includes(t.status)) && (
          <div className="px-3 py-2 border-b border-slate-100 bg-blue-50/30">
             <div className="text-[10px] font-bold text-slate-400 mb-2 px-1 flex items-center gap-1">
                <Spin size="small" /> 正在运行的任务
             </div>
             {tasks.filter(t => ['PENDING', 'PROCESSING'].includes(t.status)).map(task => (
                 <div key={task.id} className="bg-white border border-blue-100 rounded-lg p-2.5 mb-2 last:mb-0 shadow-sm">
                    <div className="flex justify-between items-center mb-1.5">
                        <span className="text-xs font-bold text-slate-700 truncate max-w-[120px]">{task.project_name}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="h-1 flex-1 bg-slate-100 rounded-full overflow-hidden">
                            <div className="h-full bg-blue-500 w-2/3 animate-[progress_1s_ease-in-out_infinite]"></div>
                        </div>
                        <span className="text-[10px] text-blue-600 font-medium">分析中</span>
                    </div>
                 </div>
             ))}
          </div>
      )}

      {/* Content based on Tab */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-3">
        {activeTab === 'reports' ? (
            <div className="space-y-1.5">
                {loading && reports.length === 0 ? (
                <div className="p-4 text-center text-slate-400 text-xs">加载中...</div>
                ) : (
                Object.keys(projectGroups).map(projName => {
                    // ... existing project tree logic ...
                    const isExpanded = expandedProjects.includes(projName);
                    const isSelected = selectedProject === projName;
                    const batches = projectGroups[projName];
                    const sortedBatches = Object.keys(batches).sort().reverse();
                    const totalFiles = Object.values(batches).flat().length;

                    return (
                    <div key={projName} className="mb-1">
                        <button
                            onClick={() => handleProjectClick(projName)}
                            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg transition-all duration-200 group font-medium text-sm text-left ${
                                isSelected && !selectedReportId ? 'bg-blue-50 text-blue-700 shadow-sm' : 'text-slate-700 hover:bg-slate-50'
                            }`}
                        >
                            <span className="text-xs text-slate-400">{isExpanded ? <DownOutlined /> : <RightOutlined />}</span>
                            <FolderOpenOutlined className={isSelected ? 'text-blue-500' : 'text-slate-400'} />
                            <span className="truncate flex-1">{projName}</span>
                            <span className="bg-slate-100 text-slate-500 text-[10px] px-1.5 py-0.5 rounded-full">{totalFiles}</span>
                        </button>

                        {isExpanded && (
                            <div className="ml-4 pl-2 border-l border-slate-100 mt-1 space-y-1">
                                {sortedBatches.map(timeKey => {
                                    const batchKey = `${projName}-${timeKey}`;
                                    const isBatchExpanded = expandedBatches.includes(batchKey);
                                    const batchReports = batches[timeKey];
                                    return (
                                        <div key={batchKey}>
                                            <button
                                                onClick={(e) => handleBatchClick(e, batchKey)}
                                                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-slate-500 hover:bg-slate-50 transition-colors"
                                            >
                                                <span className="text-[10px] text-slate-300">{isBatchExpanded ? <DownOutlined /> : <RightOutlined />}</span>
                                                <ClockCircleOutlined className="text-[10px]" />
                                                <span className="truncate flex-1">{timeKey}</span>
                                                <span className="text-[10px] bg-slate-50 px-1 rounded">{batchReports.length}</span>
                                            </button>
                                            {isBatchExpanded && (
                                                <div className="ml-3 pl-2 border-l border-slate-100 mt-1 space-y-0.5">
                                                    {batchReports.map(report => (
                                                        <button
                                                            key={report.id}
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                setSelectedProject(projName);
                                                                setSelectedReportId(report.id);
                                                            }}
                                                            className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md transition-all text-xs text-left ${
                                                                selectedReportId === report.id ? 'bg-blue-50 text-blue-700 font-medium' : 'text-slate-600 hover:bg-slate-50'
                                                            }`}
                                                        >
                                                            <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                                                                report.risk_level === 'CRITICAL' ? 'bg-red-500' : 
                                                                report.risk_level === 'HIGH' ? 'bg-orange-500' : 
                                                                report.risk_level === 'MEDIUM' ? 'bg-yellow-500' : 'bg-green-500'
                                                            }`}></div>
                                                            <span className="truncate">{report.file_name}</span>
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                    );
                })
                )}
                {reports.length === 0 && !loading && <div className="text-center text-slate-400 text-xs mt-4">暂无分析报告</div>}
            </div>
        ) : (
            <div className="text-xs text-slate-500 leading-relaxed p-2">
                <div className="mb-4 bg-slate-50 p-3 rounded border border-slate-100">
                    <h3 className="font-bold text-slate-700 mb-1">任务管理说明</h3>
                    <p>此处展示所有历史分析任务的状态。您可以在右侧主界面查看详细的任务列表和执行日志。</p>
                </div>
                <div className="space-y-2">
                    <div className="flex justify-between items-center">
                        <span>总任务数</span>
                        <span className="font-bold text-slate-700">{tasks.length}</span>
                    </div>
                    <div className="flex justify-between items-center text-green-600">
                        <span>已完成</span>
                        <span className="font-bold">{tasks.filter(t=>t.status==='COMPLETED').length}</span>
                    </div>
                    <div className="flex justify-between items-center text-red-500">
                        <span>失败</span>
                        <span className="font-bold">{tasks.filter(t=>t.status==='FAILED').length}</span>
                    </div>
                </div>
            </div>
        )}
      </div>
    </div>
  );

  const renderMainContent = () => {
      if (activeTab === 'tasks') {
          return <TaskListView tasks={tasks} />;
      }
      
      // Reports view
      if (currentReport) return <ReportDetail report={currentReport} />;
      if (selectedProject) return <ProjectOverview projectName={selectedProject} reports={currentProjectReports} onSelectReport={setSelectedReportId} />;
      
      return (
        <div className="flex flex-col items-center justify-center h-full text-slate-400">
           <Empty description={false} className="opacity-50" />
           <p className="mt-4">请从左侧选择一个项目或报告查看详情</p>
        </div>
      );
  };

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 font-sans text-slate-900">
      {renderSidebar()}
      
      <div className="flex-1 flex flex-col h-full relative w-full">
        <header className="bg-white/80 backdrop-blur-sm border-b border-slate-200 px-5 py-3 flex justify-between items-center flex-shrink-0 z-10 sticky top-0">
          <div>
            <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
               {activeTab === 'reports' ? <SafetyCertificateOutlined className="text-blue-600" /> : <ClockCircleOutlined className="text-blue-600" />}
               {activeTab === 'reports' ? '精准测试分析大屏' : '分析任务监控台'}
            </h2>
            <p className="text-[10px] text-slate-500 mt-0.5">基于代码差异与链路分析的智能评估系统</p>
          </div>
          <div className="flex items-center gap-3">
             <button 
                onClick={() => setIsAnalysisModalOpen(true)}
                disabled={analyzing}
                className={`bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-colors flex items-center gap-2 text-xs font-medium shadow-sm shadow-blue-600/20 ${analyzing ? 'opacity-70 cursor-not-allowed' : ''}`}
             >
                {analyzing ? <Spin size="small" className="text-white mr-1"/> : <PlayCircleOutlined />}
                {analyzing ? '正在分析...' : '新建分析'}
             </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 scroll-smooth">
           {renderMainContent()}
        </main>
      </div>
      
      <AnalysisConfigModal 
        open={isAnalysisModalOpen} 
        onClose={() => setIsAnalysisModalOpen(false)} 
        onSuccess={onAnalysisStart} 
        loading={analyzing}
      />
    </div>
  );
}

// New Component: Project Overview
const ProjectOverview = ({ projectName, reports = [], onSelectReport }) => {
    return (
        <div className="max-w-6xl mx-auto">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-3">
                    <FolderOpenOutlined className="text-blue-500" />
                    {projectName}
                </h1>
                <p className="text-slate-500 mt-2">该项目共检测到 {reports.length} 个文件变更。</p>
            </div>
            
            <div className="grid grid-cols-3 gap-4">
                {reports.map(report => {
                    const renderRiskBadge = (level) => {
                        const colors = { 'CRITICAL': 'text-red-600 bg-red-50', 'HIGH': 'text-orange-600 bg-orange-50', 'MEDIUM': 'text-yellow-600 bg-yellow-50', 'LOW': 'text-green-600 bg-green-50' };
                        return <span className={`px-2 py-0.5 rounded text-xs font-bold ${colors[level]}`}>{level}</span>;
                    };
                    return (
                        <div key={report.id} onClick={() => onSelectReport(report.id)} className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 cursor-pointer hover:shadow-md hover:border-blue-200 transition-all">
                            <div className="flex justify-between items-start mb-2">
                                <FileTextOutlined className="text-2xl text-slate-400" />
                                {renderRiskBadge(report.risk_level)}
                            </div>
                            <h3 className="font-bold text-slate-700 truncate mb-1" title={report.file_name}>{report.file_name}</h3>
                            <div className="text-xs text-slate-400 flex items-center gap-1">
                                <ClockCircleOutlined /> {new Date(report.created_at).toLocaleDateString()}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

const ReportDetail = ({ report }) => {
  const data = report.report_json;
  const [diffModalVisible, setDiffModalVisible] = useState(false);
  const [flowchartVisible, setFlowchartVisible] = useState(false);
  const [currentFlowData, setCurrentFlowData] = useState(null);

  const renderField = (value) => {
    if (!value) return <span className="text-slate-400">N/A</span>;
    if (typeof value === 'string') {
        // Auto-format numbered lists (e.g., "1. xxx; 2. xxx")
        if (value.match(/\d+\.\s/)) {
            const items = value.split(/(?=\d+\.\s)/).filter(item => item.trim());
            if (items.length > 1) {
                return (
                    <ul className="list-none space-y-2">
                        {items.map((item, idx) => (
                            <li key={idx} className="flex gap-2 items-start">
                                <div className="w-5 h-5 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
                                    {idx + 1}
                                </div>
                                <span className="leading-6">{item.replace(/^\d+\.\s*/, '').replace(/;$/, '')}</span>
                            </li>
                        ))}
                    </ul>
                );
            }
        }
        return value;
    }
    if (typeof value === 'object') {
        if (value.direct_impact || value.potential_impact) {
            return (
                <div className="text-xs space-y-1.5 text-slate-600">
                    {value.direct_impact && <p><b className="text-slate-700">直接影响:</b> {value.direct_impact}</p>}
                    {value.potential_impact && <p><b className="text-slate-700">潜在影响:</b> {value.potential_impact}</p>}
                    {value.regression_test_scope && <p><b className="text-slate-700">回归范围:</b> {value.regression_test_scope}</p>}
                    {value.regression_testing && <p><b className="text-slate-700">回归测试:</b> {value.regression_testing}</p>}
                </div>
            );
        }
        return <pre className="whitespace-pre-wrap text-xs bg-slate-50 p-3 rounded-lg border border-slate-100 text-slate-600 font-mono">{JSON.stringify(value, null, 2)}</pre>;
    }
    return String(value);
  };

  const cleanDiff = (diffText) => {
    if (!diffText) return '';
    return diffText.split('\n').filter(line => !line.startsWith('diff --git') && !line.startsWith('index ') && !line.startsWith('new file mode') && !line.startsWith('deleted file mode')).join('\n');
  };

  const renderRiskBadge = (level) => {
    const colors = { 
        'CRITICAL': 'bg-red-50 text-red-600 border-red-100', 
        'HIGH': 'bg-orange-50 text-orange-600 border-orange-100', 
        'MEDIUM': 'bg-yellow-50 text-yellow-600 border-yellow-100', 
        'LOW': 'bg-green-50 text-green-600 border-green-100' 
    };
    const colorClass = colors[level] || 'bg-slate-50 text-slate-600 border-slate-100';
    return <span className={`px-2.5 py-0.5 text-xs font-bold rounded-full border ${colorClass}`}>{level} RISK</span>;
  };

  return (
    <div className="space-y-3 max-w-6xl mx-auto pb-6 font-sans">
      
      {/* Title Card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 flex justify-between items-start transition-all hover:shadow-md">
         <div className="flex gap-4">
             <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center text-blue-600 text-lg flex-shrink-0 border border-blue-100 shadow-sm">
                 <FileTextOutlined />
             </div>
             <div>
                 {/* Project & Branch Context */}
                 <div className="flex items-center gap-2 text-[10px] text-gray-400 mb-1 font-medium tracking-wide">
                    <span className="flex items-center gap-1 bg-gray-50 px-1.5 py-0.5 rounded text-gray-500 border border-gray-100">
                        <FolderOpenOutlined /> {report.project_name || 'Unknown Project'}
                    </span>
                    <span className="text-gray-300">/</span>
                    <span className="flex items-center gap-1 bg-blue-50/50 text-blue-600 px-1.5 py-0.5 rounded border border-blue-100/50">
                        <BranchesOutlined /> {report.source_branch || 'master'} <ArrowRightOutlined className="text-[10px]" /> {report.target_branch || 'feature/dev'}
                    </span>
                 </div>
                 
                 <div className="flex items-center gap-3 mb-0.5">
                     <h1 className="text-lg font-bold text-gray-800 tracking-tight">{report.file_name}</h1>
                     {renderRiskBadge(report.risk_level)}
                 </div>
                 <div className="flex items-center gap-4 text-[10px] text-gray-400 font-medium">
                     <span className="flex items-center gap-1.5"><ClockCircleOutlined /> {new Date(report.created_at).toLocaleString()}</span>
                     <span className="flex items-center gap-1.5"><CodeOutlined /> ID: {report.id}</span>
                 </div>
             </div>
         </div>
         <button 
             onClick={() => setDiffModalVisible(true)}
             className="text-gray-500 hover:text-blue-600 px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-all flex items-center gap-2 text-xs font-semibold border border-transparent hover:border-gray-200"
         >
             <ExpandOutlined /> 查看 Diff
         </button>
      </div>

      <div className="grid grid-cols-1 gap-3">
          {/* Change Details */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <div className="flex items-center gap-2 mb-3 pb-3 border-b border-gray-50">
                  <InfoCircleOutlined className="text-blue-500 text-base" />
                  <h3 className="font-bold text-gray-800 text-sm">变更详情分析</h3>
              </div>
              
              <div className="space-y-3">
                  {/* Change Intent */}
                  <div>
                      <div className="flex items-center gap-2 mb-3 text-sm font-bold text-slate-700">
                          <FileTextOutlined className="text-blue-500"/> 变更详情
                      </div>
                      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm text-slate-700 leading-relaxed">
                          {renderField(report.change_intent || '暂无分析结果')}
                      </div>
                  </div>

                  {/* Impact Grid */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                      {/* Cross Service Impact */}
                      <div className="bg-orange-50/20 p-3 rounded-lg border border-orange-100/60 hover:border-orange-200 transition-colors">
                          <span className="flex items-center gap-2 text-[10px] font-bold text-orange-600 uppercase tracking-wider mb-1.5">
                              <ApiOutlined /> 跨服务影响
                          </span>
                          <div className="text-xs text-gray-700 font-medium leading-relaxed min-h-[40px]">
                              {renderField(data.cross_service_impact)}
                          </div>
                      </div>

                      {/* Functional Impact */}
                      <div className="bg-green-50/20 p-3 rounded-lg border border-green-100/60 hover:border-green-200 transition-colors">
                          <span className="flex items-center gap-2 text-[10px] font-bold text-green-600 uppercase tracking-wider mb-1.5">
                              <AppstoreOutlined /> 功能影响
                          </span>
                          <div className="text-xs text-gray-700 font-medium leading-relaxed min-h-[40px]">
                              {renderField(data.functional_impact)}
                          </div>
                      </div>
                  </div>
              </div>
          </div>
      </div>

      {/* Diff Preview */}
      {report.diff_content && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
             <div className="px-5 py-3 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                 <h3 className="font-bold text-slate-700 flex items-center gap-2">
                     <CodeOutlined className="text-indigo-500" /> 代码变更预览
                 </h3>
             </div>
             <div className="relative group">
                <div style={{ maxHeight: '250px', overflow: 'hidden' }} className="opacity-80">
                    <SyntaxHighlighter language="diff" style={vs} showLineNumbers={true} customStyle={{ margin: 0, fontSize: '12px', background: 'transparent' }}>
                        {cleanDiff(report.diff_content).slice(0, 1000) + '...'}
                    </SyntaxHighlighter>
                </div>
                <div className="absolute inset-0 bg-gradient-to-t from-white via-white/50 to-transparent flex items-end justify-center pb-6">
                    <button 
                        onClick={() => setDiffModalVisible(true)}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-full shadow-lg hover:shadow-indigo-500/30 transition-all transform hover:-translate-y-1 font-medium flex items-center gap-2"
                    >
                        <ExpandOutlined /> 进入沉浸式 Diff 视图
                    </button>
                </div>
             </div>
             <DiffModal visible={diffModalVisible} onClose={() => setDiffModalVisible(false)} diffContent={report.diff_content} fileName={report.file_name} />
        </div>
      )}

      {/* Tables Section */}
      <div className="grid gap-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2">
                  <BugOutlined className="text-cyan-500" />
                  <h3 className="font-bold text-slate-700">下游依赖分析</h3>
              </div>
              <Table 
                 dataSource={data.downstream_dependency} 
                 rowKey={(r) => (r.file_path||'')+(r.line_number||'')} 
                 pagination={false} 
                 columns={[
                    { title: '服务名', dataIndex: 'service_name', width: 140, render: t => <span className="px-2 py-1 rounded bg-blue-50 text-blue-600 text-xs font-bold whitespace-nowrap">{t}</span> },
                    { title: '文件路径', dataIndex: 'file_path', width: 300, render: t => (
                        <div className="font-mono text-xs text-slate-600 break-all whitespace-normal">
                            {t}
                        </div>
                    )},
                    { title: '行号', dataIndex: 'line_number', width: 80, align: 'center', render: t => <span className="font-mono text-xs text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded">L{t}</span> },
                    { title: '影响描述', dataIndex: 'impact_description', render: t => <span className="text-xs text-slate-700 leading-relaxed block min-w-[200px]">{t}</span> },
                    { 
                        title: '依赖流程图', 
                        key: 'action',
                        width: 120,
                        align: 'center',
                        render: (_, record) => (
                            <Button 
                                type="link" 
                                size="small" 
                                icon={<BranchesOutlined />} 
                                onClick={() => {
                                    setCurrentFlowData(record);
                                    setFlowchartVisible(true);
                                }}
                            >
                                查看链路
                            </Button>
                        )
                    }
                 ]}
                 size="middle"
                 scroll={{ x: 'max-content' }}
              />
              {(!data.downstream_dependency || data.downstream_dependency.length === 0) && <div className="p-8 text-center text-slate-400">未检测到下游依赖</div>}
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2 border-t-4 border-t-indigo-500">
                  <CheckCircleOutlined className="text-indigo-500" />
                  <h3 className="font-bold text-slate-700">测试策略矩阵</h3>
              </div>
              <Table 
                 dataSource={data.test_strategy} 
                 rowKey="title" 
                 pagination={false} 
                 columns={[
                    { title: '优先级', dataIndex: 'priority', width: 100, render: t => {
                        const color = t === 'P0' ? 'bg-red-100 text-red-700' : t === 'P1' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700';
                        return <span className={`px-2 py-1 rounded text-xs font-bold ${color}`}>{t}</span>;
                    }},
                    { title: '场景标题', dataIndex: 'title', width: 250, render: t => <b className="text-slate-800">{t}</b> },
                    { title: 'Payload 示例', dataIndex: 'payload', render: t => <pre className="bg-slate-50 border border-slate-200 rounded p-2 text-[10px] text-slate-500 overflow-auto max-w-xs">{typeof t === 'object' ? JSON.stringify(t, null, 2) : t}</pre> },
                    { title: '验证点', dataIndex: 'validation', render: t => <span className="text-sm text-slate-600">{t}</span> },
                 ]}
                 size="middle"
              />
          </div>
      </div>
      <FlowchartModal 
        visible={flowchartVisible} 
        onClose={() => setFlowchartVisible(false)} 
        data={currentFlowData}
        sourceFile={report.file_name}
      />
    </div>
  );
};

export default App;
