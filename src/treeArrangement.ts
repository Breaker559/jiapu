import type { Node, XYPosition } from '@xyflow/react';
import { CARD_HEIGHT, CARD_WIDTH } from './treeLayout';

export type Alignment = 'left' | 'centerX' | 'right' | 'top' | 'centerY' | 'bottom' | 'distributeX' | 'distributeY';
export type Guide = { axis: 'x' | 'y'; value: number; from: number; to: number };
export type Positions = Record<string, XYPosition>;
const width = (n: Node) => n.measured?.width ?? CARD_WIDTH;
const height = (n: Node) => n.measured?.height ?? CARD_HEIGHT;
export const capturePositions = (nodes: Node[]): Positions => Object.fromEntries(nodes.map(n => [n.id, { ...n.position }]));
export const samePositions = (a: Positions, b: Positions) => Object.keys(a).length === Object.keys(b).length && Object.entries(a).every(([id, p]) => b[id]?.x === p.x && b[id]?.y === p.y);
export const restorePositions = (nodes: Node[], positions: Positions) => nodes.map(n => positions[n.id] ? { ...n, position: { ...positions[n.id] } } : n);

export function alignNodes(nodes: Node[], alignment: Alignment): Node[] {
 const selected = nodes.filter(n => n.selected);
 const distribute = alignment === 'distributeX' || alignment === 'distributeY';
 if (selected.length < (distribute ? 3 : 2)) return nodes;
 const axis = ['left', 'centerX', 'right', 'distributeX'].includes(alignment) ? 'x' : 'y';
 const size = axis === 'x' ? width : height;
 const start = Math.min(...selected.map(n => n.position[axis]));
 const end = Math.max(...selected.map(n => n.position[axis] + size(n)));
 const positions: Positions = {};
 if (distribute) {
  // Keep outer cards in place when there is room; expand crowded selections to avoid overlaps.
  const ordered = [...selected].sort((a, b) => a.position[axis] - b.position[axis]);
  const gap = Math.max(24, (end - start - ordered.reduce((sum, n) => sum + size(n), 0)) / (ordered.length - 1));
  let next = start;
  for (const n of ordered) { positions[n.id] = { ...n.position, [axis]: next }; next += size(n) + gap; }
 } else {
  for (const n of selected) {
   const offset = alignment === 'left' || alignment === 'top' ? start : alignment === 'right' || alignment === 'bottom' ? end - size(n) : (start + end - size(n)) / 2;
   positions[n.id] = { ...n.position, [axis]: offset };
  }
 }
 return restorePositions(nodes, positions);
}

// A single correction is applied to the entire moving group, keeping its internal spacing intact.
// The tolerance is measured on screen so zooming out does not make snapping harder to use.
export function snapNodes(nodes: Node[], movingIds: Set<string>, zoom: number): { nodes: Node[]; guides: Guide[] } {
 const moving = nodes.filter(n => movingIds.has(n.id));
 const fixed = nodes.filter(n => !movingIds.has(n.id));
 if (!moving.length || !fixed.length) return { nodes, guides: [] };
 const tolerance = 8 / Math.max(zoom, 0.12);
 const delta = { x: 0, y: 0 }, guides: Guide[] = [];
 for (const axis of ['x', 'y'] as const) {
  const cross = axis === 'x' ? 'y' : 'x';
  const size = axis === 'x' ? width : height, crossSize = axis === 'x' ? height : width;
  let best: { delta: number; distance: number; crossDistance: number; guide: Guide } | undefined;
  for (const a of moving) for (const b of fixed) for (const fraction of [0.5, 0, 1]) {
   const value = b.position[axis] + size(b) * fraction;
   const correction = value - (a.position[axis] + size(a) * fraction);
   const distance = Math.abs(correction), crossDistance = Math.abs(a.position[cross] - b.position[cross]);
   if (distance > tolerance || (best && (distance > best.distance || (distance === best.distance && crossDistance >= best.crossDistance)))) continue;
   best = { delta: correction, distance, crossDistance, guide: { axis, value, from: Math.min(a.position[cross], b.position[cross]) - 18, to: Math.max(a.position[cross] + crossSize(a), b.position[cross] + crossSize(b)) + 18 } };
  }
  if (best) { delta[axis] = best.delta; guides.push(best.guide); }
 }
 return { nodes: nodes.map(n => movingIds.has(n.id) ? { ...n, position: { x: n.position.x + delta.x, y: n.position.y + delta.y } } : n), guides };
}

export function readArrangement(key: string): Positions {
 try {
  const saved = JSON.parse(localStorage.getItem(key) || 'null');
  if (saved?.version !== 1 || !saved.positions || typeof saved.positions !== 'object') return {};
  return Object.fromEntries(Object.entries(saved.positions).filter((entry): entry is [string, XYPosition] => {
   const p = entry[1] as XYPosition | null;
   return !!p && Number.isFinite(p.x) && Number.isFinite(p.y) && Math.abs(p.x) < 1e7 && Math.abs(p.y) < 1e7;
  }));
 } catch { return {}; }
}
