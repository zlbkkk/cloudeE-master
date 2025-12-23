import React, { useState } from 'react';
import { DownOutlined, UpOutlined, CodeOutlined } from '@ant-design/icons';

/**
 * 可折叠的代码片段组件
 * 默认只显示目标行，点击可展开显示上下文
 */
const CollapsibleCodeSnippet = ({ snippetData, fileName, lineNumber }) => {
    const [expandedItems, setExpandedItems] = useState({});
    const [debugMode, setDebugMode] = useState(false);

    // 调试日志
    console.log('CollapsibleCodeSnippet - snippetData:', snippetData);
    console.log('CollapsibleCodeSnippet - type:', typeof snippetData);
    console.log('CollapsibleCodeSnippet - isArray:', Array.isArray(snippetData));

    // 切换展开/收起状态
    const toggleExpand = (index) => {
        setExpandedItems(prev => ({
            ...prev,
            [index]: !prev[index]
        }));
    };
    
    // 如果没有数据，显示提示
    if (!snippetData) {
        return (
            <div className="w-full max-w-xl bg-red-900/20 rounded-lg border border-red-700 shadow-md overflow-hidden z-10 mt-2 p-4">
                <div className="text-red-400 text-sm">⚠️ 没有代码片段数据</div>
            </div>
        );
    }

    // 如果是旧格式（纯文本），直接显示
    if (typeof snippetData === 'string') {
        return (
            <div className="w-full max-w-xl bg-slate-900 rounded-lg border border-slate-700 shadow-md overflow-hidden z-10 mt-2">
                <div className="flex justify-between items-center px-3 py-1.5 bg-slate-800 border-b border-slate-700">
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                        <CodeOutlined />
                        <span className="font-mono">
                            {fileName || 'Snippet'}
                            {lineNumber && <span className="text-slate-500 ml-1">:{lineNumber}</span>}
                        </span>
                    </div>
                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                        旧格式 (纯文本)
                    </div>
                </div>
                <div className="p-3 font-mono text-[11px] leading-relaxed text-slate-300 overflow-x-auto">
                    <pre className="whitespace-pre-wrap break-all">{snippetData}</pre>
                </div>
                <div className="px-3 py-1.5 bg-yellow-900/20 border-t border-yellow-700/50 text-center">
                    <span className="text-[10px] text-yellow-500">
                        ⚠️ 使用旧格式数据，无法展开上下文
                    </span>
                </div>
            </div>
        );
    }

    // 新格式：结构化数据
    const snippets = Array.isArray(snippetData) ? snippetData : [snippetData];
    
    console.log('CollapsibleCodeSnippet - snippets:', snippets);
    console.log('CollapsibleCodeSnippet - snippets length:', snippets.length);

    return (
        <div className="w-full max-w-xl space-y-2 mt-2">
            {snippets.map((snippet, index) => {
                const isExpanded = expandedItems[index] || false;
                const hasContext = (snippet.context_before && snippet.context_before.length > 0) || 
                                  (snippet.context_after && snippet.context_after.length > 0);
                
                console.log(`Snippet ${index}:`, {
                    target_line: snippet.target_line,
                    hasContext,
                    context_before_length: snippet.context_before?.length || 0,
                    context_after_length: snippet.context_after?.length || 0
                });

                return (
                    <div key={index} className="bg-slate-900 rounded-lg border border-slate-700 shadow-md overflow-hidden">
                        {/* Header */}
                        <div className="flex justify-between items-center px-3 py-1.5 bg-slate-800 border-b border-slate-700">
                            <div className="flex items-center gap-2 text-xs text-slate-400">
                                <CodeOutlined />
                                <span className="font-mono">
                                    {fileName || 'Snippet'}
                                    <span className="text-slate-500 ml-1">:L{snippet.target_line}</span>
                                </span>
                            </div>
                            {hasContext && (
                                <button
                                    onClick={() => toggleExpand(index)}
                                    className="text-[10px] text-slate-400 hover:text-slate-200 font-medium uppercase tracking-wider flex items-center gap-1 transition-colors"
                                >
                                    {isExpanded ? (
                                        <>
                                            <UpOutlined className="text-[8px]" />
                                            收起上下文
                                        </>
                                    ) : (
                                        <>
                                            <DownOutlined className="text-[8px]" />
                                            展开上下文
                                        </>
                                    )}
                                </button>
                            )}
                        </div>

                        {/* Code Content */}
                        <div className="font-mono text-[11px] leading-relaxed">
                            {/* 上文（展开时显示） */}
                            {isExpanded && snippet.context_before && snippet.context_before.length > 0 && (
                                <div className="bg-slate-800/50 border-b border-slate-700/50">
                                    {snippet.context_before.map((ctx, i) => (
                                        <div key={i} className="px-3 py-1 text-slate-500 hover:bg-slate-800/70 transition-colors">
                                            <span className="text-slate-600 mr-3 select-none inline-block w-8 text-right">
                                                {ctx.line}
                                            </span>
                                            <span className="text-slate-400">{ctx.code || ' '}</span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* 目标行（始终显示，高亮） */}
                            <div className="bg-amber-500/10 border-l-2 border-amber-500">
                                <div className="px-3 py-1.5 text-slate-100">
                                    <span className="text-amber-500 mr-3 font-bold select-none inline-block w-8 text-right">
                                        {snippet.target_line}
                                    </span>
                                    <span className="text-slate-100 font-medium">{snippet.target_code}</span>
                                </div>
                            </div>

                            {/* 下文（展开时显示） */}
                            {isExpanded && snippet.context_after && snippet.context_after.length > 0 && (
                                <div className="bg-slate-800/50 border-t border-slate-700/50">
                                    {snippet.context_after.map((ctx, i) => (
                                        <div key={i} className="px-3 py-1 text-slate-500 hover:bg-slate-800/70 transition-colors">
                                            <span className="text-slate-600 mr-3 select-none inline-block w-8 text-right">
                                                {ctx.line}
                                            </span>
                                            <span className="text-slate-400">{ctx.code || ' '}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* 提示信息（未展开且有上下文时显示） */}
                        {!isExpanded && hasContext && (
                            <div className="px-3 py-1.5 bg-slate-800/30 border-t border-slate-700/50 text-center">
                                <span className="text-[10px] text-slate-500">
                                    点击上方按钮查看完整上下文
                                </span>
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
};

export default CollapsibleCodeSnippet;
