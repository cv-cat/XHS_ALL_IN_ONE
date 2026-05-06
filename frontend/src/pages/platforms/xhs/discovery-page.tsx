import {
  CheckOutlined,
  CommentOutlined,
  DatabaseOutlined,
  HeartOutlined,
  LeftOutlined,
  LinkOutlined,
  LoadingOutlined,
  PlayCircleOutlined,
  PictureOutlined,
  ReloadOutlined,
  RightOutlined,
  SearchOutlined,
  StarOutlined,
} from "@ant-design/icons";
import { Alert, Badge, Button, Card, Col, Descriptions, Drawer, Empty, Input, Row, Select, Space, Spin, Tag, Typography } from "antd";
import { FormEvent, MouseEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { fetchAccounts, fetchSavedNoteIds, fetchXhsNoteComments, fetchXhsNoteDetail, saveXhsNotesToLibrary, searchXhsNotes } from "../../../lib/api";
import type { NoteComment, PlatformAccount, XhsSearchNote, XhsSearchOptions } from "../../../types";

const { Title, Text, Paragraph } = Typography;

const sortOptions = [{ value: 0, label: "综合排序" }, { value: 1, label: "最新" }, { value: 2, label: "最多点赞" }, { value: 3, label: "最多评论" }, { value: 4, label: "最多收藏" }];
const noteTypeOptions = [{ value: 0, label: "不限类型" }, { value: 1, label: "视频笔记" }, { value: 2, label: "普通笔记" }];
const noteTimeOptions = [{ value: 0, label: "不限时间" }, { value: 1, label: "一天内" }, { value: 2, label: "一周内" }, { value: 3, label: "半年内" }];
const noteRangeOptions = [{ value: 0, label: "不限范围" }, { value: 1, label: "已看过" }, { value: 2, label: "未看过" }, { value: 3, label: "已关注" }];
const distanceOptions = [{ value: 0, label: "不限距离" }, { value: 1, label: "同城" }, { value: 2, label: "附近" }];

function formatMetric(value: number): string {
  if (value >= 10000) return `${(value / 10000).toFixed(value >= 100000 ? 0 : 1)}w`;
  return value.toLocaleString();
}
function formatNoteTime(note: XhsSearchNote): string {
  const ts = note.timestamp;
  if (ts) {
    const num = typeof ts === "number" ? ts : Number(ts);
    if (Number.isFinite(num) && num > 0) {
      return new Date(num > 1e12 ? num : num * 1000).toLocaleDateString("zh-CN");
    }
    if (typeof ts === "string") return ts;
  }
  const raw = note.raw ?? {};
  const data = (raw.data && typeof raw.data === "object") ? raw.data as Record<string, unknown> : {};
  const items = Array.isArray(data.items) ? data.items : [];
  const item = (items[0] && typeof items[0] === "object") ? items[0] as Record<string, unknown> : {};
  const card = (item.note_card && typeof item.note_card === "object") ? item.note_card as Record<string, unknown> : {};
  const deep = card.time ?? card.create_time ?? card.last_update_time ?? raw.time ?? raw.create_time;
  if (deep) {
    const n = typeof deep === "number" ? deep : Number(deep);
    if (Number.isFinite(n) && n > 0) {
      return new Date(n > 1e12 ? n : n * 1000).toLocaleDateString("zh-CN");
    }
  }
  return "";
}
function rawString(note: XhsSearchNote, keys: string[]): string {
  for (const key of keys) { const v = note.raw?.[key]; if (typeof v === "string" && v) return v; } return "";
}
function getPreviewNoteUrl(note: XhsSearchNote): string {
  return note.note_url || rawString(note, ["note_url", "url", "share_url"]) || (note.note_id ? `https://www.xiaohongshu.com/explore/${note.note_id}` : "");
}
function getCoverUrl(note: XhsSearchNote): string { return note.cover_url || note.image_urls?.[0] || rawString(note, ["cover_url", "image_url"]); }
function getNoteImageUrls(note: XhsSearchNote): string[] { const urls = note.image_urls?.length ? note.image_urls : [getCoverUrl(note)]; return urls.filter((u): u is string => Boolean(u)); }
function getNoteVideoUrl(note: XhsSearchNote): string { return note.video_url || note.video_addr || rawString(note, ["video_url", "video_addr"]); }
function getNoteKindLabel(note: XhsSearchNote): "视频" | "图文" {
  const rawType = rawString(note, ["type", "note_type", "model_type"]);
  return `${note.type || rawType}`.toLowerCase().includes("video") || Boolean(getNoteVideoUrl(note)) ? "视频" : "图文";
}
function stopCardClick(e: MouseEvent<HTMLElement>) { e.stopPropagation(); }

export function XhsDiscoveryPage() {
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [keyword, setKeyword] = useState("");
  const [noteUrl, setNoteUrl] = useState("");
  const [filters, setFilters] = useState({ sort_type_choice: 0, note_type: 0, note_time: 0, note_range: 0, pos_distance: 0, geo: "" });
  const [notes, setNotes] = useState<XhsSearchNote[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(true);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isFetchingUrl, setIsFetchingUrl] = useState(false);
  const [isFetchingDetail, setIsFetchingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchedKeyword, setSearchedKeyword] = useState("");
  const [savingNoteIds, setSavingNoteIds] = useState<string[]>([]);
  const [savedNoteIds, setSavedNoteIds] = useState<string[]>([]);
  const [selectedNote, setSelectedNote] = useState<XhsSearchNote | null>(null);
  const [detailMediaIndex, setDetailMediaIndex] = useState(0);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [commentPreviewByNoteId, setCommentPreviewByNoteId] = useState<Record<string, NoteComment[]>>({});
  const [commentPreviewErrors, setCommentPreviewErrors] = useState<Record<string, string>>({});
  const [loadingCommentNoteIds, setLoadingCommentNoteIds] = useState<string[]>([]);

  const pcAccounts = useMemo(() => accounts.filter((a) => a.platform === "xhs" && a.sub_type === "pc"), [accounts]);
  const pcAccountOptions = useMemo(() => pcAccounts.map((a) => ({ value: a.id, label: `${a.nickname || `PC ${a.id}`} · ${a.status}` })), [pcAccounts]);

  async function loadAccounts() {
    setIsLoadingAccounts(true); setError(null);
    try { const loaded = await fetchAccounts("xhs"); setAccounts(loaded); const first = loaded.find((a) => a.sub_type === "pc"); setSelectedAccountId((c) => c ?? first?.id ?? null); }
    catch { setError("账号列表加载失败。"); } finally { setIsLoadingAccounts(false); }
  }

  function searchPayload(nextPage: number): XhsSearchOptions | null {
    if (!selectedAccountId) { setError("请先选择一个 PC 账号。"); return null; }
    if (!keyword.trim()) { setError("请输入要搜索的关键词。"); return null; }
    return { account_id: selectedAccountId, keyword: keyword.trim(), page: nextPage, ...filters, geo: filters.geo.trim() };
  }

  async function runSearch(nextPage: number, append: boolean) {
    const payload = searchPayload(nextPage); if (!payload) return;
    setError(null); append ? setIsLoadingMore(true) : setIsSearching(true);
    try {
      const result = await searchXhsNotes(payload);
      setNotes((c) => append ? [...c, ...result.items] : result.items);
      setPage(result.page); setHasMore(result.has_more);
      void loadSavedNoteIds();
      setCommentPreviewByNoteId((c) => append ? c : {}); setCommentPreviewErrors((c) => append ? c : {}); setSearchedKeyword(payload.keyword);
    } catch (err: unknown) { const a = err as { response?: { status?: number; data?: { detail?: string } }; message?: string }; setError(a?.response?.data?.detail ? `[${a.response.status}] ${a.response.data.detail}` : `搜索失败：${a?.message || "请检查网络和后端服务"}`); }
    finally { setIsSearching(false); setIsLoadingMore(false); }
  }

  async function handleSearch(e: FormEvent) { e.preventDefault(); await runSearch(1, false); }
  async function handleLoadMore() { await runSearch(page + 1, true); }

  async function loadSavedNoteIds() {
    try {
      const ids = await fetchSavedNoteIds("xhs");
      setSavedNoteIds(ids);
    } catch { /* ignore */ }
  }

  async function handleSaveNote(note: XhsSearchNote) {
    setError(null); if (!selectedAccountId) { setError("请先选择一个 PC 账号。"); return; }
    setSavingNoteIds((c) => [...c, note.note_id]);
    try { const d = await ensureNoteDetail(note); await saveXhsNotesToLibrary({ account_id: selectedAccountId, notes: [d] }); setSavedNoteIds((c) => c.includes(note.note_id) ? c : [...c, note.note_id]); }
    catch { setError("保存到内容库失败。"); } finally { setSavingNoteIds((c) => c.filter((id) => id !== note.note_id)); }
  }

  async function ensureNoteDetail(note: XhsSearchNote): Promise<XhsSearchNote> {
    const url = getPreviewNoteUrl(note); if (!selectedAccountId || !url) return note;
    const detail = await fetchXhsNoteDetail({ account_id: selectedAccountId, url });
    const merged = { ...note, ...detail, note_url: detail.note_url || url };
    setNotes((c) => c.map((n) => n.note_id === note.note_id ? merged : n));
    setSelectedNote((c) => c?.note_id === note.note_id ? merged : c); return merged;
  }

  async function handleFetchUrlDetail() {
    setError(null); if (!selectedAccountId) { setError("请先选择一个 PC 账号。"); return; }
    const cleanUrl = noteUrl.trim(); if (!cleanUrl) { setError("请输入小红书笔记 URL。"); return; }
    setIsFetchingUrl(true);
    try {
      const detail = await fetchXhsNoteDetail({ account_id: selectedAccountId, url: cleanUrl });
      const merged = { ...detail, note_url: detail.note_url || cleanUrl };
      setNotes([merged]); setDetailMediaIndex(0); setSelectedNote(merged); setHasMore(false); setPage(1);
      setSearchedKeyword("URL 直查"); setSavedNoteIds([]); setCommentPreviewByNoteId({}); setCommentPreviewErrors({});
    } catch (err: unknown) { const a = err as { response?: { status?: number; data?: { detail?: string } }; message?: string }; setError(a?.response?.data?.detail ? `[${a.response.status}] ${a.response.data.detail}` : `URL 直查失败：${a?.message || "请检查网络"}`); } finally { setIsFetchingUrl(false); }
  }

  async function openDetail(note: XhsSearchNote) {
    setDetailMediaIndex(0); setSelectedNote(note); setDetailError(null);
    if (!selectedAccountId) { setDetailError("请先选择一个 PC 账号。"); return; }
    const url = getPreviewNoteUrl(note); if (!url) { setDetailError("缺少可用于获取详情的笔记 URL。"); return; }
    setIsFetchingDetail(true);
    try { const detail = await fetchXhsNoteDetail({ account_id: selectedAccountId, url }); setDetailMediaIndex(0); setSelectedNote({ ...note, ...detail, note_url: detail.note_url || url }); }
    catch { setDetailError("详情加载失败，已保留搜索结果预览。"); } finally { setIsFetchingDetail(false); }
  }

  function closeDetail() { setSelectedNote(null); setDetailMediaIndex(0); setDetailError(null); }

  function getChildComments(noteId: string, parentId: string): NoteComment[] {
    return (commentPreviewByNoteId[noteId] ?? []).filter((c) => c.parent_comment_id === parentId);
  }

  async function handlePreviewComments(note: XhsSearchNote) {
    setError(null); if (!selectedAccountId) { setError("请先选择一个 PC 账号。"); return; }
    const url = getPreviewNoteUrl(note);
    if (!url) { setCommentPreviewErrors((c) => ({ ...c, [note.note_id]: "缺少笔记 URL。" })); return; }
    if (commentPreviewByNoteId[note.note_id]) { setCommentPreviewByNoteId((c) => { const n = { ...c }; delete n[note.note_id]; return n; }); return; }
    setLoadingCommentNoteIds((c) => [...c, note.note_id]); setCommentPreviewErrors((c) => ({ ...c, [note.note_id]: "" }));
    try { const r = await fetchXhsNoteComments({ account_id: selectedAccountId, note_url: url }); setCommentPreviewByNoteId((c) => ({ ...c, [note.note_id]: r.items })); }
    catch { setCommentPreviewErrors((c) => ({ ...c, [note.note_id]: "评论加载失败。" })); }
    finally { setLoadingCommentNoteIds((c) => c.filter((id) => id !== note.note_id)); }
  }

  useEffect(() => { void loadAccounts(); void loadSavedNoteIds(); }, []);

  const noPcAccount = !isLoadingAccounts && pcAccounts.length === 0;
  const selImgUrls = selectedNote ? getNoteImageUrls(selectedNote) : [];
  const selVideoUrl = selectedNote ? getNoteVideoUrl(selectedNote) : "";
  const selMediaIdx = selImgUrls.length ? Math.min(detailMediaIndex, selImgUrls.length - 1) : 0;

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col><Title level={4} style={{ margin: 0 }}>笔记发现</Title><Text type="secondary">按关键词或链接查找笔记，查看详情、评论和原文，保存到内容库</Text></Col>
        <Col><Button icon={<ReloadOutlined />} onClick={loadAccounts} loading={isLoadingAccounts}>刷新账号</Button></Col>
      </Row>

      <Card style={{ marginBottom: 24 }}>
        <form onSubmit={(e) => { e.preventDefault(); void runSearch(1, false); }}>
          <Row gutter={[12, 12]}>
            <Col span={6}><div style={{ marginBottom: 4 }}><Text type="secondary" style={{ fontSize: 12 }}>搜索账号</Text></div><Select value={selectedAccountId} onChange={setSelectedAccountId} placeholder="选择 PC 账号" style={{ width: "100%" }} options={pcAccountOptions} /></Col>
            <Col span={6}><div style={{ marginBottom: 4 }}><Text type="secondary" style={{ fontSize: 12 }}>关键词</Text></div><Input.Search value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="低卡早餐、通勤穿搭" loading={isSearching} onSearch={() => void runSearch(1, false)} enterButton /></Col>
            <Col span={3}><div style={{ marginBottom: 4 }}><Text type="secondary" style={{ fontSize: 12 }}>排序</Text></div><Select value={filters.sort_type_choice} onChange={(v) => setFilters((c) => ({ ...c, sort_type_choice: v }))} style={{ width: "100%" }} options={sortOptions} /></Col>
            <Col span={3}><div style={{ marginBottom: 4 }}><Text type="secondary" style={{ fontSize: 12 }}>类型</Text></div><Select value={filters.note_type} onChange={(v) => setFilters((c) => ({ ...c, note_type: v }))} style={{ width: "100%" }} options={noteTypeOptions} /></Col>
            <Col span={3}><div style={{ marginBottom: 4 }}><Text type="secondary" style={{ fontSize: 12 }}>时间</Text></div><Select value={filters.note_time} onChange={(v) => setFilters((c) => ({ ...c, note_time: v }))} style={{ width: "100%" }} options={noteTimeOptions} /></Col>
            <Col span={3}><div style={{ marginBottom: 4 }}><Text type="secondary" style={{ fontSize: 12 }}>范围</Text></div><Select value={filters.note_range} onChange={(v) => setFilters((c) => ({ ...c, note_range: v }))} style={{ width: "100%" }} options={noteRangeOptions} /></Col>
          </Row>
          <Row gutter={12} style={{ marginTop: 12 }} align="bottom">
            <Col span={6}><div style={{ marginBottom: 4 }}><Text type="secondary" style={{ fontSize: 12 }}>笔记 URL</Text></div><Input value={noteUrl} onChange={(e) => setNoteUrl(e.target.value)} placeholder="https://www.xiaohongshu.com/explore/..." /></Col>
            <Col><Button icon={<SearchOutlined />} loading={isFetchingUrl} disabled={noPcAccount} onClick={handleFetchUrlDetail}>URL 直查</Button></Col>
          </Row>
        </form>
        {error && <Alert message={error} type="error" showIcon style={{ marginTop: 12 }} closable onClose={() => setError(null)} />}
        {noPcAccount && <Empty description="还没有可用的 PC 账号" style={{ marginTop: 24 }}><Link to="/platforms/xhs/accounts"><Button type="primary" icon={<LinkOutlined />}>去绑定账号</Button></Link></Empty>}
      </Card>

      <Card title={<Space><Title level={5} style={{ margin: 0 }}>{searchedKeyword ? `"${searchedKeyword}" 的搜索结果` : "搜索结果"}</Title><Tag>{notes.length} 篇</Tag></Space>}>
        {notes.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={searchedKeyword ? "这次搜索没有返回笔记。" : "输入关键词后，搜索结果会以笔记卡片显示在这里。"} />
        ) : (
          <>
            <Row gutter={[16, 16]}>
              {notes.map((note) => {
                const coverUrl = getCoverUrl(note);
                const originalUrl = getPreviewNoteUrl(note);
                const kind = getNoteKindLabel(note);
                return (
                  <Col xs={12} sm={8} md={6} lg={4} xl={4} key={`${note.note_id}-${note.title}`}>
                    <Card hoverable size="small" style={{ overflow: "hidden" }} onClick={() => void openDetail(note)}
                      cover={
                        <div style={{ position: "relative", background: "#262626" }}>
                          {coverUrl
                            ? <img src={coverUrl} alt={note.title || "封面"} referrerPolicy="no-referrer" style={{ width: "100%", aspectRatio: "1/1", objectFit: "cover", display: "block" }} />
                            : <div style={{ width: "100%", aspectRatio: "1/1", display: "flex", alignItems: "center", justifyContent: "center", color: "rgba(255,255,255,.2)", fontSize: 28 }}><PictureOutlined /></div>}
                          <Tag color={kind === "视频" ? "purple" : "blue"} style={{ position: "absolute", top: 8, left: 8 }} icon={kind === "视频" ? <PlayCircleOutlined /> : <PictureOutlined />}>{kind}</Tag>
                        </div>
                      }>
                      <Card.Meta title={<Text ellipsis style={{ fontSize: 13 }}>{note.title || "未命名笔记"}</Text>} description={<><Text type="secondary" style={{ fontSize: 12 }}>{note.author_name || "未知作者"}</Text>{formatNoteTime(note) && <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>{formatNoteTime(note)}</Text>}</>} />
                      <Space size={12} style={{ marginTop: 8, fontSize: 12, color: "rgba(255,255,255,.45)" }}>
                        <span><HeartOutlined /> {formatMetric(note.likes)}</span>
                        <span><StarOutlined /> {formatMetric(note.collects)}</span>
                        <span><CommentOutlined /> {formatMetric(note.comments)}</span>
                      </Space>
                      <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }} onClick={stopCardClick}>
                        <Button size="small" type={savedNoteIds.includes(note.note_id) ? "default" : "primary"} ghost={!savedNoteIds.includes(note.note_id)} icon={savedNoteIds.includes(note.note_id) ? <CheckOutlined /> : <DatabaseOutlined />} loading={savingNoteIds.includes(note.note_id)} disabled={savedNoteIds.includes(note.note_id)} onClick={() => void handleSaveNote(note)}>
                          {savedNoteIds.includes(note.note_id) ? "已保存" : "保存"}
                        </Button>
                        <Button size="small" icon={<CommentOutlined />} loading={loadingCommentNoteIds.includes(note.note_id)} onClick={() => void handlePreviewComments(note)}>
                          {commentPreviewByNoteId[note.note_id] ? "收起" : "评论"}
                        </Button>
                        {originalUrl && <Button size="small" icon={<LinkOutlined />} href={originalUrl} target="_blank" rel="noreferrer" onClick={stopCardClick}>原文</Button>}
                      </div>
                      {commentPreviewErrors[note.note_id] && <Alert message={commentPreviewErrors[note.note_id]} type="error" style={{ marginTop: 8, fontSize: 12 }} showIcon />}
                      {commentPreviewByNoteId[note.note_id] && (
                        <div style={{ marginTop: 8, borderTop: "1px solid #303030", paddingTop: 8 }} onClick={stopCardClick}>
                          {commentPreviewByNoteId[note.note_id].length === 0 ? <Text type="secondary" style={{ fontSize: 12 }}>暂无评论</Text> : null}
                          {commentPreviewByNoteId[note.note_id].filter((c) => !c.parent_comment_id).slice(0, 4).map((c) => (
                            <div key={c.comment_id} style={{ marginBottom: 6, fontSize: 12 }}>
                              <Text strong style={{ fontSize: 12 }}>{c.user_name}</Text> <Text type="secondary" style={{ fontSize: 11 }}>{c.created_at_remote} · {c.like_count} likes</Text>
                              <div style={{ color: "rgba(255,255,255,.65)" }}>{c.content}</div>
                              {getChildComments(note.note_id, c.comment_id).map((r) => (
                                <div key={r.comment_id} style={{ marginLeft: 16, marginTop: 4 }}>
                                  <Text strong style={{ fontSize: 11 }}>{r.user_name}</Text> <Text type="secondary" style={{ fontSize: 11 }}>{r.like_count} likes</Text>
                                  <div style={{ color: "rgba(255,255,255,.55)", fontSize: 12 }}>{r.content}</div>
                                </div>
                              ))}
                            </div>
                          ))}
                        </div>
                      )}
                    </Card>
                  </Col>
                );
              })}
            </Row>
            <div style={{ textAlign: "center", marginTop: 24 }}>
              <Button onClick={handleLoadMore} disabled={!hasMore || isLoadingMore} loading={isLoadingMore}>{hasMore ? "加载更多" : "没有更多了"}</Button>
            </div>
          </>
        )}
      </Card>

      <Drawer title={selectedNote?.title || "笔记详情"} open={!!selectedNote} onClose={closeDetail} width={640} styles={{ body: { background: "#1a1a1a" } }}>
        {selectedNote && (
          <div>
            {isFetchingDetail && <Spin style={{ display: "block", textAlign: "center", margin: "16px 0" }} />}
            {detailError && <Alert message={detailError} type="warning" showIcon style={{ marginBottom: 12 }} />}
            {selVideoUrl && getNoteKindLabel(selectedNote) === "视频" ? (
              <div style={{ marginBottom: 16 }}>
                <div style={{ position: "relative", background: "#262626", borderRadius: 8, overflow: "hidden" }}>
                  {selImgUrls.length ? <img src={selImgUrls[0]} alt="视频封面" referrerPolicy="no-referrer" style={{ width: "100%", maxHeight: 400, objectFit: "contain", display: "block" }} /> : <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center" }}><PlayCircleOutlined style={{ fontSize: 40, color: "rgba(255,255,255,.3)" }} /></div>}
                  <Tag color="purple" style={{ position: "absolute", top: 8, left: 8 }}><PlayCircleOutlined /> 视频封面</Tag>
                </div>
                <Button type="primary" icon={<LinkOutlined />} href={selVideoUrl} target="_blank" rel="noreferrer" style={{ marginTop: 8 }} block>打开视频</Button>
              </div>
            ) : selImgUrls.length ? (
              <div style={{ marginBottom: 16 }}>
                <div style={{ position: "relative", background: "#262626", borderRadius: 8, overflow: "hidden", textAlign: "center" }}>
                  <img src={selImgUrls[selMediaIdx]} alt="笔记图片" referrerPolicy="no-referrer" style={{ maxWidth: "100%", maxHeight: 400, objectFit: "contain" }} />
                  {selImgUrls.length > 1 && (
                    <>
                      <Button shape="circle" icon={<LeftOutlined />} size="small" style={{ position: "absolute", left: 8, top: "50%", transform: "translateY(-50%)" }} onClick={() => setDetailMediaIndex((c) => (c - 1 + selImgUrls.length) % selImgUrls.length)} />
                      <Button shape="circle" icon={<RightOutlined />} size="small" style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)" }} onClick={() => setDetailMediaIndex((c) => (c + 1) % selImgUrls.length)} />
                      <Tag style={{ position: "absolute", bottom: 8, right: 8 }}>{selMediaIdx + 1}/{selImgUrls.length}</Tag>
                    </>
                  )}
                </div>
                {selImgUrls.length > 1 && (
                  <Space size={4} style={{ marginTop: 8, overflowX: "auto" }}>
                    {selImgUrls.map((url, i) => (
                      <div key={url} onClick={() => setDetailMediaIndex(i)} style={{ width: 48, height: 48, borderRadius: 4, overflow: "hidden", cursor: "pointer", border: i === selMediaIdx ? "2px solid #1668dc" : "2px solid transparent", flexShrink: 0 }}>
                        <img src={url} alt="" referrerPolicy="no-referrer" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                      </div>
                    ))}
                  </Space>
                )}
              </div>
            ) : null}

            <Descriptions column={1} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="作者">{selectedNote.author_id ? <Typography.Link href={`https://www.xiaohongshu.com/user/profile/${selectedNote.author_id}`} target="_blank" rel="noreferrer">{selectedNote.author_name || "-"}</Typography.Link> : (selectedNote.author_name || "-")}</Descriptions.Item>
              <Descriptions.Item label="互动">赞 {formatMetric(selectedNote.likes)} · 藏 {formatMetric(selectedNote.collects)} · 评 {formatMetric(selectedNote.comments)}</Descriptions.Item>
              <Descriptions.Item label="笔记 ID">{selectedNote.note_id || "-"}</Descriptions.Item>
              {formatNoteTime(selectedNote) && <Descriptions.Item label="发布时间">{formatNoteTime(selectedNote)}</Descriptions.Item>}
              <Descriptions.Item label="作品链接"><Typography.Link href={getPreviewNoteUrl(selectedNote)} target="_blank" rel="noreferrer" style={{ fontSize: 12, wordBreak: "break-all" }}>{getPreviewNoteUrl(selectedNote) || "-"}</Typography.Link></Descriptions.Item>
            </Descriptions>

            {selectedNote.tags?.length ? <div style={{ marginBottom: 12 }}>{selectedNote.tags.map((t) => <Tag key={t} color="blue">#{t}</Tag>)}</div> : null}

            <div style={{ marginBottom: 16 }}>
              <Text strong>正文</Text>
              <Paragraph style={{ marginTop: 4, color: "rgba(255,255,255,.65)" }}>{selectedNote.content || "暂无正文。"}</Paragraph>
            </div>

            <Space wrap style={{ marginBottom: 16 }}>
              <Button
                icon={savedNoteIds.includes(selectedNote.note_id) ? <CheckOutlined /> : <DatabaseOutlined />}
                onClick={() => void handleSaveNote(selectedNote)}
                loading={savingNoteIds.includes(selectedNote.note_id)}
                disabled={savedNoteIds.includes(selectedNote.note_id)}
              >{savedNoteIds.includes(selectedNote.note_id) ? "已保存" : "保存到内容库"}</Button>
              <Button icon={<CommentOutlined />} onClick={() => void handlePreviewComments(selectedNote)}>{commentPreviewByNoteId[selectedNote.note_id] ? "收起评论" : "查看评论"}</Button>
              {getPreviewNoteUrl(selectedNote) && <Button type="primary" icon={<LinkOutlined />} href={getPreviewNoteUrl(selectedNote)} target="_blank" rel="noreferrer">打开原文</Button>}
            </Space>

            {commentPreviewErrors[selectedNote.note_id] && <Alert message={commentPreviewErrors[selectedNote.note_id]} type="error" showIcon style={{ marginBottom: 12 }} />}
            {commentPreviewByNoteId[selectedNote.note_id] && (
              <Card size="small" title="评论预览" style={{ background: "#1f1f1f" }}>
                {commentPreviewByNoteId[selectedNote.note_id].length === 0 ? <Text type="secondary">暂无评论</Text> : null}
                {commentPreviewByNoteId[selectedNote.note_id].filter((c) => !c.parent_comment_id).map((c) => (
                  <div key={c.comment_id} style={{ marginBottom: 12, paddingBottom: 8, borderBottom: "1px solid #303030" }}>
                    <Space><Text strong style={{ fontSize: 13 }}>{c.user_name}</Text><Text type="secondary" style={{ fontSize: 11 }}>{c.created_at_remote} · {c.like_count} likes</Text></Space>
                    <div style={{ color: "rgba(255,255,255,.65)", fontSize: 13, marginTop: 2 }}>{c.content}</div>
                    {getChildComments(selectedNote.note_id, c.comment_id).map((r) => (
                      <div key={r.comment_id} style={{ marginLeft: 20, marginTop: 6, paddingLeft: 8, borderLeft: "2px solid #303030" }}>
                        <Space><Text strong style={{ fontSize: 12 }}>{r.user_name}</Text><Text type="secondary" style={{ fontSize: 11 }}>{r.like_count} likes</Text></Space>
                        <div style={{ color: "rgba(255,255,255,.55)", fontSize: 12 }}>{r.content}</div>
                      </div>
                    ))}
                  </div>
                ))}
              </Card>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
