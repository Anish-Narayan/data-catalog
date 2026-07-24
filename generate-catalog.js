const fs = require('fs');
const path = require('path');

function buildTree(dirPath, relativeTo = dirPath) {
    const items = fs.readdirSync(dirPath);
    const result = [];

    items.forEach(item => {
        if (item.startsWith('.') || item === 'node_modules' || item === 'generate-catalog.js') return;
        
        const fullPath = path.join(dirPath, item);
        const relPath = path.relative(relativeTo, fullPath).replace(/\\/g, '/');
        const stat = fs.statSync(fullPath);

        if (stat.isDirectory()) {
            const children = buildTree(fullPath, relativeTo);
            if (children.length > 0) {
                result.push({
                    name: item.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                    type: 'directory',
                    children: children
                });
            }
        } else if (item.endsWith('.md')) {
            result.push({
                name: path.basename(item, '.md').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                path: relPath,
                type: 'file'
            });
        }
    });
    return result;
}

const tree = buildTree(__dirname);
fs.writeFileSync('catalog-structure.json', JSON.stringify(tree, null, 2));
console.log('catalog-structure.json has been generated.');