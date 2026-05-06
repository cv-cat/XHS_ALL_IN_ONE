import {
  BookOutlined,
  CheckSquareOutlined,
  CopyOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  FileAddOutlined,
  FileTextOutlined,
  HeartOutlined,
  LinkOutlined,
  MessageOutlined,
  PictureOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  ShareAltOutlined,
  StarOutlined,
  TagsOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Image,
  Input,
  Modal,
  Popconfirm,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  batchCreateDraftsFromNotes,
  batchTagNotes,
  createDraftFromNote,
  createTag,
  deleteSavedNote,
  downloadExportFile,
  exportSavedNotes,
  fetchSavedNote,
  fetchSavedNoteAssets,
  fetchSavedNoteComments,
  fetchSavedNotes,
  fetchTags,
} from "../../../lib/api";
import { formatShanghaiTime } from "../../../lib/time";
import type { NoteAsset, NoteComment, NotesExportResponse, SavedNote, Tag as TagType } from "../../../types";

const { Title, Text, Paragraph } = Typography;

function formatSavedTime(v: string): string { return formatShanghaiTime(v); }
function getRawNoteType(note: SavedNote): string { const t = note.raw_json?.model_type ?? note.raw_json?.type; return typeof t === "string" ? t : "note"; }
function getNotePublishTime(note: SavedNote): string {
  const raw = note.raw_json ?? {};
  const data = (raw.data && typeof raw.data === "object") ? raw.data as Record<string, unknown> : {};
  const items = Array.isArray(data.items) ? data.items : [];
  const item = (items[0] && typeof items[0] === "object") ? items[0] as Record<string, unknown> : {};
  const card = (item.note_card && typeof item.note_card === "object") ? item.note_card as Record<string, unknown> : {};
  const ts = card.time ?? card.create_time ?? card.last_update_time ?? raw.time ?? raw.create_time;
  if (ts) {
    const n = typeof ts === "number" ? ts : Number(ts);
    if (Number.isFinite(n) && n > 0) return new Date(n > 1e12 ? n : n * 1000).toLocaleDateString("zh-CN");
  }
  return "";
}
function getNoteUrl(note: SavedNote): string {
  const raw = note.raw_json ?? {};
  for (const key of ["note_url", "url", "share_url"]) {
    const v = raw[key];
    if (typeof v === "string" && v.startsWith("http")) return v;
  }
  const data = (raw.data && typeof raw.data === "object") ? raw.data as Record<string, unknown> : {};
  const items = Array.isArray(data.items) ? data.items : [];
  const item = (items[0] && typeof items[0] === "object") ? items[0] as Record<string, unknown> : {};
  const card = (item.note_card && typeof item.note_card === "object") ? item.note_card as Record<string, unknown> : {};
  for (const obj of [card, item]) {
    const xsec = obj.xsec_token;
    if (typeof xsec === "string" && xsec) {
      const src = (typeof obj.xsec_source === "string" ? obj.xsec_source : "") || "pc_feed";
      return `https://www.xiaohongshu.com/explore/${note.note_id}?xsec_token=${xsec}&xsec_source=${src}`;
    }
    for (const k of ["note_url", "url", "share_url"]) {
      const v = obj[k];
      if (typeof v === "string" && v.startsWith("http")) return v;
    }
  }
  return `https://www.xiaohongshu.com/explore/${note.note_id}`;
}
function getAuthorProfileUrl(note: SavedNote): string {
  const raw = note.raw_json ?? {};
  const directId = raw.author_id;
  if (typeof directId === "string" && directId) return `https://www.xiaohongshu.com/user/profile/${directId}`;
  const data = (raw.data && typeof raw.data === "object") ? raw.data as Record<string, unknown> : {};
  const items = Array.isArray(data.items) ? data.items : [];
  const item = (items[0] && typeof items[0] === "object") ? items[0] as Record<string, unknown> : {};
  const card = (item.note_card && typeof item.note_card === "object") ? item.note_card as Record<string, unknown> : {};
  const user = (card.user && typeof card.user === "object") ? card.user as Record<string, unknown> : {};
  const uid = user.user_id ?? user.id;
  if (typeof uid === "string" && uid) return `https://www.xiaohongshu.com/user/profile/${uid}`;
  return "";
}
function getNoteTags(note: SavedNote): string[] {
  const raw = note.raw_json ?? {};
  const directList = raw.tag_list ?? raw.tags;
  if (Array.isArray(directList) && directList.length > 0) {
    return directList.map((t: unknown) => {
      if (typeof t === "string") return t;
      if (t && typeof t === "object" && "name" in (t as Record<string, unknown>)) return String((t as Record<string, unknown>).name);
      return "";
    }).filter(Boolean);
  }
  const data = (raw.data && typeof raw.data === "object") ? raw.data as Record<string, unknown> : {};
  const items = Array.isArray(data.items) ? data.items : [];
  const item = (items[0] && typeof items[0] === "object") ? items[0] as Record<string, unknown> : {};
  const card = (item.note_card && typeof item.note_card === "object") ? item.note_card as Record<string, unknown> : {};
  const nestedList = card.tag_list;
  if (Array.isArray(nestedList) && nestedList.length > 0) {
    return nestedList.map((t: unknown) => {
      if (typeof t === "string") return t;
      if (t && typeof t === "object" && "name" in (t as Record<string, unknown>)) return String((t as Record<string, unknown>).name);
      return "";
    }).filter(Boolean);
  }
  return [];
}
function getNoteEngagement(note: SavedNote): { likes: number; collects: number; comments: number; shares: number } {
  const raw = note.raw_json ?? {};
  // Direct fields (from search results)
  const likes = Number(raw.liked_count ?? raw.likes ?? 0);
  const collects = Number(raw.collected_count ?? raw.collects ?? 0);
  const comments = Number(raw.comment_count ?? raw.comments ?? 0);
  const shares = Number(raw.share_count ?? raw.shares ?? 0);
  if (likes || collects || comments || shares) return { likes, collects, comments, shares };
  // Nested in data.items[0].note_card.interact_info
  const data = (raw.data && typeof raw.data === "object") ? raw.data as Record<string, unknown> : {};
  const items = Array.isArray(data.items) ? data.items : [];
  const item = (items[0] && typeof items[0] === "object") ? items[0] as Record<string, unknown> : {};
  const card = (item.note_card && typeof item.note_card === "object") ? item.note_card as Record<string, unknown> : {};
  const info = (card.interact_info && typeof card.interact_info === "object") ? card.interact_info as Record<string, unknown> : {};
  return {
    likes: Number(info.liked_count ?? 0),
    collects: Number(info.collected_count ?? 0),
    comments: Number(info.comment_count ?? 0),
    shares: Number(info.share_count ?? 0),
  };
}
function rawString(note: SavedNote, keys: string[]): string { for (const k of keys) { const v = note.raw_json?.[k]; if (typeof v === "string" && v) return v; } return ""; }
function getSavedNoteCoverUrl(note: SavedNote): string { return note.cover_url || note.asset_urls?.[0] || rawString(note, ["cover_url", "image_url"]); }

export function XhsLibraryPage() {
  const navigate = useNavigate();
  const [notes, setNotes] = useState<SavedNote[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNote, setSelectedNote] = useState<SavedNote | null>(null);
  const [selectedAssets, setSelectedAssets] = useState<NoteAsset[]>([]);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailActionMessage, setDetailActionMessage] = useState<string | null>(null);
  const [isCreatingDraft, setIsCreatingDraft] = useState(false);
  const [availableTags, setAvailableTags] = useState<TagType[]>([]);
  const [newTagName, setNewTagName] = useState("");
  const [tagActionMessage, setTagActionMessage] = useState<string | null>(null);
  const [isCommentsOpen, setIsCommentsOpen] = useState(false);
  const [comments, setComments] = useState<NoteComment[]>([]);
  const [commentsTotal, setCommentsTotal] = useState(0);
  const [commentsPage, setCommentsPage] = useState(1);
  const [isCommentsLoading, setIsCommentsLoading] = useState(false);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [keywordFilter, setKeywordFilter] = useState("");
  const [selectedTagFilter, setSelectedTagFilter] = useState("");
  const [hasAssetsFilter, setHasAssetsFilter] = useState(false);
  const [hasCommentsFilter, setHasCommentsFilter] = useState(false);
  const [viewMode, setViewMode] = useState<string>("card");
  const [selectedNoteIds, setSelectedNoteIds] = useState<number[]>([]);
  const [batchTagId, setBatchTagId] = useState<string>("");
  const [batchActionMessage, setBatchActionMessage] = useState<string | null>(null);
  const [isBatchWorking, setIsBatchWorking] = useState(false);
  const [latestExport, setLatestExport] = useState<NotesExportResponse | null>(null);
  const [selectedPreviewAsset, setSelectedPreviewAsset] = useState<NoteAsset | null>(null);

  const selectedNoteIdSet = new Set(selectedNoteIds);

  async function loadNotes(overrideFilters?: { q?: string; tag_id?: number; has_assets?: boolean; has_comments?: boolean }) {
    setIsLoading(true); setError(null);
    const f = overrideFilters ?? { q: keywordFilter.trim() || undefined, tag_id: selectedTagFilter ? Number(selectedTagFilter) : undefined, has_assets: hasAssetsFilter || undefined, has_comments: hasCommentsFilter || undefined };
    try {
      const r = await fetchSavedNotes({ platform: "xhs", ...f });
      setNotes(r.items); setTotal(r.total);
      const ids = new Set(r.items.map((n) => n.id));
      setSelectedNoteIds((c) => c.filter((id) => ids.has(id)));
    } catch { setError("内容库加载失败。"); } finally { setIsLoading(false); }
  }

  useEffect(() => { void loadNotes(); void loadTags(); }, []);

  function clearFilters() { setKeywordFilter(""); setSelectedTagFilter(""); setHasAssetsFilter(false); setHasCommentsFilter(false); void loadNotes({}); }
  function toggleNoteSelection(id: number) { setSelectedNoteIds((c) => c.includes(id) ? c.filter((i) => i !== id) : [...c, id]); }
  function toggleVisibleSelection() { if (!notes.length) return; const vis = notes.map((n) => n.id); const allSel = vis.every((id) => selectedNoteIdSet.has(id)); setSelectedNoteIds((c) => allSel ? c.filter((id) => !vis.includes(id)) : Array.from(new Set([...c, ...vis]))); }
  function clearSelection() { setSelectedNoteIds([]); setBatchActionMessage(null); }

  async function loadTags() { try { const r = await fetchTags(); setAvailableTags(r.items); } catch { setAvailableTags([]); } }

  async function openDetail(note: SavedNote) {
    setIsDetailOpen(true); setSelectedNote(note); setDetailError(null); setDetailActionMessage(null); setTagActionMessage(null); resetComments(); setIsDetailLoading(true);
    try { const [d, a] = await Promise.all([fetchSavedNote(note.id), fetchSavedNoteAssets(note.id)]); setSelectedNote(d); setSelectedAssets(a.items); }
    catch { setDetailError("笔记详情加载失败。"); } finally { setIsDetailLoading(false); }
  }
  function closeDetail() { setIsDetailOpen(false); setDetailError(null); setDetailActionMessage(null); setTagActionMessage(null); setSelectedAssets([]); resetComments(); }
  function resetComments() { setIsCommentsOpen(false); setComments([]); setCommentsTotal(0); setCommentsPage(1); setIsCommentsLoading(false); setCommentsError(null); }

  async function copySelectedNote() {
    if (!selectedNote) return;
    try { await navigator.clipboard.writeText(`${selectedNote.title}\n\n${selectedNote.content}`.trim()); setDetailActionMessage("已复制标题和正文。"); }
    catch { setDetailActionMessage("复制失败。"); }
  }

  async function createDraft(intent: "rewrite" | "publish") {
    if (!selectedNote) return; setIsCreatingDraft(true); setDetailActionMessage(null);
    try {
      const d = await createDraftFromNote({ platform: "xhs", source_note_id: selectedNote.id, intent });
      setDetailActionMessage(intent === "rewrite" ? `已创建草稿 #${d.id}，正在跳转...` : `已创建草稿 #${d.id}，正在跳转...`);
      setTimeout(() => navigate("/platforms/xhs/drafts"), 600);
    }
    catch { setDetailActionMessage("草稿创建失败。"); } finally { setIsCreatingDraft(false); }
  }

  async function addToDrafts() {
    if (!selectedNote) return; setIsCreatingDraft(true); setDetailActionMessage(null);
    try {
      const d = await createDraftFromNote({ platform: "xhs", source_note_id: selectedNote.id, intent: "rewrite" });
      setDetailActionMessage(`已加入草稿工坊，草稿 #${d.id}。`);
    }
    catch { setDetailActionMessage("加入草稿工坊失败。"); } finally { setIsCreatingDraft(false); }
  }

  async function handleDeleteNote(note: SavedNote) {
    Modal.confirm({
      title: "确定删除？", content: "相关素材、评论和标签关系也会一起删除。",
      onOk: async () => {
        try {
          await deleteSavedNote(note.id);
          setNotes((c) => c.filter((n) => n.id !== note.id));
          setSelectedNoteIds((c) => c.filter((id) => id !== note.id));
          setTotal((c) => Math.max(0, c - 1));
          if (selectedNote?.id === note.id) closeDetail();
          setBatchActionMessage("已删除笔记。");
        } catch { setBatchActionMessage("删除失败。"); }
      },
    });
  }

  function selectedNoteHasTag(tagId: number): boolean { return Boolean(selectedNote?.tags?.some((t) => t.id === tagId)); }
  function replaceNoteInList(u: SavedNote) { setNotes((c) => c.map((n) => n.id === u.id ? u : n)); }
  function replaceNotesInList(us: SavedNote[]) { const m = new Map(us.map((n) => [n.id, n])); setNotes((c) => c.map((n) => m.get(n.id) ?? n)); if (selectedNote) { const u = m.get(selectedNote.id); if (u) setSelectedNote(u); } }

  async function applyBatchTag(mode: "add" | "remove") {
    if (!selectedNoteIds.length) { setBatchActionMessage("请先选择笔记。"); return; }
    if (!batchTagId) { setBatchActionMessage("请选择一个标签。"); return; }
    setIsBatchWorking(true); setBatchActionMessage(null);
    try { const r = await batchTagNotes({ note_ids: selectedNoteIds, tag_ids: [Number(batchTagId)], mode }); replaceNotesInList(r.items); setBatchActionMessage(mode === "add" ? `已添加标签 (${r.updated_count})` : `已移除标签 (${r.updated_count})`); }
    catch { setBatchActionMessage("批量标签操作失败。"); } finally { setIsBatchWorking(false); }
  }

  async function createBatchRewriteDrafts() {
    if (!selectedNoteIds.length) { setBatchActionMessage("请先选择笔记。"); return; }
    setIsBatchWorking(true); setBatchActionMessage(null);
    try { const r = await batchCreateDraftsFromNotes({ note_ids: selectedNoteIds, intent: "rewrite" }); setBatchActionMessage(`已创建 ${r.created_count} 个改写草稿。`); }
    catch { setBatchActionMessage("批量创建草稿失败。"); } finally { setIsBatchWorking(false); }
  }

  async function exportSelectedNotes(format: "json" | "csv") {
    if (!selectedNoteIds.length) { setBatchActionMessage("请先选择笔记。"); return; }
    setIsBatchWorking(true); setBatchActionMessage(null);
    try { const r = await exportSavedNotes({ note_ids: selectedNoteIds, format }); setLatestExport(r); setBatchActionMessage(`已导出 ${r.exported_count} 条笔记。`); }
    catch { setBatchActionMessage("导出失败。"); } finally { setIsBatchWorking(false); }
  }

  async function batchDeleteNotes() {
    if (!selectedNoteIds.length) return;
    setIsBatchWorking(true); setBatchActionMessage(null);
    try {
      for (const id of selectedNoteIds) {
        await deleteSavedNote(id);
      }
      setNotes((c) => c.filter((n) => !selectedNoteIds.includes(n.id)));
      setTotal((c) => Math.max(0, c - selectedNoteIds.length));
      setBatchActionMessage(`已删除 ${selectedNoteIds.length} 条笔记。`);
      setSelectedNoteIds([]);
    } catch { setBatchActionMessage("批量删除失败。"); }
    finally { setIsBatchWorking(false); }
  }

  async function downloadLatestExport() {
    if (!latestExport) return; setIsBatchWorking(true); setBatchActionMessage(null);
    try { await downloadExportFile(latestExport.download_url, latestExport.file_name); setBatchActionMessage(`已下载：${latestExport.file_name}`); }
    catch { setBatchActionMessage("下载失败。"); } finally { setIsBatchWorking(false); }
  }

  async function toggleSelectedTag(tag: TagType) {
    if (!selectedNote) return; setTagActionMessage(null);
    const mode = selectedNoteHasTag(tag.id) ? "remove" : "add";
    try { const r = await batchTagNotes({ note_ids: [selectedNote.id], tag_ids: [tag.id], mode }); const u = r.items[0]; setSelectedNote(u); replaceNoteInList(u); }
    catch { setTagActionMessage("标签更新失败。"); }
  }

  async function createAndAssignTag() {
    if (!selectedNote) return; const name = newTagName.trim(); if (!name) { setTagActionMessage("请输入标签名称。"); return; }
    setTagActionMessage(null);
    try { const c = await createTag({ name, color: "#111111" }); setAvailableTags((t) => [...t, c]); setNewTagName(""); const r = await batchTagNotes({ note_ids: [selectedNote.id], tag_ids: [c.id], mode: "add" }); const u = r.items[0]; setSelectedNote(u); replaceNoteInList(u); }
    catch { setTagActionMessage("标签创建失败。"); }
  }

  async function loadComments(page = 1) {
    if (!selectedNote) return; setIsCommentsLoading(true); setCommentsError(null);
    try { const r = await fetchSavedNoteComments(selectedNote.id, page); setComments((c) => page === 1 ? r.items : [...c, ...r.items]); setCommentsTotal(r.total); setCommentsPage(page); }
    catch { setCommentsError("评论加载失败。"); } finally { setIsCommentsLoading(false); }
  }

  function toggleComments() { const next = !isCommentsOpen; setIsCommentsOpen(next); if (next && selectedNote && comments.length === 0) void loadComments(1); }
  const topLevelComments = comments.filter((c) => !c.parent_comment_id);
  function childComments(pid: string) { return comments.filter((c) => c.parent_comment_id === pid); }

  const tableColumns: ColumnsType<SavedNote> = [
    { title: "标题", dataIndex: "title", ellipsis: true, render: (t: string, n) => <a onClick={() => void openDetail(n)}>{t || "未命名"}</a> },
    { title: "作者", dataIndex: "author_name", width: 120 },
    { title: "笔记 ID", dataIndex: "note_id", width: 140, ellipsis: true },
    { title: "保存时间", dataIndex: "created_at", width: 160, render: (v: string) => formatSavedTime(v) },
    { title: "标签", key: "tags", width: 180, render: (_, n) => n.tags?.length ? <Space size={4} wrap>{n.tags.map((t) => <Tag key={t.id} color="blue">{t.name}</Tag>)}</Space> : <Text type="secondary">-</Text> },
    { title: "操作", key: "actions", width: 80, render: (_, n) => <Button type="text" danger icon={<DeleteOutlined />} size="small" onClick={(e) => { e.stopPropagation(); void handleDeleteNote(n); }} /> },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col><Title level={4} style={{ margin: 0 }}>内容库</Title><Text type="secondary">保存的笔记素材，支持标签、筛选、批量操作和导出</Text></Col>
        <Col><Button icon={<ReloadOutlined />} onClick={() => void loadNotes()} loading={isLoading}>刷新</Button></Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card size="small"><Statistic title="已保存笔记" value={total} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="当前视图" value={viewMode === "card" ? "卡片" : "表格"} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="已选择" value={selectedNoteIds.length} suffix="条" /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="平台" value="XHS" /></Card></Col>
      </Row>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={12} align="middle">
          <Col span={5}><Input placeholder="标题、正文、作者" value={keywordFilter} onChange={(e) => setKeywordFilter(e.target.value)} allowClear /></Col>
          <Col span={4}><Select value={selectedTagFilter || undefined} onChange={(v) => setSelectedTagFilter(v ?? "")} placeholder="全部标签" allowClear style={{ width: "100%" }} options={availableTags.map((t) => ({ value: String(t.id), label: t.name }))} /></Col>
          <Col><Checkbox checked={hasAssetsFilter} onChange={(e) => setHasAssetsFilter(e.target.checked)}>有素材</Checkbox></Col>
          <Col><Checkbox checked={hasCommentsFilter} onChange={(e) => setHasCommentsFilter(e.target.checked)}>有评论</Checkbox></Col>
          <Col><Segmented value={viewMode} onChange={(v) => setViewMode(v as string)} options={[{ label: "卡片", value: "card" }, { label: "表格", value: "table" }]} /></Col>
          <Col><Button onClick={clearFilters}>重置</Button></Col>
          <Col><Button type="primary" onClick={() => void loadNotes()} loading={isLoading}>筛选</Button></Col>
        </Row>
      </Card>

      {notes.length > 0 && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space wrap>
            <Checkbox checked={notes.length > 0 && notes.every((n) => selectedNoteIdSet.has(n.id))} onChange={toggleVisibleSelection}>选择当前页</Checkbox>
            <Text strong>{selectedNoteIds.length} 条已选</Text>
            <Button icon={<CheckSquareOutlined />} disabled={isBatchWorking || !selectedNoteIds.length} onClick={createBatchRewriteDrafts} size="small">批量加入草稿工坊</Button>
            <Button type="primary" icon={<DownloadOutlined />} disabled={isBatchWorking || !selectedNoteIds.length} onClick={() => exportSelectedNotes("json")} size="small">JSON</Button>
            <Button icon={<DownloadOutlined />} disabled={isBatchWorking || !selectedNoteIds.length} onClick={() => exportSelectedNotes("csv")} size="small">CSV</Button>
            {latestExport && <Button icon={<DownloadOutlined />} disabled={isBatchWorking} onClick={downloadLatestExport} size="small">下载</Button>}
            <Popconfirm title={`确定删除选中的 ${selectedNoteIds.length} 条笔记？`} onConfirm={batchDeleteNotes}>
              <Button danger icon={<DeleteOutlined />} disabled={isBatchWorking || !selectedNoteIds.length} size="small">批量删除</Button>
            </Popconfirm>
            <Button disabled={!selectedNoteIds.length} onClick={clearSelection} size="small">清空选择</Button>
          </Space>
          {batchActionMessage && <Alert message={batchActionMessage} type="info" showIcon style={{ marginTop: 8 }} closable onClose={() => setBatchActionMessage(null)} />}
        </Card>
      )}

      {error && <Alert message={error} type="error" showIcon style={{ marginBottom: 16 }} />}

      {isLoading ? <Spin size="large" style={{ display: "block", textAlign: "center", margin: "48px 0" }} /> : notes.length === 0 ? (
        <Empty description="内容库还是空的"><Link to="/platforms/xhs/discovery"><Button type="primary" icon={<BookOutlined />}>去发现笔记</Button></Link></Empty>
      ) : viewMode === "table" ? (
        <Card size="small">
          <Table<SavedNote> columns={tableColumns} dataSource={notes} rowKey="id" size="small" pagination={{ pageSize: 20 }}
            rowSelection={{ selectedRowKeys: selectedNoteIds, onChange: (keys) => setSelectedNoteIds(keys as number[]) }}
            onRow={(n) => ({ onClick: () => void openDetail(n), style: { cursor: "pointer" } })} />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {notes.map((note) => {
            const cover = getSavedNoteCoverUrl(note);
            const kind = getRawNoteType(note);
            return (
              <Col xs={12} sm={8} md={6} lg={4} xl={4} key={note.id}>
                <Card hoverable size="small" style={{ overflow: "hidden" }} onClick={() => void openDetail(note)}
                  cover={
                    <div style={{ position: "relative", background: "#262626" }}>
                      <Checkbox checked={selectedNoteIdSet.has(note.id)} onClick={(e) => { e.stopPropagation(); toggleNoteSelection(note.id); }} style={{ position: "absolute", top: 8, left: 8, zIndex: 2 }} />
                      {cover ? <img src={cover} alt={note.title} referrerPolicy="no-referrer" style={{ width: "100%", aspectRatio: "1/1", objectFit: "cover", display: "block" }} /> : <div style={{ width: "100%", aspectRatio: "1/1", display: "flex", alignItems: "center", justifyContent: "center", color: "rgba(255,255,255,.2)", fontSize: 28 }}><PictureOutlined /></div>}
                      <Tag color={kind.includes("video") ? "purple" : "blue"} style={{ position: "absolute", top: 8, right: 8 }} icon={kind.includes("video") ? <PlayCircleOutlined /> : <PictureOutlined />}>{kind.includes("video") ? "视频" : "图文"}</Tag>
                    </div>
                  }>
                  <Card.Meta title={<Text ellipsis style={{ fontSize: 13 }}>{note.title || "未命名"}</Text>} description={
                    <>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>{note.author_name}</Text>
                        {getNotePublishTime(note) ? <Text type="secondary" style={{ fontSize: 11, marginLeft: 6 }}>{getNotePublishTime(note)}</Text> : <Text type="secondary" style={{ fontSize: 11, marginLeft: 6 }}>{formatSavedTime(note.created_at)}</Text>}
                      </div>
                      {(() => {
                        const eng = getNoteEngagement(note);
                        if (!eng.likes && !eng.collects && !eng.comments && !eng.shares) return null;
                        return (
                          <div style={{ marginTop: 4, display: "flex", gap: 8, fontSize: 11, color: "rgba(255,255,255,.45)" }}>
                            {eng.likes > 0 && <span><HeartOutlined /> {eng.likes}</span>}
                            {eng.collects > 0 && <span><StarOutlined /> {eng.collects}</span>}
                            {eng.comments > 0 && <span><MessageOutlined /> {eng.comments}</span>}
                            {eng.shares > 0 && <span><ShareAltOutlined /> {eng.shares}</span>}
                          </div>
                        );
                      })()}
                    </>
                  } />
                  {note.tags?.length ? <div style={{ marginTop: 6 }}>{note.tags.map((t) => <Tag key={t.id} color="blue" style={{ fontSize: 11 }}>{t.name}</Tag>)}</div> : null}
                </Card>
              </Col>
            );
          })}
        </Row>
      )}

      <Drawer title={selectedNote?.title || "笔记详情"} open={isDetailOpen} onClose={closeDetail} width={640} styles={{ body: { background: "#1a1a1a" } }}>
        {selectedNote && (
          <Spin spinning={isDetailLoading}>
            {detailError && <Alert message={detailError} type="warning" showIcon style={{ marginBottom: 12 }} />}
            {detailActionMessage && <Alert message={detailActionMessage} type="success" showIcon style={{ marginBottom: 12 }} closable onClose={() => setDetailActionMessage(null)} />}

            <Descriptions column={1} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="作者">{getAuthorProfileUrl(selectedNote) ? <Typography.Link href={getAuthorProfileUrl(selectedNote)} target="_blank" rel="noreferrer">{selectedNote.author_name || "未知"}</Typography.Link> : (selectedNote.author_name || "未知")}</Descriptions.Item>
              <Descriptions.Item label="互动">赞 {getNoteEngagement(selectedNote).likes} · 藏 {getNoteEngagement(selectedNote).collects} · 评 {getNoteEngagement(selectedNote).comments}</Descriptions.Item>
              <Descriptions.Item label="笔记 ID">{selectedNote.note_id}</Descriptions.Item>
              <Descriptions.Item label="保存时间">{formatSavedTime(selectedNote.created_at)}</Descriptions.Item>
              {getNotePublishTime(selectedNote) && <Descriptions.Item label="发布时间">{getNotePublishTime(selectedNote)}</Descriptions.Item>}
              <Descriptions.Item label="作品链接"><Typography.Link href={getNoteUrl(selectedNote)} target="_blank" rel="noreferrer" style={{ fontSize: 12, wordBreak: "break-all" }}>{getNoteUrl(selectedNote)}</Typography.Link></Descriptions.Item>
            </Descriptions>

            {getNoteTags(selectedNote).length > 0 && (
              <div style={{ marginBottom: 12 }}>{getNoteTags(selectedNote).map((t) => <Tag key={t} color="blue">#{t}</Tag>)}</div>
            )}

            <Button type="link" icon={<LinkOutlined />} href={getNoteUrl(selectedNote)} target="_blank" rel="noreferrer" style={{ padding: 0, marginBottom: 16 }}>查看原文</Button>

            <Space wrap style={{ marginBottom: 16 }}>
              <Button icon={<CopyOutlined />} onClick={copySelectedNote} size="small">复制内容</Button>
              <Button icon={<FileAddOutlined />} onClick={addToDrafts} loading={isCreatingDraft} size="small">加入草稿工坊</Button>
              <Button icon={<EditOutlined />} onClick={() => createDraft("rewrite")} loading={isCreatingDraft} size="small">AI 改写</Button>
              <Popconfirm title="确定删除？" onConfirm={() => void handleDeleteNote(selectedNote)}><Button danger icon={<DeleteOutlined />} size="small">删除</Button></Popconfirm>
            </Space>

            {selectedAssets.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Text strong style={{ display: "block", marginBottom: 6 }}>素材 ({selectedAssets.length})</Text>
                <Image.PreviewGroup>
                  <Space size={8} wrap>
                    {selectedAssets.map((a) => (
                      a.asset_type === "video" ? (
                        <div key={a.id} style={{ width: 80, height: 80, background: "#262626", borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <Button type="link" icon={<PlayCircleOutlined />} href={a.url} target="_blank" rel="noreferrer">视频</Button>
                        </div>
                      ) : <Image key={a.id} src={a.url} width={80} height={80} style={{ objectFit: "cover", borderRadius: 6 }} referrerPolicy="no-referrer" />
                    ))}
                  </Space>
                </Image.PreviewGroup>
              </div>
            )}

            <div style={{ marginBottom: 16 }}>
              <Text strong>正文</Text>
              <Paragraph style={{ marginTop: 4, color: "rgba(255,255,255,.65)", whiteSpace: "pre-wrap" }}>{selectedNote.content || "暂无正文。"}</Paragraph>
            </div>

            <Button onClick={toggleComments} style={{ marginBottom: 8 }}>{isCommentsOpen ? "收起评论" : `查看评论 (${commentsTotal})`}</Button>
            {isCommentsOpen && (
              <Card size="small" style={{ background: "#1f1f1f" }}>
                {commentsError && <Alert message={commentsError} type="error" showIcon style={{ marginBottom: 8 }} />}
                {isCommentsLoading && <Spin size="small" />}
                {topLevelComments.length === 0 && !isCommentsLoading ? <Text type="secondary">暂无评论</Text> : null}
                {topLevelComments.map((c) => (
                  <div key={c.comment_id} style={{ marginBottom: 10, paddingBottom: 8, borderBottom: "1px solid #303030" }}>
                    <Space><Text strong style={{ fontSize: 13 }}>{c.user_name}</Text><Text type="secondary" style={{ fontSize: 11 }}>{c.created_at_remote} · {c.like_count} likes</Text></Space>
                    <div style={{ color: "rgba(255,255,255,.65)", fontSize: 13, marginTop: 2 }}>{c.content}</div>
                    {childComments(c.comment_id).map((r) => (
                      <div key={r.comment_id} style={{ marginLeft: 20, marginTop: 4, paddingLeft: 8, borderLeft: "2px solid #303030" }}>
                        <Space><Text strong style={{ fontSize: 12 }}>{r.user_name}</Text><Text type="secondary" style={{ fontSize: 11 }}>{r.like_count} likes</Text></Space>
                        <div style={{ color: "rgba(255,255,255,.55)", fontSize: 12 }}>{r.content}</div>
                      </div>
                    ))}
                  </div>
                ))}
                {comments.length < commentsTotal && <Button size="small" onClick={() => void loadComments(commentsPage + 1)} loading={isCommentsLoading}>加载更多</Button>}
              </Card>
            )}

            {selectedNote.raw_json && (
              <details style={{ marginTop: 16 }}>
                <summary style={{ cursor: "pointer", color: "rgba(255,255,255,.45)", fontSize: 12 }}>原始 JSON</summary>
                <pre style={{ fontSize: 11, color: "rgba(255,255,255,.5)", background: "#1f1f1f", padding: 8, borderRadius: 6, overflow: "auto", maxHeight: 300 }}>{JSON.stringify(selectedNote.raw_json, null, 2)}</pre>
              </details>
            )}
          </Spin>
        )}
      </Drawer>
    </div>
  );
}
