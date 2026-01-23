import React, { useState } from 'react';
import { Button, Table, message } from 'antd';
import { 
    ArrowLeftOutlined, FileTextOutlined, ClockCircleOutlined, CodeOutlined, 
    ExpandOutlined, InfoCircleOutlined, ApiOutlined, AppstoreOutlined, 
    ArrowDownOutlined, BugOutlined, CheckCircleOutlined, SwapOutlined, 
    FolderOpenOutlined, BranchesOutlined, CopyOutlined, RightOutlined
} from '@ant-design/icons';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vs } from 'react-syntax-highlighter/dist/esm/styles/prism';
import DependencyGraph from './DependencyGraph';
import FlowchartModal from './FlowchartModal';
import DiffModal from './DiffModal';

const SmartHighlight = ({ text }) => {
    if (!text) return null;
    if (typeof text !== 'string') return text;

    // First split by markdown code blocks `code`
    const parts = text.split(/(`[^`]+`)/);
    
    return (
        <>
            {parts.map((part, i) => {
                // If it's a code block (wrapped in backticks)
                if (part.startsWith('`') && part.endsWith('`')) {
                    const content = part.slice(1, -1);
                    return (
                        <span key={i} className="font-mono text-[0.9em] mx-0.5 px-1 py-0.5 rounded bg-slate-100 text-pink-600 border border-slate-200/60 font-medium select-all">
                            {content}
                        </span>
                    );
                }
                
                // For normal text, try to highlight potential class/method/API names
                // Regex for:
                // 1. API paths: /v1/user/add (must start with / and have slashes)
                // 2. Java Package/Class/Method: com.example.Service.method or com.example.Service (dots followed by words)
                // 3. Class.Method: PointController.addPoint (PascalCase.camelCase)
                // 4. Class Names: PointManager (PascalCase, at least 4 chars)
                // 5. Method Calls: addPoint( (camelCase followed by paren)
                // 6. Service Names / Hyphenated: cloudE-pay-api
                // 7. CamelCase Variables: riskLevel (at least 4 chars)
                
                // Regex Explanation:
                // - API Path: \/[a-zA-Z0-9\/_\-]{2,}
                // - Java Full Name: \b[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)+\b(?:\(.*?\))?  (Matches com.pkg.Class or com.pkg.Class.method, optionally with params)
                // - Class.Method (Simple): \b[A-Z][a-zA-Z0-9]*\.[a-z][a-zA-Z0-9]*\b
                // - Method Call: \b[a-z][a-zA-Z0-9]*\(
                // - Service Name: \b[a-zA-Z0-9]+-[a-zA-Z0-9-]+\b
                // - Class Name: \b[A-Z][a-zA-Z0-9]{3,}\b
                // - Variable: \b[a-z][a-zA-Z0-9]{3,}\b
                
                const tokens = part.split(/(\/[a-zA-Z0-9\/_\-]{2,}|\b[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+(?:\(.*?\))?|\b[A-Z][a-zA-Z0-9]*\.[a-z][a-zA-Z0-9]*\b|\b[a-z][a-zA-Z0-9]*\(|\b[a-zA-Z0-9]+-[a-zA-Z0-9-]+\b|\b[A-Z][a-zA-Z0-9]{3,}\b|\b[a-z][a-zA-Z0-9]{3,}\b)/);
                
                return (
                    <span key={i}>
                        {tokens.map((token, j) => {
                            const isApi = token.startsWith('/') && token.includes('/');
                            const isJavaFullName = token.includes('.') && /^[a-zA-Z_]/.test(token); // Matches package.Class.method
                            const isClassMethod = /^[A-Z][a-zA-Z0-9]*\.[a-z]/.test(token);
                            const isClass = /^[A-Z][a-zA-Z0-9]{3,}$/.test(token);
                            const isMethod = /^[a-z][a-zA-Z0-9]*\(/.test(token);
                            const isService = /^[a-zA-Z0-9]+-[a-zA-Z0-9-]+/.test(token);
                            const isVariable = /^[a-z][a-zA-Z0-9]{3,}$/.test(token) && !token.includes(' ');

                            if (isApi || isJavaFullName || isClassMethod || isClass || isMethod || isService || isVariable) {
                                return (
                                    <span key={j} className="font-mono text-[0.9em] mx-0.5 px-1 py-0.5 rounded bg-slate-50 text-indigo-600 border border-indigo-100/50 hover:bg-indigo-50 transition-colors cursor-text break-all">
                                        {token}
                                    </span>
                                );
                            }
                            return token;
                        })}
                    </span>
                );
            })}
        </>
    );
};

const ReportDetail = ({ report, onBack }) => {
  // Ensure data is an object, handling potential double-serialization
  const data = React.useMemo(() => {
      let raw = report.report_json;
      if (!raw) return {};
      
      // Try parsing if it's a string
      if (typeof raw === 'string') {
          try { 
              const parsed = JSON.parse(raw);
              // Handle double-encoded JSON string
              if (typeof parsed === 'string') {
                  try { return JSON.parse(parsed); } catch(e) { return {}; }
              }
              return parsed;
          } catch(e) { return {}; }
      }
      return raw;
  }, [report.report_json]);

  const [diffModalVisible, setDiffModalVisible] = useState(false);
  const [flowchartVisible, setFlowchartVisible] = useState(false);
  const [currentFlowData, setCurrentFlowData] = useState(null);
  const [detailsTab, setDetailsTab] = useState('intent'); // 'intent' or 'rules'
  
  // Collapse States
  const [isDataFlowOpen, setIsDataFlowOpen] = useState(true);
  const [isApiImpactOpen, setIsApiImpactOpen] = useState(true); // Keep API impact open by default as it's important
  const [isDiffOpen, setIsDiffOpen] = useState(true);

  // Helper functions
  const cleanJsonString = (str) => {
      if (typeof str !== 'string') return JSON.stringify(str, null, 2);
      // Remove comments (// ...) 
      let cleaned = str.replace(/\/\/.*$/gm, '').trim();
      try {
          const parsed = JSON.parse(cleaned);
          return JSON.stringify(parsed, null, 2);
      } catch (e) {
          return cleaned;
      }
  };

  const renderField = (value) => {
    if (!value) return <span className="text-slate-400">N/A</span>;
    if (typeof value === 'string') {
        // Try to parse JSON string if it looks like an array or object
        if ((value.startsWith('[') && value.endsWith(']')) || (value.startsWith('{') && value.endsWith('}'))) {
            try {
                const parsed = JSON.parse(value);
                return renderField(parsed);
            } catch (e) {
                // Ignore parse error, treat as string
            }
        }

        // Auto-format numbered lists (e.g., "1. xxx; 2. xxx", "1、xxx")
        // Support dot (.) or Chinese comma (、) as separator
        const listMatch = value.match(/\d+[\.\、]\s/);
        if (listMatch) {
            // Split looking ahead for number + separator
            const items = value.split(/(?=\d+[\.\、]\s)/).filter(item => item.trim());
            if (items.length > 1) {
                return (
                    <ul className="list-none space-y-3">
                        {items.map((item, idx) => {
                            // Check for sub-items (e.g. "(1) sub-item")
                            // Remove the number prefix (e.g. "1. " or "1、 ")
                            const cleanItem = item.replace(/^\d+[\.\、]\s*/, '').replace(/;$/, '').trim();
                            let mainContent = cleanItem;
                            let subItems = [];

                            // Support both English (1) and Chinese （1） parentheses
                            // Use capturing group to split but keep the delimiters
                            const splitRegex = /([\(（]\d+[\)）])/;
                            if (cleanItem.match(splitRegex)) {
                                const parts = cleanItem.split(splitRegex);
                                // parts will look like: ["Main text", "(1)", "Sub text 1", "(2)", "Sub text 2"]
                                if (parts.length > 1) {
                                    mainContent = parts[0].trim();
                                    
                                    // Reconstruct sub-items
                                    subItems = [];
                                    for (let i = 1; i < parts.length; i += 2) {
                                        // parts[i] is the marker e.g. "(1)"
                                        // parts[i+1] is the content
                                        if (i + 1 < parts.length) {
                                            const content = parts[i+1].trim();
                                            if (content) {
                                                subItems.push(content);
                                            }
                                        }
                                    }
                                }
                            }

                            return (
                                <li key={idx} className="flex gap-2 items-start">
                                    <div className="w-5 h-5 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 shadow-sm">
                                        {idx + 1}
                                    </div>
                                    <div className="flex-1">
                                        <div className="leading-6 font-medium text-slate-700">{mainContent}</div>
                                        {subItems.length > 0 && (
                                            <ul className="mt-1.5 space-y-1 ml-1">
                                                {subItems.map((sub, sIdx) => (
                                                    <li key={sIdx} className="text-xs text-slate-500 flex gap-2 items-start bg-slate-50 p-1.5 rounded border border-slate-100/50">
                                                        <span className="font-mono text-green-600 font-bold opacity-70">({sIdx + 1})</span>
                                                        <span>{sub}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        )}
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                );
            }
        }
        return value;
    }
    // If it's a string but didn't match specific list patterns, still render it with detail item logic (highlighting, etc.)
    if (typeof value === 'string') {
        return renderDetailItem(value);
    }
    
    if (Array.isArray(value)) {
        return (
            <ul className="list-none space-y-3">
                {value.map((item, idx) => (
                    <li key={idx} className="flex gap-2 items-start">
                        <div className="w-5 h-5 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 shadow-sm">
                            {idx + 1}
                        </div>
                        <div className="flex-1 leading-6 font-medium text-slate-700">
                             {typeof item === 'string' ? renderDetailItem(item) : renderField(item)}
                        </div>
                    </li>
                ))}
            </ul>
        );
    }

    if (typeof value === 'object') {
        // Handle structured item with summary and details
        if (value && value.summary && (value.details === undefined || Array.isArray(value.details))) {
            return (
                <div className="w-full">
                     <div className="font-bold text-slate-800 text-sm leading-relaxed mb-2 whitespace-pre-wrap">{value.summary}</div>
                     {value.details && value.details.length > 0 && (
                        <div className="space-y-1.5 bg-slate-50 p-2.5 rounded-md border border-slate-100">
                            {value.details.map((detail, dIdx) => (
                                <div key={dIdx} className="text-xs text-slate-600 flex gap-2 items-start">
                                    <span className="w-1.5 h-1.5 rounded-full bg-slate-400 mt-1.5 flex-shrink-0 opacity-60"></span>
                                    <span className="leading-relaxed block w-full whitespace-pre-wrap break-words">{renderDetailItem(detail)}</span>
                                </div>
                            ))}
                        </div>
                     )}
                </div>
            );
        }

        // Handle Cross Service Impact (Object with service names as keys)
        // Detect if values look like { file_path, impact_description } OR arrays of such objects
        const keys = Object.keys(value);
        const firstValue = value[keys[0]];
        const isCrossService = keys.length > 0 && (
            (firstValue && typeof firstValue === 'object' && (firstValue.impact_description || firstValue.file_path)) || 
            (Array.isArray(firstValue) && firstValue.length > 0 && (firstValue[0].impact_description || firstValue[0].file_path))
        );

        if (isCrossService) {
            // Flatten the structure for rendering: [ {service, ...info}, ... ]
            let flatItems = [];
            keys.forEach(serviceName => {
                const itemOrArray = value[serviceName];
                if (Array.isArray(itemOrArray)) {
                    itemOrArray.forEach(item => flatItems.push({ serviceName, ...item }));
                } else {
                    flatItems.push({ serviceName, ...itemOrArray });
                }
            });

            return (
                <ul className="list-none space-y-3">
                    {flatItems.map((info, idx) => (
                        <li key={idx} className="flex gap-2 items-start">
                            <div className="w-5 h-5 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 shadow-sm">
                                {idx + 1}
                            </div>
                            <div className="flex-1">
                                    <div className="font-bold text-slate-700 text-xs mb-1 bg-slate-100 inline-block px-1.5 py-0.5 rounded border border-slate-200">
                                    {info.serviceName}
                                    </div>
                                    <div className="text-slate-600 text-xs leading-relaxed">
                                    {info.impact_description || '暂无详细描述'}
                                    </div>
                                    {info.file_path && (
                                        <div className="mt-1 font-mono text-[10px] text-slate-400 break-all bg-slate-50 p-1 rounded border border-slate-100/50">
                                        {info.file_path}:{info.line_number}
                                        </div>
                                    )}
                            </div>
                        </li>
                    ))}
                </ul>
            );
        }

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
        
        // Handle structured Functional Impact (JSON with specific keys)
        if (value.risks || value.data_flow || value.api_impact || value.entry_points || value.business_scenario) {
             const sections = [
                { title: '业务场景', content: value.business_scenario, color: 'blue', collapsible: false },
                { title: '数据流向', content: value.data_flow, color: 'indigo', collapsible: true, isOpen: isDataFlowOpen, toggle: () => setIsDataFlowOpen(!isDataFlowOpen) },
                { title: 'API 影响', content: value.api_impact, color: 'purple', collapsible: true, isOpen: isApiImpactOpen, toggle: () => setIsApiImpactOpen(!isApiImpactOpen) },
                { title: '潜在风险', content: value.risks, color: 'red', collapsible: false },
                { title: '关联入口', content: value.entry_points, color: 'orange', collapsible: false },
             ].filter(s => s.content && (Array.isArray(s.content) ? s.content.length > 0 : true));
             
             return (
                <div className="space-y-4">
                    {sections.map((section, idx) => (
                        <div key={idx} className="text-xs">
                            <div 
                                className={`font-bold mb-1.5 flex items-center gap-1.5 text-${section.color}-700 ${section.collapsible ? 'cursor-pointer hover:opacity-80 select-none' : ''}`}
                                onClick={section.collapsible ? section.toggle : undefined}
                            >
                                <span className={`w-1.5 h-1.5 rounded-full bg-${section.color}-500`}></span>
                                {section.title}
                                {section.collapsible && (
                                    <span className="ml-auto text-[10px] text-slate-400 font-normal bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100 flex items-center gap-1">
                                        {section.isOpen ? '收起' : '点击展开'} 
                                        <RightOutlined className={`transform transition-transform ${section.isOpen ? 'rotate-90' : ''} text-[8px]`} />
                                    </span>
                                )}
                            </div>
                            
                            {(!section.collapsible || section.isOpen) && (
                                <div className="animate-fadeIn">
                                    {Array.isArray(section.content) ? (
                                        <ul className="space-y-2 pl-1">
                                            {section.content.map((item, i) => {
                                                if (typeof item === 'object' && item !== null && item.summary) {
                                                    return (
                                                        <li key={i} className="flex gap-2 items-start text-slate-600 bg-slate-50/50 p-2 rounded-lg border border-slate-100 shadow-sm">
                                                             <div className="w-5 h-5 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 shadow-sm">
                                                                {i + 1}
                                                             </div>
                                                             <div className="flex-1">
                                                                <div className="font-medium text-slate-800 leading-relaxed"><SmartHighlight text={item.summary} /></div>
                                                                {item.details && Array.isArray(item.details) && item.details.length > 0 && (
                                                                    <div className="mt-2 space-y-1.5">
                                                                        {item.details.map((detail, dIdx) => (
                                                                            <div key={dIdx} className="text-xs text-slate-500 flex gap-2 items-start bg-white p-1.5 rounded border border-slate-100">
                                                                                <span className="w-1.5 h-1.5 rounded-full bg-slate-300 mt-1.5 flex-shrink-0"></span>
                                                                                <span className="leading-relaxed block w-full">{renderDetailItem(detail)}</span>
                                                                            </div>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                             </div>
                                                        </li>
                                                    );
                                                }
                                                return (
                                                    <li key={i} className="flex gap-2 items-start text-slate-600 bg-slate-50/50 p-1 rounded-sm">
                                                        <div className="w-5 h-5 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 shadow-sm">
                                                            {i + 1}
                                                        </div>
                                                        <span className="flex-1 leading-6">
                                                            {typeof item === 'string' ? renderDetailItem(item) : JSON.stringify(item)}
                                                        </span>
                                                    </li>
                                                );
                                            })}
                                        </ul>
                                    ) : (
                                        <div className="text-slate-600 bg-slate-50/50 p-1.5 rounded-sm leading-relaxed border-l-2 border-slate-100 pl-2">
                                            {renderDetailItem(section.content)}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
             );
        }

        return <pre className="whitespace-pre-wrap text-xs bg-slate-50 p-3 rounded-lg border border-slate-100 text-slate-600 font-mono">{JSON.stringify(value, null, 2)}</pre>;
    }
    return String(value);
  };

  const renderDetailItem = (text) => {
      if (typeof text !== 'string') return text;
      
      // 1. Handle Arrow Flows ("->" or "→")
      if (text.includes('→') || text.includes('->')) {
          const arrowParts = text.split(/→|->/).map(p => p.trim()).filter(p => p);
          if (arrowParts.length > 1) {
              return (
                  <div className="flex flex-col gap-2 w-full mt-1">
                      {arrowParts.map((part, idx) => (
                          <div key={idx} className="flex flex-col items-start relative">
                              {/* Connector Line (except for last item) */}
                              {idx < arrowParts.length - 1 && (
                                  <div className="absolute left-2.5 top-6 bottom-0 w-0.5 bg-slate-200 h-full -mb-2 z-0"></div>
                              )}
                              
                              <div className="flex gap-2 items-start z-10 relative">
                                  {/* Step Number/Icon */}
                                  <div className="w-5 h-5 rounded-full bg-indigo-50 text-indigo-600 border border-indigo-100 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 select-none shadow-sm">
                                      {idx + 1}
                                  </div>
                                  
                                  {/* Content */}
                                  <div className="bg-slate-50 border border-slate-100 rounded px-2 py-1 text-slate-700 leading-relaxed text-xs">
                                      <SmartHighlight text={part} />
                                  </div>
                              </div>
                              
                              {/* Down Arrow Icon (visual only, between items) */}
                              {idx < arrowParts.length - 1 && (
                                  <div className="ml-2.5 my-0.5 text-slate-300 text-[10px]">
                                      <ArrowDownOutlined />
                                  </div>
                              )}
                          </div>
                      ))}
                  </div>
              );
          }
      }

      // 2. Handle Numbered Lists ("1. ", "2. ")
      // Split by "1. ", "2. " patterns occurring at start or after punctuation/space
      // Using lookahead to keep the number with the item
      const parts = text.split(/(?:^|[\s。；;])(?=\d+[.、．]\s*)/).filter(p => p.trim());
      
      if (parts.length > 1) {
          return (
              <div className="flex flex-col gap-1.5 w-full mt-0.5">
                  {parts.map((part, idx) => {
                      const cleanPart = part.trim();
                      // Highlight the number prefix
                      const match = cleanPart.match(/^(\d+[.、．]\s*)(.*)/s);
                      if (match) {
                          return (
                              <div key={idx} className="flex gap-2 items-start">
                                  <div className="w-5 h-5 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 shadow-sm">
                                      {match[1].replace(/[.、．]/, '').trim()}
                                  </div>
                                  <span className="flex-1 leading-relaxed text-slate-700">
                                      <SmartHighlight text={match[2]} />
                                  </span>
                              </div>
                          );
                      }
                      return <div key={idx}><SmartHighlight text={cleanPart} /></div>;
                  })}
              </div>
          );
      }
      return <SmartHighlight text={text} />;
  };

  const cleanDiff = (diffText) => {
    if (!diffText) return '';
    return diffText.split('\n').filter(line => !line.startsWith('diff --git') && !line.startsWith('index ') && !line.startsWith('new file mode') && !line.startsWith('deleted file mode')).join('\n');
  };

  const renderRiskBadge = (level) => {
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
    return <span className={`px-2.5 py-0.5 text-xs font-bold rounded-full border ${colorClass} shadow-sm`}>{level}</span>;
  };

  return (
    <div className="space-y-3 max-w-6xl mx-auto pb-6 font-sans">
      
      {/* Header */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 transition-all hover:shadow-md">

         <div className="flex justify-between items-start">
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
                        <span className="flex items-center gap-1 bg-blue-50/50 text-blue-600 px-1.5 py-0.5 rounded border border-blue-100/50" title="工作分支">
                            <BranchesOutlined /> {report.source_branch || 'master'}
                        </span>
                        {report.target_branch && (
                            <>
                                <span className="text-gray-300">/</span>
                                <span className="flex items-center gap-1 bg-purple-50/50 text-purple-600 px-1.5 py-0.5 rounded border border-purple-100/50" title="比对范围">
                                    <SwapOutlined /> {report.target_branch}
                                </span>
                            </>
                        )}
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
      </div>

      <div className="grid grid-cols-1 gap-3">
          {/* Summary Section */}
          <div className="bg-gradient-to-r from-slate-50 to-white rounded-xl shadow-sm border border-slate-200 p-5 relative overflow-hidden group">
              <div className="relative z-10">
                  <div className="flex items-center gap-3 mb-4 border-b border-slate-100 pb-3">
                      <span className="text-sm font-bold text-slate-700 uppercase tracking-widest flex items-center gap-2">
                          变更总结
                      </span>
                  </div>
                  
                  <div className="space-y-4">
                      {/* Core Change Summary */}
                      <div>
                          <div className="text-xs font-bold text-slate-500 mb-2 flex items-center gap-1.5 uppercase tracking-wider">
                              <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                              核心变更
                          </div>
                          <div className="text-sm text-slate-700 font-medium leading-relaxed bg-white shadow-sm p-3.5 rounded-lg border border-slate-100/80 hover:border-blue-100 transition-colors">
                              {data.change_intent && Array.isArray(data.change_intent) ? (
                                  <ul className="space-y-2">
                                      {data.change_intent.map((intent, idx) => (
                                          <li key={idx} className="flex gap-2 items-start">
                                              <span className="text-blue-400 mt-1.5 text-[6px]">●</span>
                                              <span className="flex-1"><SmartHighlight text={intent.summary} /></span>
                                          </li>
                                      ))}
                                  </ul>
                              ) : (
                                  <SmartHighlight text={typeof report.change_intent === 'string' ? report.change_intent : '暂无摘要'} />
                              )}
                          </div>
                      </div>

                      {/* Cross Service Impact Summary */}
                      {data.cross_service_impact && data.cross_service_impact !== '无' && (
                          <div className="animate-fadeIn">
                              <div className="text-xs font-bold text-slate-500 mb-2 flex items-center gap-1.5 uppercase tracking-wider">
                                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500"></span>
                                  跨服务影响
                              </div>
                              <div className="text-xs text-slate-600 font-medium leading-relaxed bg-orange-50/30 shadow-sm p-3.5 rounded-lg border border-orange-100 hover:border-orange-200 transition-colors">
                                  <div className="flex gap-2 items-start">
                                      <ApiOutlined className="text-orange-400 mt-0.5 text-sm" />
                                      <div className="flex-1">
                                          <SmartHighlight text={
                                              data.cross_service_impact_summary || 
                                              (typeof data.cross_service_impact === 'string' 
                                                  ? (data.cross_service_impact.length > 100 ? data.cross_service_impact.slice(0, 100) + '...' : data.cross_service_impact)
                                                  : JSON.stringify(data.cross_service_impact))
                                          } />
                                      </div>
                                  </div>
                              </div>
                          </div>
                      )}
                  </div>
              </div>
          </div>

          {/* Visual Topology Graph */}
          <DependencyGraph data={data} fileName={report.file_name} />

          {/* Change Details */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <div className="flex items-center gap-2 mb-3 pb-3 border-b border-gray-50">
                  <h3 className="font-bold text-gray-800 text-sm">变更详情分析</h3>
              </div>
              
              <div className="space-y-3">
                  {/* Change Details Tabs */}
                  <div className="mb-3">
                      <div className="flex items-center gap-6 border-b border-slate-100 mb-3 px-1">
                          <button 
                              onClick={() => setDetailsTab('intent')}
                              className={`flex items-center gap-2 pb-2 text-sm font-bold border-b-2 transition-all outline-none ${
                                  detailsTab === 'intent' 
                                  ? 'text-blue-600 border-blue-500' 
                                  : 'text-slate-400 border-transparent hover:text-slate-600'
                              }`}
                          >
                              <FileTextOutlined /> 变更详情
                          </button>
                          
                          <button 
                              onClick={() => setDetailsTab('rules')}
                              className={`flex items-center gap-2 pb-2 text-sm font-bold border-b-2 transition-all outline-none ${
                                  detailsTab === 'rules' 
                                  ? 'text-emerald-600 border-emerald-500' 
                                  : 'text-slate-400 border-transparent hover:text-slate-600'
                              }`}
                          >
                              <CheckCircleOutlined /> 逻辑规则
                              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                                  detailsTab === 'rules' ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-100 text-slate-500'
                              }`}>
                                  {data.business_rules ? data.business_rules.length : 0}
                              </span>
                          </button>
                      </div>

                      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm text-slate-700 leading-relaxed min-h-[120px]">
                          {detailsTab === 'intent' ? (
                              renderField(report.change_intent || '暂无分析结果')
                          ) : (
                              <div className="overflow-hidden bg-white border border-slate-200 rounded-md">
                                  {(!data.business_rules || data.business_rules.length === 0) ? (
                                      <div className="text-center py-6 text-slate-400">
                                          <div className="mb-2"><CheckCircleOutlined className="text-2xl opacity-20" /></div>
                                          <div>暂无逻辑规则变更</div>
                                          <div className="text-xs opacity-60 mt-1">（如果是历史报告，请重新运行分析以提取规则）</div>
                                      </div>
                                  ) : (
                                      <Table 
                                          dataSource={data.business_rules}
                                          rowKey={(r, i) => i}
                                          pagination={false}
                                          size="small"
                                          bordered
                                          columns={[
                                              { 
                                                  title: '业务场景', 
                                                  dataIndex: 'scenario', 
                                                  width: 200,
                                                  render: (text, record) => (
                                                      <div className="font-bold text-slate-700 text-xs whitespace-normal" style={{ wordBreak: 'break-word' }}>
                                                          {text || '通用规则'}
                                                          {record.related_file && (
                                                              <div className="mt-1 font-mono text-[9px] text-slate-400 font-normal whitespace-normal" style={{ wordBreak: 'break-word' }} title={record.related_file}>
                                                                  <FileTextOutlined className="mr-1" />
                                                                  {record.related_file.split('/').pop()}
                                                              </div>
                                                          )}
                                                      </div>
                                                  )
                                              },
                                              { 
                                                  title: '变更前 (Old)', 
                                                  dataIndex: 'old_rule', 
                                                  width: 280,
                                                  render: t => <div className="text-xs text-slate-500 bg-slate-50 p-1.5 rounded border border-slate-100 whitespace-pre-wrap" style={{ wordBreak: 'break-word' }}>{t || '-'}</div> 
                                              },
                                              { 
                                                  title: '变更后 (New)', 
                                                  dataIndex: 'new_rule', 
                                                  width: 280,
                                                  render: t => <div className="text-xs text-slate-800 font-medium bg-emerald-50/50 p-1.5 rounded border border-emerald-100 whitespace-pre-wrap" style={{ wordBreak: 'break-word' }}>{t || '-'}</div> 
                                              },
                                              { 
                                                  title: '影响', 
                                                  dataIndex: 'impact',
                                                  render: t => <div className="text-xs text-slate-600 whitespace-pre-wrap break-words">{t}</div> 
                                              }
                                          ]}
                                      />
                                  )}
                              </div>
                          )}
                      </div>
                  </div>

                  {/* Impact Grid */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {/* Cross Service Impact */}
                      <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-all">
                          <div className="flex items-center gap-2 text-xs font-bold text-slate-700 uppercase tracking-wider mb-3 pb-2 border-b border-slate-200/50">
                              <ApiOutlined className="text-sm text-orange-500" /> 跨服务影响
                          </div>
                          <div className="text-sm text-slate-700 font-medium leading-loose">
                              {/* Force use of renderDetailItem to ensure highlighting logic is applied */}
                              {(() => {
                                  const content = data.cross_service_impact;
                                  if (typeof content === 'string') {
                                      // Try to split by periods if it's a long paragraph (Fallback for legacy reports)
                                      const sentences = content.split(/([。！；]|(?<!\w)\.(?=\s))/).reduce((acc, part, i, arr) => {
                                          if (i % 2 === 0) { // Content part
                                              if (part.trim()) acc.push(part.trim() + (arr[i+1] || ''));
                                          }
                                          return acc;
                                      }, []);

                                      if (sentences.length > 1) {
                                          return (
                                              <ul className="list-none space-y-3">
                                                  {sentences.map((sentence, idx) => (
                                                      <li key={idx} className="flex gap-2 items-start">
                                                          <div className="w-5 h-5 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 shadow-sm">
                                                              {idx + 1}
                                                          </div>
                                                          <div className="flex-1 leading-relaxed">
                                                              {renderDetailItem(sentence)}
                                                          </div>
                                                      </li>
                                                  ))}
                                              </ul>
                                          );
                                      }
                                      return renderDetailItem(content);
                                  }
                                  // If it's an array (New format), renderField handles it as a list automatically
                                  return renderField(content);
                              })()}
                          </div>
                      </div>

                      {/* Functional Impact */}
                      <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-all">
                          <div className="flex items-center gap-2 text-xs font-bold text-slate-700 uppercase tracking-wider mb-3 pb-2 border-b border-slate-200/50">
                              <AppstoreOutlined className="text-sm text-green-500" /> 功能影响
                          </div>
                          <div className="text-sm text-slate-700 font-medium leading-loose whitespace-pre-wrap">
                              {renderField(data.functional_impact)}
                          </div>
                      </div>
                  </div>
              </div>
          </div>
      </div>

      {/* Affected APIs Section */}
      {data.affected_apis && data.affected_apis.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden p-5">
              <h3 className="font-bold text-slate-700 flex items-center gap-2 mb-4">
                  <ApiOutlined className="text-purple-500" /> 影响接口 (Affected APIs)
              </h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {data.affected_apis.map((api, idx) => (
                      <div key={idx} className="bg-purple-50/30 border border-purple-100 rounded-lg p-3 flex flex-col gap-2 hover:bg-purple-50 transition-colors">
                          <div className="flex items-center gap-2">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                                  api.method === 'GET' ? 'bg-blue-100 text-blue-700' :
                                  api.method === 'POST' ? 'bg-green-100 text-green-700' :
                                  api.method === 'DELETE' ? 'bg-red-100 text-red-700' :
                                  'bg-orange-100 text-orange-700'
                              }`}>
                                  {api.method}
                              </span>
                          </div>
                          <code className="text-xs font-mono text-slate-700 break-all bg-white px-2 py-1 rounded border border-slate-200">
                              {api.url}
                          </code>
                          <div className="text-xs text-slate-500 mt-1 leading-relaxed">
                              {api.description}
                          </div>
                      </div>
                  ))}
              </div>
          </div>
      )}

      {/* Frontend Calls Section */}
      {data.frontend_calls && data.frontend_calls.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden p-5">
              <h3 className="font-bold text-slate-700 flex items-center gap-2 mb-4">
                  <AppstoreOutlined className="text-blue-500" /> 前端调用信息 (Frontend Calls)
                  <span className="text-xs font-normal text-slate-500 bg-blue-50 px-2 py-1 rounded">
                      发现 {data.frontend_calls.length} 个前端调用
                  </span>
              </h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {data.frontend_calls.map((call, idx) => (
                      <div key={idx} className="bg-blue-50/30 border border-blue-100 rounded-lg p-3 flex flex-col gap-2 hover:bg-blue-50 transition-colors">
                          <div className="flex items-center gap-2">
                              <AppstoreOutlined className="text-blue-600" />
                              <span className="font-bold text-blue-700 text-sm">{call.component}</span>
                          </div>
                          <div className="text-xs text-slate-600 space-y-1">
                              <div className="flex items-start gap-1">
                                  <span className="text-slate-400">📄</span>
                                  <code className="font-mono text-[10px] break-all">{call.file_path}</code>
                              </div>
                              <div className="flex items-center gap-1">
                                  <span className="text-slate-400">📍</span>
                                  <span>第 {call.line_number} 行</span>
                              </div>
                              <div className="flex items-center gap-1">
                                  <span className="text-slate-400">🔗</span>
                                  <span className="font-mono bg-white px-1.5 py-0.5 rounded border border-blue-100 text-[10px]">
                                      {call.call_type}
                                  </span>
                              </div>
                              {call.backend_api && (
                                  <div className="mt-2 pt-2 border-t border-blue-200">
                                      <div className="text-[10px] text-slate-500 mb-1">关联后端 API:</div>
                                      <code className="font-mono text-[10px] text-blue-700 bg-white px-1.5 py-0.5 rounded border border-blue-200 block break-all">
                                          {call.backend_api}
                                      </code>
                                  </div>
                              )}
                          </div>
                      </div>
                  ))}
              </div>
          </div>
      )}

      {/* Diff Preview */}
      {report.diff_content && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
             <div 
                className="px-5 py-3 border-b border-slate-100 flex justify-between items-center bg-slate-50/50 cursor-pointer hover:bg-slate-100 transition-colors"
                onClick={() => setIsDiffOpen(!isDiffOpen)}
             >
                 <h3 className="font-bold text-slate-700 flex items-center gap-2">
                     <CodeOutlined className="text-indigo-500" /> 代码变更预览
                     <span className="text-xs font-mono font-normal text-slate-500 bg-white border border-slate-200 px-2 py-0.5 rounded ml-2 shadow-sm">
                        {report.project_name}/{report.file_name}
                     </span>
                 </h3>
                 <span className="text-xs text-slate-400 flex items-center gap-1 font-medium">
                    {isDiffOpen ? '收起' : '点击展开'} 
                    <RightOutlined className={`transform transition-transform ${isDiffOpen ? 'rotate-90' : ''} text-[10px]`} />
                 </span>
             </div>
             
             {isDiffOpen && (
                 <div className="relative group animate-fadeIn">
                    <div style={{ maxHeight: '400px', overflow: 'hidden' }} className="opacity-90">
                        <SyntaxHighlighter language="diff" style={vs} showLineNumbers={true} customStyle={{ margin: 0, fontSize: '12px', background: 'transparent' }}>
                            {cleanDiff(report.diff_content).slice(0, 2000) + (report.diff_content.length > 2000 ? '...' : '')}
                        </SyntaxHighlighter>
                    </div>
                    <div className="absolute inset-0 bg-gradient-to-t from-white via-white/30 to-transparent flex items-end justify-center pb-6 pointer-events-none">
                        <button 
                            onClick={(e) => {
                                e.stopPropagation();
                                setDiffModalVisible(true);
                            }}
                            className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-full shadow-lg hover:shadow-indigo-500/30 transition-all transform hover:-translate-y-1 font-medium flex items-center gap-2 pointer-events-auto"
                        >
                            <ExpandOutlined /> 进入沉浸式 Diff 视图
                        </button>
                    </div>
                 </div>
             )}
             <DiffModal visible={diffModalVisible} onClose={() => setDiffModalVisible(false)} diffContent={report.diff_content} fileName={report.file_name} />
        </div>
      )}

      {/* Tables Section */}
      <div className="grid gap-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="px-5 py-2 border-b border-slate-100 flex items-center gap-2">
                  <BugOutlined className="text-cyan-500" />
                  <h3 className="font-bold text-slate-700 text-sm">下游依赖分析</h3>
              </div>
              <Table 
                 dataSource={data.downstream_dependency} 
                 rowKey={(r) => (r.file_path||'')+(r.line_number||'')} 
                 pagination={false} 
                 columns={[
                    { title: '服务名', dataIndex: 'service_name', width: 140, render: t => <span className="px-2 py-1 rounded bg-blue-50 text-blue-600 text-xs font-bold whitespace-nowrap">{t}</span> },
                    { title: '文件路径', dataIndex: 'file_path', width: 300, render: t => (
                        <div className="font-mono text-xs text-slate-600 break-all whitespace-normal">
                            {t.replace(/^.*[\\/]workspace[\\/][^\\/]+[\\/]/, '')}
                        </div>
                    )},
                    { title: '行号', dataIndex: 'line_number', width: 150, align: 'center', render: t => <span className="font-mono text-xs text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded whitespace-nowrap">Line: {t}</span> },
                    { 
                        title: '影响描述', 
                        dataIndex: 'impact_description', 
                        width: 400, // Fixed width
                        render: t => <div className="text-xs text-slate-700 leading-relaxed whitespace-normal break-words" style={{ wordBreak: 'break-word' }}>{t}</div> 
                    },
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
              <div className="px-5 py-2 border-b border-slate-100 flex items-center gap-2 border-t-4 border-t-indigo-500">
                  <CheckCircleOutlined className="text-indigo-500" />
                  <h3 className="font-bold text-slate-700 text-sm">测试策略矩阵</h3>
              </div>
              <div className="overflow-x-auto">
                  <Table 
                     dataSource={data.test_strategy} 
                     rowKey="title" 
                     pagination={false} 
                     size="middle"
                     bordered={true}
                     className="test-strategy-table"
                     rowClassName={() => 'test-strategy-row'}
                     scroll={{ x: 'max-content' }}
                     columns={[
                        { 
                            title: <div className="text-center font-bold text-slate-700">优先级</div>, 
                            dataIndex: 'priority', 
                            width: 60,
                            fixed: 'left',
                            align: 'center',
                            onCell: () => ({ 
                                style: { 
                                    verticalAlign: 'middle', 
                                    textAlign: 'center',
                                    padding: '12px 4px',
                                    backgroundColor: '#fafafa'
                                } 
                            }),
                            render: t => {
                                const colors = { 
                                    'P0': 'text-red-600 bg-red-50 border-red-200 shadow-sm', 
                                    'P1': 'text-orange-600 bg-orange-50 border-orange-200 shadow-sm', 
                                    'P2': 'text-blue-600 bg-blue-50 border-blue-200 shadow-sm' 
                                };
                                return <span className={`inline-block px-2 py-0.5 rounded border text-[10px] font-bold ${colors[t] || 'text-slate-600 bg-slate-50'}`}>{t}</span>;
                            }
                        },
                        { 
                            title: <div className="text-center font-bold text-slate-700">场景标题</div>, 
                            dataIndex: 'title', 
                            width: 150,
                            fixed: 'left',
                            align: 'center',
                            onCell: () => ({ 
                                style: { 
                                    verticalAlign: 'middle', 
                                    padding: '12px 8px',
                                    backgroundColor: '#fafafa',
                                    textAlign: 'center'
                                } 
                            }),
                            render: t => (
                                <div className="inline-flex items-center justify-center">
                                    <div className="relative">
                                        <div className="text-blue-600 text-xs px-2 py-1 bg-blue-50 border-l-4 border-blue-500 rounded-r shadow-sm" style={{ fontWeight: 900 }}>
                                            {t}
                                        </div>
                                    </div>
                                </div>
                            )
                        },
                        { 
                            title: <div className="font-bold text-slate-700">测试步骤</div>, 
                            dataIndex: 'steps', 
                            width: 400,
                            onCell: () => ({ 
                                style: { 
                                    verticalAlign: 'top', 
                                    padding: '12px 8px',
                                    lineHeight: '1.5'
                                } 
                            }),
                            render: (text) => {
                                if (!text) return <span className="text-slate-400">-</span>;
                                
                                // 高亮步骤标题的函数（只高亮第一个冒号前的文字）
                                const highlightStepTitles = (str) => {
                                    // 找到第一个冒号的位置（中文冒号：或英文冒号:）
                                    const firstColonIndex = str.search(/[：:]/);
                                    
                                    // 如果没有冒号，直接返回原文本
                                    if (firstColonIndex === -1) {
                                        return str;
                                    }
                                    
                                    // 分割字符串：第一个冒号前的文字、第一个冒号、剩余部分
                                    const beforeColon = str.substring(0, firstColonIndex);
                                    const colon = str[firstColonIndex];
                                    const afterColon = str.substring(firstColonIndex + 1);
                                    
                                    return (
                                        <>
                                            <span className="font-bold text-green-600">{beforeColon}</span>
                                            <span className="font-bold text-green-600">{colon}</span>
                                            {afterColon}
                                        </>
                                    );
                                };
                                
                                // Custom compact list render for steps
                                const items = typeof text === 'string' ? text.split(/(?:^|[\s。；;])(?=\d+[.、．]\s*)/).filter(p => p.trim()) : [];
                                
                                if (items.length > 1) {
                                    return (
                                        <div className="flex flex-col gap-2 w-full">
                                            {items.map((part, idx) => {
                                                const match = part.trim().match(/^(\d+[.、．]\s*)(.*)/s);
                                                if (match) {
                                                    return (
                                                        <div key={idx} className="flex gap-2 items-start">
                                                            <span className="font-mono text-indigo-600 font-bold shrink-0 select-none text-[10px] bg-indigo-50 px-1.5 py-0.5 rounded min-w-[20px] text-center border border-indigo-100">
                                                                {match[1].trim().replace(/[.、．]/,'')}
                                                            </span>
                                                            <span className="leading-relaxed text-slate-700 text-xs flex-1">
                                                                {highlightStepTitles(match[2])}
                                                            </span>
                                                        </div>
                                                    );
                                                }
                                                return <div key={idx} className="leading-relaxed text-slate-700 text-xs">{highlightStepTitles(part)}</div>;
                                            })}
                                        </div>
                                    );
                                }
                                return <div className="text-xs text-slate-700 whitespace-pre-wrap leading-relaxed">{highlightStepTitles(text)}</div>;
                            }
                        },
                        { 
                            title: <div className="text-center font-bold text-slate-700">Payload 示例</div>, 
                            dataIndex: 'payload', 
                            width: 280,
                            align: 'center',
                            onCell: () => ({ 
                                style: { 
                                    verticalAlign: 'top', 
                                    padding: '12px 8px',
                                    textAlign: 'center'
                                } 
                            }),
                            render: t => {
                                const content = cleanJsonString(t);
                                return (
                                    <div className="flex justify-center">
                                        <div className="relative group inline-block w-full">
                                            <div className="bg-slate-50 rounded-md border border-slate-200 p-2 font-mono text-xs text-slate-600 max-h-[280px] overflow-y-auto custom-scrollbar leading-relaxed break-all pr-7 whitespace-pre-wrap shadow-inner text-left">
                                                {content}
                                            </div>
                                            <div className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                                <Button 
                                                    type="text" 
                                                    size="small" 
                                                    icon={<CopyOutlined />} 
                                                    className="text-slate-400 hover:text-blue-600 bg-white/90 backdrop-blur-sm shadow-md border border-slate-200 h-6 w-6 flex items-center justify-center rounded hover:shadow-lg transition-all"
                                                    onClick={() => {
                                                        navigator.clipboard.writeText(content);
                                                        message.success('Payload 已复制');
                                                    }}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                );
                            }
                        },
                        { 
                            title: <div className="font-bold text-slate-700">验证点</div>, 
                            dataIndex: 'validation',
                            width: 260,
                            onCell: () => ({ 
                                style: { 
                                    verticalAlign: 'top', 
                                    padding: '12px 8px',
                                    lineHeight: '1.5'
                                } 
                            }),
                            render: (text) => {
                                if (!text) return <span className="text-slate-400">-</span>;
                                
                                // 高亮数值的函数
                                const highlightNumbers = (str) => {
                                    // 匹配数字（包括小数点、逗号、等号）
                                    const parts = str.split(/(\d+(?:[.,]\d+)*|[=＝])/);
                                    return parts.map((part, i) => {
                                        // 如果是数字
                                        if (/^\d+(?:[.,]\d+)*$/.test(part)) {
                                            return (
                                                <span key={i} className="font-mono font-bold text-blue-600">
                                                    {part}
                                                </span>
                                            );
                                        }
                                        // 如果是等号
                                        if (/^[=＝]$/.test(part)) {
                                            return <span key={i} className="text-slate-500 font-bold">{part}</span>;
                                        }
                                        return part;
                                    });
                                };
                                
                                // 如果是字符串，尝试按顿号、分号等分隔符拆分
                                if (typeof text === 'string') {
                                    // 首先检查是否包含明确的列表标记（如 "1. "、"2. " 等）
                                    const hasNumberedList = /\d+[.、．]\s+/.test(text);
                                    
                                    // 如果有明确的数字列表标记，按数字标记分割
                                    if (hasNumberedList) {
                                        // 按照 "数字. " 或 "数字、" 或 "数字． " 的模式分割
                                        const items = text.split(/(?=\d+[.、．]\s+)/).map(item => item.trim()).filter(item => item && /^\d+[.、．]\s+/.test(item));
                                        
                                        if (items.length > 1) {
                                            return (
                                                <div className="flex flex-col gap-2 w-full">
                                                    {items.map((item, idx) => {
                                                        // 移除开头的数字标记
                                                        const cleanItem = item.replace(/^\d+[.、．]\s+/, '');
                                                        return (
                                                            <div key={idx} className="flex gap-2 items-start">
                                                                <span className="font-mono text-green-600 font-bold shrink-0 select-none text-[10px] bg-green-50 px-1.5 py-0.5 rounded min-w-[20px] text-center border border-green-100">
                                                                    {idx + 1}
                                                                </span>
                                                                <span className="leading-relaxed text-slate-700 text-xs flex-1" style={{ wordBreak: 'break-all', overflowWrap: 'anywhere' }}>
                                                                    {highlightNumbers(cleanItem)}
                                                                </span>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            );
                                        }
                                    } else {
                                        // 如果没有数字列表标记，按顿号、分号、句号等分隔
                                        // 要求分隔符后面有空格或者是结尾
                                        const items = text.split(/[、；;。](?=\s|$)/).map(item => item.trim()).filter(item => item);
                                        
                                        // 如果拆分后有多个项，显示为列表
                                        if (items.length > 1) {
                                            return (
                                                <div className="flex flex-col gap-2 w-full">
                                                    {items.map((item, idx) => (
                                                        <div key={idx} className="flex gap-2 items-start">
                                                            <span className="font-mono text-green-600 font-bold shrink-0 select-none text-[10px] bg-green-50 px-1.5 py-0.5 rounded min-w-[20px] text-center border border-green-100">
                                                                {idx + 1}
                                                            </span>
                                                            <span className="leading-relaxed text-slate-700 text-xs flex-1" style={{ wordBreak: 'break-all', overflowWrap: 'anywhere' }}>
                                                                {highlightNumbers(item)}
                                                            </span>
                                                        </div>
                                                    ))}
                                                </div>
                                            );
                                        }
                                    }
                                    
                                    // 单行文本也高亮数值，允许换行
                                    return (
                                        <div className="text-xs text-slate-700 leading-relaxed" style={{ wordBreak: 'break-all', overflowWrap: 'anywhere' }}>
                                            {highlightNumbers(text)}
                                        </div>
                                    );
                                }
                                
                                // 否则使用默认渲染，允许换行
                                return (
                                    <div className="text-xs text-slate-700 leading-relaxed" style={{ wordBreak: 'break-all', overflowWrap: 'anywhere' }}>
                                        {renderField(text)}
                                    </div>
                                );
                            }
                        }
                     ]}
                  />
              </div>
          </div>
      </div>
      <FlowchartModal 
        visible={flowchartVisible} 
        onClose={() => setFlowchartVisible(false)} 
        data={currentFlowData}
        sourceFile={report.file_name}
        providerService={(() => {
            if (!report.diff_content) return null;
            const match = report.diff_content.match(/diff --git a\/([^/]+)\//);
            return match ? match[1] : null;
        })()}
      />
    </div>
  );
};

export default ReportDetail;

