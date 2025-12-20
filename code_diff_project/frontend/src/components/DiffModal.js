import React, { useEffect, useState } from 'react';
import { Modal, Button } from 'antd';
import { CodeOutlined } from '@ant-design/icons';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { getLanguage, parseDiff } from '../utils/helpers';

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

export default DiffModal;

