import React, { useState, useMemo, useRef, useEffect } from 'react';

// --- Types matching the Python visualize_ast.py output ---

type ASTNodeType = 'function' | 'leaf' | 'string' | 'unknown';

interface ASTNodeData {
  name: string;
  type: ASTNodeType;
  children: ASTNodeData[];
}

interface ASTViewerProps {
  data: ASTNodeData;
  height?: number; // Optional fixed height for the container
}

// --- Layout Logic ---

interface Point { x: number; y: number }
interface TreeLayoutNode {
  data: ASTNodeData;
  x: number;
  y: number;
  width: number;
  children: TreeLayoutNode[];
  collapsed: boolean;
}

const NODE_WIDTH = 120;
const NODE_HEIGHT = 40;
const VERTICAL_SPACING = 70;
const HORIZONTAL_SPACING = 20;

/**
 * Recursively calculates tree layout coordinates.
 * Returns the full width of the subtree.
 */
const calculateLayout = (
  node: ASTNodeData, 
  depth: number = 0, 
  collapsedIds: Set<string>, 
  pathId: string = "root"
): TreeLayoutNode => {
  const isCollapsed = collapsedIds.has(pathId);
  
  // Base case: Leaf or Collapsed
  if (!node.children || node.children.length === 0 || isCollapsed) {
    return {
      data: node,
      x: 0, 
      y: depth * VERTICAL_SPACING,
      width: NODE_WIDTH,
      children: [],
      collapsed: isCollapsed
    };
  }

  // Recursive case
  let currentX = 0;
  const layoutChildren: TreeLayoutNode[] = [];

  node.children.forEach((child, index) => {
    const childPath = `${pathId}-${index}`;
    const childLayout = calculateLayout(child, depth + 1, collapsedIds, childPath);
    
    // Shift child to the right based on previous siblings
    childLayout.x = currentX;
    layoutChildren.push(childLayout);
    
    currentX += childLayout.width + HORIZONTAL_SPACING;
  });

  // Total width of this node's subtree
  const totalWidth = currentX - HORIZONTAL_SPACING;

  // Center parent above children
  // If children are narrower than parent, we still need enough space for parent
  const finalWidth = Math.max(NODE_WIDTH, totalWidth);
  
  // Adjust children positions to be centered under the new final width if parent is wider
  const offset = (finalWidth - totalWidth) / 2;
  if (offset > 0) {
    layoutChildren.forEach(child => child.x += offset);
  }

  return {
    data: node,
    x: finalWidth / 2 - NODE_WIDTH / 2, // Center of the block
    y: depth * VERTICAL_SPACING,
    width: finalWidth,
    children: layoutChildren,
    collapsed: false
  };
};

/**
 * Flattens the recursive layout into a list of renderable nodes and links
 */
const flattenTree = (
  node: TreeLayoutNode, 
  offsetX: number = 0, 
  nodes: any[] = [], 
  links: any[] = [],
  pathId: string = "root"
) => {
  const absoluteX = offsetX + node.x;
  const absoluteY = node.y;

  nodes.push({
    id: pathId,
    x: absoluteX,
    y: absoluteY,
    data: node.data,
    collapsed: node.collapsed,
    hasChildren: node.data.children && node.data.children.length > 0
  });

  if (!node.collapsed) {
    node.children.forEach((child, index) => {
      const childPath = `${pathId}-${index}`;
      
      // Calculate connection points
      const parentBottom = { x: absoluteX + NODE_WIDTH / 2, y: absoluteY + NODE_HEIGHT };
      const childTop = { x: offsetX + child.x + NODE_WIDTH / 2, y: child.y };

      links.push({
        source: parentBottom,
        target: childTop,
        key: `${pathId}->${childPath}`
      });

      flattenTree(child, offsetX + child.x, nodes, links, childPath);
    });
  }

  return { nodes, links };
};

// --- Component ---

export default function ASTViewer({ data, height = 500 }: ASTViewerProps) {
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
  const [transform, setTransform] = useState({ x: 0, y: 50, scale: 1 });
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);
  const lastPos = useRef({ x: 0, y: 0 });

  // 1. Calculate Layout
  const { nodes, links } = useMemo(() => {
    const rootLayout = calculateLayout(data, 0, collapsedIds);
    return flattenTree(rootLayout, 0);
  }, [data, collapsedIds]);

  // 2. Center the tree initially
  useEffect(() => {
    if (containerRef.current && nodes.length > 0) {
       const rootNode = nodes[0];
       // Rough centering
       const containerWidth = containerRef.current.clientWidth;
       setTransform(prev => ({
         ...prev,
         x: (containerWidth / 2) - (rootNode.x + NODE_WIDTH / 2)
       }));
    }
  }, [data]);

  // --- Handlers ---

  const toggleCollapse = (id: string) => {
    const newSet = new Set(collapsedIds);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setCollapsedIds(newSet);
  };

  const handleWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const scaleAmt = -e.deltaY * 0.001;
      setTransform(prev => ({
        ...prev,
        scale: Math.max(0.1, Math.min(3, prev.scale + scaleAmt))
      }));
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    isDragging.current = true;
    lastPos.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging.current) return;
    const dx = e.clientX - lastPos.current.x;
    const dy = e.clientY - lastPos.current.y;
    lastPos.current = { x: e.clientX, y: e.clientY };
    setTransform(prev => ({ ...prev, x: prev.x + dx, y: prev.y + dy }));
  };

  const handleMouseUp = () => {
    isDragging.current = false;
  };

  // --- Render Helpers ---

  const getNodeColor = (type: ASTNodeType) => {
    switch (type) {
      case 'function': return 'bg-blue-100 border-blue-400 text-blue-800';
      case 'leaf': return 'bg-green-100 border-green-400 text-green-800'; // String literals
      case 'string': return 'bg-yellow-100 border-yellow-400 text-yellow-800';
      default: return 'bg-gray-100 border-gray-400 text-gray-800';
    }
  };

  return (
    <div 
      className="border rounded-lg bg-slate-50 relative overflow-hidden select-none cursor-move"
      style={{ height }}
      ref={containerRef}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <div className="absolute top-2 right-2 bg-white/80 p-2 rounded shadow text-xs text-gray-500 z-10 pointer-events-none">
        Scroll to Zoom • Drag to Pan • Click Nodes to Collapse
      </div>

      <div 
        style={{ 
          transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
          transformOrigin: '0 0',
          transition: isDragging.current ? 'none' : 'transform 0.1s ease-out'
        }}
        className="w-full h-full"
      >
        <svg className="overflow-visible w-1 h-1"> {/* 1x1 base, content flows out */}
          <defs>
             <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="0" refY="3.5" orient="auto">
               <polygon points="0 0, 10 3.5, 0 7" fill="#cbd5e1" />
             </marker>
          </defs>

          {/* Links */}
          {links.map(link => (
            <path
              key={link.key}
              d={`M${link.source.x},${link.source.y} 
                  C${link.source.x},${link.source.y + 20} 
                   ${link.target.x},${link.target.y - 20} 
                   ${link.target.x},${link.target.y}`}
              fill="none"
              stroke="#cbd5e1"
              strokeWidth="2"
            />
          ))}

          {/* Nodes (rendered as ForeignObjects for HTML content) */}
          {nodes.map(node => (
            <foreignObject
              key={node.id}
              x={node.x}
              y={node.y}
              width={NODE_WIDTH}
              height={NODE_HEIGHT}
              className="overflow-visible"
            >
              <div 
                onClick={(e) => { e.stopPropagation(); toggleCollapse(node.id); }}
                className={`
                  w-[120px] h-[40px] 
                  flex items-center justify-center 
                  border-2 rounded-md shadow-sm text-sm font-mono font-bold
                  transition-all hover:scale-105 cursor-pointer
                  ${getNodeColor(node.data.type || 'function')}
                `}
                title={node.data.name}
              >
                <div className="truncate px-1">
                  {node.data.name}
                </div>
                {node.hasChildren && node.collapsed && (
                   <div className="absolute -bottom-2 -right-2 bg-gray-600 text-white rounded-full w-4 h-4 flex items-center justify-center text-[10px]">
                     +
                   </div>
                )}
              </div>
            </foreignObject>
          ))}
        </svg>
      </div>
    </div>
  );
}