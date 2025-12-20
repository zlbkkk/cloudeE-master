export const getLanguage = (fileName) => {
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

export const parseDiff = (text) => {
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

