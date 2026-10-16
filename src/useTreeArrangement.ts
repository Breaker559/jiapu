import { useEffect, useRef, useState } from 'react';
import { applyNodeChanges } from '@xyflow/react';
import type { Node, NodeChange } from '@xyflow/react';
import { alignNodes, capturePositions, readArrangement, restorePositions, samePositions, snapNodes } from './treeArrangement';
import type { Alignment, Guide, Positions } from './treeArrangement';

export default function useTreeArrangement(initialNodes: Node[], scope: string, snap: boolean, zoom: number) {
 const key = `qinpu:tree-layout:v1:${scope}`;
 const [nodes, setNodes] = useState(() => restorePositions(initialNodes, readArrangement(key)));
 const current = useRef(nodes), previousKey = useRef(key);
 const past = useRef<Positions[]>([]), future = useRef<Positions[]>([]), dragStart = useRef<Positions | null>(null);
 const [history, setHistory] = useState({ undo: false, redo: false });
 const [guides, setGuides] = useState<Guide[]>([]);
 const [saved, setSaved] = useState(true);
 const update = (next: Node[]) => { current.current = next; setNodes(next); };
 const syncHistory = () => setHistory({ undo: !!past.current.length, redo: !!future.current.length });
 const save = (next: Node[]) => {
  try { localStorage.setItem(key, JSON.stringify({ version: 1, positions: capturePositions(next) })); setSaved(true); }
  catch { setSaved(false); }
 };
 useEffect(() => {
  const changedScope = previousKey.current !== key;
  const old = new Map(current.current.map(n => [n.id, n]));
  const changedPeople = initialNodes.length !== old.size || initialNodes.some(n => !old.has(n.id));
  // Data updates (including today's age) must not reset the user's arrangement or selection.
  const next = changedScope ? restorePositions(initialNodes, readArrangement(key)) : initialNodes.map(n => old.has(n.id) ? { ...old.get(n.id)!, ...n, position: old.get(n.id)!.position, selected: old.get(n.id)!.selected } : n);
  previousKey.current = key;
  if (changedScope || changedPeople) { past.current = []; future.current = []; dragStart.current = null; syncHistory(); setGuides([]); }
  update(next);
 }, [initialNodes, key]);

 const commit = (next: Node[], before = capturePositions(current.current)) => {
  if (!samePositions(before, capturePositions(next))) {
   past.current = [...past.current.slice(-29), before]; future.current = []; syncHistory();
   update(next); save(next);
  }
  setGuides([]);
 };
 const onNodesChange = (changes: NodeChange[]) => {
  let next = applyNodeChanges(changes, current.current);
  const moving = new Set(changes.filter(c => c.type === 'position' && c.position).map(c => 'id' in c ? c.id : ''));
  if (moving.size && dragStart.current && snap) {
   const result = snapNodes(next, moving, zoom); next = result.nodes; setGuides(result.guides);
  } else if (moving.size) setGuides([]);
  // Arrow-key moves have no drag gesture, but still belong in saved layout history.
  if (moving.size && !dragStart.current) commit(next);
  else update(next);
 };
 const beginDrag = () => { if (!dragStart.current) dragStart.current = capturePositions(current.current); };
 const endDrag = () => { if (dragStart.current) commit(current.current, dragStart.current); dragStart.current = null; setGuides([]); };
 const undo = () => {
  const positions = past.current.pop(); if (!positions) return;
  future.current.push(capturePositions(current.current)); const next = restorePositions(current.current, positions);
  update(next); save(next); syncHistory(); setGuides([]);
 };
 const redo = () => {
  const positions = future.current.pop(); if (!positions) return;
  past.current.push(capturePositions(current.current)); const next = restorePositions(current.current, positions);
  update(next); save(next); syncHistory(); setGuides([]);
 };
 return {
  nodes, guides, history, saved, onNodesChange, beginDrag, endDrag, undo, redo,
  align: (alignment: Alignment) => commit(alignNodes(current.current, alignment)),
  autoLayout: () => commit(restorePositions(current.current, capturePositions(initialNodes))),
  selectAll: () => update(current.current.map(n => ({ ...n, selected: true }))),
  clearSelection: () => update(current.current.map(n => ({ ...n, selected: false }))),
 };
}
