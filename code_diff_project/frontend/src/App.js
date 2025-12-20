import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Empty, Spin } from 'antd';
import { 
    ClockCircleOutlined, PlayCircleOutlined, ProjectOutlined, 
    AppstoreOutlined, FolderOpenOutlined, RightOutlined, DownOutlined, 
    SafetyCertificateOutlined, LinkOutlined 
} from '@ant-design/icons';

import { REPORTS_URL, TASKS_URL } from './utils/api';
import ReportDetail from './components/ReportDetail';
import ProjectOverview from './components/ProjectOverview';
import TaskListView from './components/TaskListView';
import AnalysisConfigModal from './components/AnalysisConfigModal';
import ProjectRelations from './pages/ProjectRelations';
import AutoDiscoveryConfig from './components/AutoDiscoveryConfig';

function App() {
  const [reports, setReports] = useState([]);
  const [tasks, setTasks] = useState([]); 
  const [activeTab, setActiveTab] = useState('reports'); // 'reports' | 'tasks' | 'relations'
  const [selectedReportId, setSelectedReportId] = useState(null);
  const [selectedProject, setSelectedProject] = useState(null); 
  const [expandedProjects, setExpandedProjects] = useState([]); 
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false); // Used for loading state of button, though modal handles logic
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

  // Refresh data when switching tabs
  useEffect(() => {
      if (activeTab === 'reports') {
          fetchReports();
      } else if (activeTab === 'tasks') {
          // Immediately fetch tasks to show latest status
          axios.get(TASKS_URL).then(res => {
              setTasks(res.data);
              // Restart polling if there are active tasks and polling loop has stopped
              const hasActive = res.data.some(t => ['PENDING', 'PROCESSING'].includes(t.status));
              if (hasActive) {
                  startPolling();
              }
          }).catch(console.error);
      }
  }, [activeTab, fetchReports, startPolling]);

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
        
        {/* Main Navigation Tabs - 垂直排列 */}
        <div className="flex flex-col gap-2">
            <button 
                onClick={() => {
                    setActiveTab('reports');
                    setSelectedReportId(null);
                }}
                className={`w-full py-2.5 px-3 text-sm font-bold rounded-lg transition-all flex items-center gap-2.5 ${activeTab === 'reports' ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            >
                <AppstoreOutlined className="text-base" /> 服务分析
            </button>
            <button 
                onClick={() => setActiveTab('tasks')}
                className={`w-full py-2.5 px-3 text-sm font-bold rounded-lg transition-all flex items-center gap-2.5 ${activeTab === 'tasks' ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            >
                <ClockCircleOutlined className="text-base" /> 任务管理
            </button>
            <button 
                onClick={() => setActiveTab('relations')}
                className={`w-full py-2.5 px-3 text-sm font-bold rounded-lg transition-all flex items-center gap-2.5 ${activeTab === 'relations' ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            >
                <LinkOutlined className="text-base" /> 项目关联
            </button>
            <button 
                onClick={() => setActiveTab('auto-discovery')}
                className={`w-full py-2.5 px-3 text-sm font-bold rounded-lg transition-all flex items-center gap-2.5 ${activeTab === 'auto-discovery' ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            >
                <FolderOpenOutlined className="text-base" /> 自动发现
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
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {activeTab === 'reports' ? (
            <>
                {/* 项目列表标题 */}
                <div className="px-3 py-2 border-b border-slate-100 bg-slate-50/50 sticky top-0 z-10">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <FolderOpenOutlined className="text-xs" />
                        <span>分析项目</span>
                        <span className="ml-auto bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full text-[9px]">
                            {Object.keys(projectGroups).length}
                        </span>
                    </div>
                </div>
                
                <div className="p-3 space-y-1.5">
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
            </>
        ) : activeTab === 'tasks' ? (
            <>
                {/* 任务统计标题 */}
                <div className="px-3 py-2 border-b border-slate-100 bg-slate-50/50 sticky top-0 z-10">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <ClockCircleOutlined className="text-xs" />
                        <span>任务统计</span>
                    </div>
                </div>
                
                <div className="p-3">
                    <div className="text-xs text-slate-500 leading-relaxed">
                        <div className="mb-4 bg-slate-50 p-3 rounded-lg border border-slate-100">
                            <h3 className="font-bold text-slate-700 mb-1.5 flex items-center gap-1.5">
                                <ClockCircleOutlined className="text-blue-600" />
                                任务管理说明
                            </h3>
                            <p className="text-slate-600">此处展示所有历史分析任务的状态。您可以在右侧主界面查看详细的任务列表和执行日志。</p>
                        </div>
                        <div className="space-y-2.5">
                            <div className="flex justify-between items-center p-2 bg-slate-50 rounded-lg">
                                <span className="font-medium">总任务数</span>
                                <span className="font-bold text-slate-700 text-base">{tasks.length}</span>
                            </div>
                            <div className="flex justify-between items-center p-2 bg-green-50 rounded-lg">
                                <span className="font-medium text-green-700">已完成</span>
                                <span className="font-bold text-green-600 text-base">{tasks.filter(t=>t.status==='COMPLETED').length}</span>
                            </div>
                            <div className="flex justify-between items-center p-2 bg-red-50 rounded-lg">
                                <span className="font-medium text-red-700">失败</span>
                                <span className="font-bold text-red-600 text-base">{tasks.filter(t=>t.status==='FAILED').length}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </>
        ) : (
            <>
                {/* 项目关联标题 */}
                <div className="px-3 py-2 border-b border-slate-100 bg-slate-50/50 sticky top-0 z-10">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <LinkOutlined className="text-xs" />
                        <span>关联配置</span>
                    </div>
                </div>
                
                <div className="p-3">
                    <div className="text-xs text-slate-500 leading-relaxed">
                        <div className="bg-blue-50 p-3 rounded-lg border border-blue-100">
                            <h3 className="font-bold text-blue-700 mb-1.5 flex items-center gap-1.5">
                                <LinkOutlined className="text-blue-600" />
                                项目关联说明
                            </h3>
                            <p className="text-slate-600">在右侧主界面中配置主项目与关联项目的依赖关系，支持跨项目影响分析。</p>
                        </div>
                    </div>
                </div>
            </>
        )}
      </div>
    </div>
  );

  const renderMainContent = () => {
      if (activeTab === 'tasks') {
          return <TaskListView tasks={tasks} />;
      }
      
      if (activeTab === 'relations') {
          return <ProjectRelations />;
      }
      
      if (activeTab === 'auto-discovery') {
          return <AutoDiscoveryConfig />;
      }
      
      // Reports view
      if (currentReport) return <ReportDetail report={currentReport} onBack={() => setSelectedReportId(null)} />;
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
               {activeTab === 'reports' && <SafetyCertificateOutlined className="text-blue-600" />}
               {activeTab === 'tasks' && <ClockCircleOutlined className="text-blue-600" />}
               {activeTab === 'relations' && <LinkOutlined className="text-blue-600" />}
               {activeTab === 'auto-discovery' && <FolderOpenOutlined className="text-blue-600" />}
               {activeTab === 'reports' && '精准测试分析大屏'}
               {activeTab === 'tasks' && '分析任务监控台'}
               {activeTab === 'relations' && '项目关联管理'}
               {activeTab === 'auto-discovery' && '自动项目发现'}
            </h2>
            <p className="text-[10px] text-slate-500 mt-0.5">
               {activeTab === 'reports' && '基于代码差异与链路分析的智能评估系统'}
               {activeTab === 'tasks' && '实时监控分析任务执行状态'}
               {activeTab === 'relations' && '配置主项目与关联项目的依赖关系'}
               {activeTab === 'auto-discovery' && '自动发现 Git 组织下的所有项目并分析依赖关系'}
            </p>
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

export default App;
