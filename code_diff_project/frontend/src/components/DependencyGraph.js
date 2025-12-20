import React, { useState, useRef } from 'react';
import { DeploymentUnitOutlined, FileTextOutlined, CloudServerOutlined, FullscreenOutlined, DragOutlined } from '@ant-design/icons';
import { Modal } from 'antd';

// Fullscreen Graph View Component with Drag Support
const FullscreenGraphView = ({ renderGraphContent, fileName, count, handleMouseDown, handleMouseMove, handleMouseUp, dragState }) => {
  const containerRef = useRef(null);
  
  return (
    <div className="relative w-full h-full">
      {/* Scrollable Container */}
      <div 
        ref={containerRef}
        onMouseDown={(e) => handleMouseDown(e, containerRef)}
        onMouseMove={(e) => handleMouseMove(e, containerRef)}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ 
          width: '100%',
          height: '100%',
          overflow: 'auto',
          cursor: dragState.isDragging ? 'grabbing' : 'grab',
          userSelect: dragState.isDragging ? 'none' : 'auto',
          padding: '20px'
        }}
      >
        <div style={{ display: 'inline-block', minWidth: '100%' }}>
          {renderGraphContent(true)}
        </div>
      </div>
      
      {/* Info Panel */}
      <div className="absolute top-6 left-6 bg-white/95 backdrop-blur-sm p-4 rounded-lg border border-slate-200 shadow-lg max-w-xs z-50 pointer-events-none">
        <h4 className="text-sm font-bold text-slate-700 mb-2 flex items-center gap-2">
          <FileTextOutlined className="text-indigo-600" />
          变更文件信息
        </h4>
        <div className="text-xs text-slate-600 space-y-1">
          <div><span className="font-medium">文件名:</span> {fileName || 'Unknown'}</div>
          <div><span className="font-medium">影响节点:</span> {count} 个</div>
          <div className="pt-2 mt-2 border-t border-slate-200 flex items-center gap-2 text-slate-500">
            <DragOutlined />
            <span>按住鼠标拖动或使用滚动条查看</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const DependencyGraph = ({ data, fileName }) => {
  const [fullscreenVisible, setFullscreenVisible] = useState(false);
  
  console.log('DependencyGraph render, fullscreenVisible:', fullscreenVisible);
  
  const dependencies = data.downstream_dependency || [];
  
  // Child Nodes (Callers)
  const uniqueDeps = [];
  const seen = new Set();
  dependencies.forEach(dep => {
      // Handle both object and string formats if any
      if (typeof dep === 'string') return;
      const key = `${dep.service_name}-${dep.caller_class || dep.file_path}`;
      if (!seen.has(key)) {
          seen.add(key);
          uniqueDeps.push(dep);
      }
  });

  // Graph dimensions
  const count = uniqueDeps.length;
  const nodeSpacing = 220; // Horizontal space between nodes
  const minWidth = 800;
  
  // Dynamic width to accommodate all nodes horizontally
  const width = Math.max(minWidth, count * nodeSpacing + 100);
  const centerX = width / 2;
  
  // Fixed vertical positions for Tree Layout
  // If no dependencies, center the root node vertically
  const rootY = count > 0 ? 80 : 160; 
  const childY = 280;
  // Reduce height significantly if no downstream impact
  const height = count > 0 ? Math.max(400, childY + 150) : 120;

  // Root Node (The Changed File)
  const rootNode = {
    id: 'root',
    label: fileName ? fileName.split('/').pop() : 'Changed File',
    subLabel: '变更源头',
    // New fields for enhanced display
    fileName: fileName ? fileName.split('/').pop() : 'Unknown',
    fileType: 'Java Class', // Simplified assumption or derive
    x: centerX,
    y: rootY,
    type: 'root'
  };

  // Child Nodes (Callers)
  const nodes = count > 0 ? [rootNode] : []; // Do not show root node if no dependencies
  const links = [];

  if (uniqueDeps.length > 0) {
      // Tree Layout: Spread children horizontally below root
      uniqueDeps.forEach((dep, idx) => {
          // Calculate horizontal position centered around centerX
          // Formula: center + (index - (total-1)/2) * spacing
          const offset = (idx - (count - 1) / 2) * nodeSpacing;
          const x = centerX + offset;
          const y = childY;
          
          nodes.push({
              id: `dep-${idx}`,
              label: dep.service_name || 'Unknown Service',
              subLabel: dep.caller_class ? dep.caller_class.split('.').pop() : (dep.file_path ? dep.file_path.split('/').pop() : 'Unknown'),
              x,
              y,
              type: 'child',
              details: dep // Store full details
          });

          links.push({
              source: rootNode,
              target: { x, y }
          });
      });
  } else {
      // No dependencies - we will render a placeholder message instead of the graph
  }

  // Drag state for fullscreen mode
  const [dragState, setDragState] = useState({ isDragging: false, startX: 0, startY: 0, scrollLeft: 0, scrollTop: 0 });

  // Handle mouse down for drag
  const handleMouseDown = (e, containerRef) => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    setDragState({
      isDragging: true,
      startX: e.clientX,
      startY: e.clientY,
      scrollLeft: container.scrollLeft,
      scrollTop: container.scrollTop
    });
  };

  // Handle mouse move for drag
  const handleMouseMove = (e, containerRef) => {
    if (!dragState.isDragging || !containerRef.current) return;
    e.preventDefault();
    const container = containerRef.current;
    const dx = e.clientX - dragState.startX;
    const dy = e.clientY - dragState.startY;
    container.scrollLeft = dragState.scrollLeft - dx;
    container.scrollTop = dragState.scrollTop - dy;
  };

  // Handle mouse up for drag
  const handleMouseUp = () => {
    setDragState(prev => ({ ...prev, isDragging: false }));
  };

  // Render graph content (reusable for both normal and fullscreen)
  const renderGraphContent = (isFullscreen = false) => {
    // Fullscreen: compact and comfortable layout
    const fullscreenNodeSpacing = 200; // Tighter spacing in fullscreen
    const fullscreenWidth = Math.max(1800, count * fullscreenNodeSpacing + 300);
    const fullscreenHeight = count > 0 ? 450 : 200;
    const fullscreenRootY = 100;
    const fullscreenChildY = 320;
    
    if (isFullscreen) {
      console.log('Fullscreen dimensions:', { width: fullscreenWidth, height: fullscreenHeight, count });
    }
    
    const displayWidth = isFullscreen ? fullscreenWidth : width;
    const displayHeight = isFullscreen ? fullscreenHeight : height;
    const displayRootY = isFullscreen ? fullscreenRootY : rootY;
    const displayChildY = isFullscreen ? fullscreenChildY : childY;
    const displayCenterX = displayWidth / 2;
    
    // Recalculate node positions for fullscreen
    const displayNodes = [];
    const displayLinks = [];
    
    if (count > 0) {
      const displayRootNode = {
        ...rootNode,
        x: displayCenterX,
        y: displayRootY
      };
      displayNodes.push(displayRootNode);
      
      uniqueDeps.forEach((dep, idx) => {
        const spacing = isFullscreen ? fullscreenNodeSpacing : nodeSpacing;
        const offset = (idx - (count - 1) / 2) * spacing;
        const x = displayCenterX + offset;
        const y = displayChildY;
        
        displayNodes.push({
          id: `dep-${idx}`,
          label: dep.service_name || 'Unknown Service',
          subLabel: dep.caller_class ? dep.caller_class.split('.').pop() : (dep.file_path ? dep.file_path.split('/').pop() : 'Unknown'),
          x,
          y,
          type: 'child',
          details: dep
        });
        
        displayLinks.push({
          source: displayRootNode,
          target: { x, y }
        });
      });
    }
    
    return (
      <>
        {count === 0 ? (
            <div className="flex flex-col items-center justify-center h-[120px] text-slate-400 text-sm">
                <DeploymentUnitOutlined className="text-2xl mb-2 opacity-30" />
                <span>暂无直接影响链路</span>
            </div>
        ) : (
            <>
                <div className={`${isFullscreen ? 'w-full h-full' : 'flex justify-center'} overflow-auto custom-scrollbar relative`}>
                    {/* Background decorative elements */}
                    <div className="absolute inset-0 z-0 opacity-[0.03]" 
                         style={{backgroundImage: 'radial-gradient(#4f46e5 1px, transparent 1px)', backgroundSize: '20px 20px'}}>
                    </div>

                    <svg 
                        width={displayWidth} 
                        height={displayHeight} 
                        viewBox={isFullscreen ? undefined : `0 0 ${displayWidth} ${displayHeight}`}
                        className={`select-none z-10 ${isFullscreen ? '' : 'max-w-full'}`}
                        style={isFullscreen ? { minWidth: displayWidth, minHeight: displayHeight } : {}}
                    >
                        <defs>
                            <linearGradient id="grad-root" x1="0%" y1="0%" x2="100%" y2="100%">
                                <stop offset="0%" stopColor="#fca5a5" />
                                <stop offset="100%" stopColor="#ef4444" />
                            </linearGradient>
                            <linearGradient id="grad-child" x1="0%" y1="0%" x2="100%" y2="100%">
                                <stop offset="0%" stopColor="#fdba74" />
                                <stop offset="100%" stopColor="#f97316" />
                            </linearGradient>
                            <filter id="shadow-lg" x="-50%" y="-50%" width="200%" height="200%">
                                <feDropShadow dx="0" dy="4" stdDeviation="6" floodColor="#000" floodOpacity="0.15"/>
                            </filter>
                            <filter id="glow-root" x="-50%" y="-50%" width="200%" height="200%">
                                <feGaussianBlur stdDeviation="8" result="blur"/>
                                <feComposite in="blur" in2="SourceGraphic" operator="over"/>
                            </filter>
                             <marker id="arrowhead-fancy" markerWidth="12" markerHeight="12" refX="24" refY="6" orient="auto">
                                <path d="M0,0 L12,6 L0,12 L3,6 Z" fill="#cbd5e1"/>
                            </marker>
                        </defs>

                        {/* Links */}
                        {displayLinks.map((link, i) => (
                            <g key={i}>
                                <line 
                                    x1={link.source.x} y1={link.source.y} 
                                    x2={link.target.x} y2={link.target.y} 
                                    stroke="#cbd5e1" 
                                    strokeWidth={isFullscreen ? "3" : "2"}
                                    strokeDasharray={isFullscreen ? "8 6" : "6 4"}
                                    markerEnd="url(#arrowhead-fancy)"
                                    className="opacity-60"
                                />
                            </g>
                        ))}

                        {/* Nodes */}
                        {displayNodes.map((node, i) => {
                            const isRoot = node.type === 'root';
                            // Fullscreen: slightly larger nodes and icons for better visibility
                            const iconSize = isFullscreen ? (isRoot ? 18 : 16) : (isRoot ? 16 : 14);
                            const nodeRadius = isFullscreen ? (isRoot ? 28 : 24) : (isRoot ? 24 : 20);
                            
                            return (
                                <g key={node.id} transform={`translate(${node.x},${node.y})`} 
                                   className="cursor-pointer"
                                   style={{transformOrigin: `${node.x}px ${node.y}px`}}
                                >
                                    <title>{isRoot ? '本次代码变更的源文件' : `调用方: ${node.details?.caller_class || 'Unknown'}`}</title>
                                    
                                    {isRoot && (
                                        <circle r={nodeRadius + 6} fill="#fee2e2" opacity="0.6" />
                                    )}

                                    <circle 
                                        r={nodeRadius} 
                                        fill={`url(#${isRoot ? 'grad-root' : 'grad-child'})`} 
                                        filter="url(#shadow-lg)"
                                        stroke="white"
                                        strokeWidth="2"
                                    />

                                    <foreignObject 
                                        x={-iconSize/2} y={-iconSize/2} 
                                        width={iconSize} height={iconSize}
                                        className="pointer-events-none"
                                    >
                                        <div className="flex items-center justify-center w-full h-full text-white">
                                            {isRoot ? <FileTextOutlined style={{fontSize: iconSize}}/> : <CloudServerOutlined style={{fontSize: iconSize}}/>}
                                        </div>
                                    </foreignObject>

                                    <foreignObject 
                                        x={isFullscreen ? "-90" : "-80"}
                                        y={isRoot ? -(nodeRadius + (isFullscreen ? 50 : 45)) : nodeRadius + (isFullscreen ? 10 : 8)} 
                                        width={isFullscreen ? "180" : "160"}
                                        height={isFullscreen ? "90" : "80"}
                                        style={{overflow: 'visible'}}
                                    >
                                        <div className={`flex flex-col items-center text-center leading-tight ${isRoot ? 'justify-end' : 'justify-start'}`}>
                                            {isRoot ? (
                                                <>
                                                    <div className={`${isFullscreen ? 'text-sm' : 'text-[10px]'} font-bold text-slate-700 bg-white/90 px-2 py-1 rounded-md border border-slate-200 shadow-md mb-1 truncate max-w-full`}>
                                                        {node.fileName}
                                                    </div>
                                                    <div className={`${isFullscreen ? 'text-xs' : 'text-[9px]'} text-red-500 font-medium bg-red-50 px-2 py-0.5 rounded-full border border-red-200`}>
                                                        变更源头
                                                    </div>
                                                </>
                                            ) : (
                                                <>
                                                    <div className={`${isFullscreen ? 'text-[11px]' : 'text-[9px]'} text-slate-500 font-medium mb-1 truncate max-w-full px-1`}>
                                                        {node.label}
                                                    </div>
                                                    <div className={`${isFullscreen ? 'text-sm' : 'text-[10px]'} font-bold text-slate-700 bg-white/90 px-2 py-0.5 rounded-md border border-slate-200 shadow-md mb-1 truncate max-w-full`}>
                                                        {node.subLabel}
                                                    </div>
                                                    {node.details?.line_number && (
                                                        <div className={`${isFullscreen ? 'text-xs' : 'text-[9px]'} text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200`}>
                                                            Line: {node.details.line_number}
                                                        </div>
                                                    )}
                                                </>
                                            )}
                                        </div>
                                    </foreignObject>
                                </g>
                            );
                        })}
                    </svg>
                </div>
                
                {/* Legend */}
                <div className={`${isFullscreen ? 'absolute bottom-6 right-6' : 'absolute bottom-3 right-4'} flex gap-4 text-[10px] bg-white/90 p-2 rounded-lg border border-slate-100 shadow-sm backdrop-blur-sm`}>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-gradient-to-br from-red-300 to-red-500 shadow-sm flex items-center justify-center">
                            <div className="w-1 h-1 bg-white rounded-full"></div>
                        </div>
                        <span className="text-slate-600 font-medium">变更点 (Source)</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-gradient-to-br from-orange-300 to-orange-500 shadow-sm flex items-center justify-center">
                            <div className="w-1 h-1 bg-white rounded-full"></div>
                        </div>
                        <span className="text-slate-600 font-medium">影响范围 (Impact)</span>
                    </div>
                </div>
            </>
        )}
      </>
    );
  };

  return (
    <>
    <div className="bg-gradient-to-br from-slate-50 to-white rounded-xl shadow-sm border border-slate-200 p-4 mb-4 overflow-hidden relative group">
        <div className="absolute top-3 left-4 flex items-center gap-2 text-indigo-900 text-xs font-bold uppercase tracking-wider z-10 bg-white/50 backdrop-blur-sm px-2 py-1 rounded-full border border-indigo-100/50">
            <DeploymentUnitOutlined className="text-indigo-600"/> 影响链路关系图
        </div>
        
        {/* Fullscreen Button */}
        {count > 0 && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              console.log('Fullscreen button clicked');
              setFullscreenVisible(true);
            }}
            className="absolute top-3 right-4 z-50 bg-white hover:bg-indigo-50 px-3 py-1.5 rounded-lg border border-slate-300 hover:border-indigo-400 transition-all duration-200 flex items-center gap-2 text-slate-700 hover:text-indigo-600 text-xs font-medium shadow-md hover:shadow-lg cursor-pointer"
            title="全屏查看"
            type="button"
          >
            <FullscreenOutlined className="text-sm" />
            <span>全屏查看</span>
          </button>
        )}
        
        {renderGraphContent(false)}
    </div>

    {/* Fullscreen Modal */}
    <Modal
      title={
        <div className="flex items-center gap-3">
          <DeploymentUnitOutlined className="text-indigo-600 text-lg" />
          <span className="text-lg font-bold">影响链路关系图 - 全屏视图</span>
          <span className="text-sm text-slate-500 font-normal">({count} 个影响节点)</span>
        </div>
      }
      open={fullscreenVisible}
      onCancel={() => setFullscreenVisible(false)}
      footer={null}
      width="90vw"
      style={{ top: 20, maxWidth: '1600px' }}
      styles={{ 
        body: {
          height: '80vh', 
          overflow: 'hidden',
          padding: 0,
          background: 'linear-gradient(to bottom right, #f8fafc, #ffffff)'
        }
      }}
      destroyOnClose
    >
      <FullscreenGraphView 
        renderGraphContent={renderGraphContent}
        fileName={fileName}
        count={count}
        handleMouseDown={handleMouseDown}
        handleMouseMove={handleMouseMove}
        handleMouseUp={handleMouseUp}
        dragState={dragState}
      />
    </Modal>
    </>
  );
};

export default DependencyGraph;

