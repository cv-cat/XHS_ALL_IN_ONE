import {
  DeleteOutlined,
  EditOutlined,
  ExperimentOutlined,
  EyeOutlined,
  FileImageOutlined,
  FileTextOutlined,
  HighlightOutlined,
  InboxOutlined,
  LinkOutlined,
  PictureOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
  SendOutlined,
  VideoCameraOutlined,
} from "@ant-design/icons";
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import { SortableContext, useSortable, horizontalListSortingStrategy, arrayMove } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Divider,
  Empty,
  Form,
  Image,
  Input,
  List,
  message as antMessage,
  Modal,
  Popconfirm,
  Row,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
  Upload,
} from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { PageHeader } from "../../../components/layout/app-shell";
import {
  addDraftAsset,
  deleteDraft,
  deleteDraftAsset,
  fetchDraftAssets,
  fetchDrafts,
  fetchGeneratedImageAssets,
  fetchSavedNote,
  fetchUserImages,
  generateImageWithAi,
  reorderDraftAssets,
  sendDraftToPublish,
  updateDraft,
  uploadAssetFile,
} from "../../../lib/api";
import type { DraftAsset } from "../../../lib/api";
import { formatShanghaiTime } from "../../../lib/time";
import type { Draft, GeneratedImageAsset, SavedNote, UserImageFile } from "../../../types";

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

/* ── helpers ───────────────────────────────────────────────────────── */

function isValidUrl(s: string): boolean {
  return s.startsWith("http://") || s.startsWith("https://");
}

function getAssetTypeFromUrl(url: string): "image" | "video" {
  const lower = url.toLowerCase();
  if (/\.(mp4|mov|avi|mkv|flv|wmv)/.test(lower)) return "video";
  return "image";
}

function getAssetTypeFromFile(file: File): "image" | "video" {
  if (file.type.startsWith("video/")) return "video";
  return "image";
}

function filenameFromUrl(url: string): string {
  try {
    const pathname = new URL(url).pathname;
    const segments = pathname.split("/");
    return segments[segments.length - 1] || url;
  } catch {
    return url;
  }
}

/* ── sortable image thumbnail ─────────────────────────────────────── */

function SortableImageThumb({ asset, onEdit, onRemove, onView }: { asset: DraftAsset; onEdit: () => void; onRemove: () => void; onView: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: asset.id });
  const style: React.CSSProperties = {
    position: "relative",
    display: "inline-block",
    padding: 2,
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    cursor: "grab",
  };
  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <img
        src={asset.url || asset.local_path}
        width={60}
        height={60}
        style={{ objectFit: "cover", borderRadius: 4, display: "block", pointerEvents: "none" }}
        referrerPolicy="no-referrer"
      />
      <Button
        type="text" size="small" icon={<EditOutlined />}
        onClick={(e) => { e.stopPropagation(); onEdit(); }}
        onPointerDown={(e) => e.stopPropagation()}
        style={{
          position: "absolute", top: -6, left: -6, fontSize: 10,
          width: 18, height: 18, minWidth: 18, padding: 0,
          background: "rgba(0,0,0,.6)", borderRadius: "50%", color: "#1668dc",
        }}
      />
      <Popconfirm title="移除此图片？" onConfirm={onRemove}>
        <Button
          type="text" danger size="small" icon={<DeleteOutlined />}
          onClick={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
          style={{
            position: "absolute", top: -6, right: -6, fontSize: 10,
            width: 18, height: 18, minWidth: 18, padding: 0,
            background: "rgba(0,0,0,.6)", borderRadius: "50%",
          }}
        />
      </Popconfirm>
      <Button
        type="text" size="small" icon={<EyeOutlined />}
        onClick={(e) => { e.stopPropagation(); onView(); }}
        onPointerDown={(e) => e.stopPropagation()}
        style={{
          position: "absolute", bottom: -6, left: -6, fontSize: 10,
          width: 18, height: 18, minWidth: 18, padding: 0,
          background: "rgba(0,0,0,.6)", borderRadius: "50%", color: "#fff",
        }}
      />
    </div>
  );
}

/* ── component ─────────────────────────────────────────────────────── */

export function XhsDraftsPage() {
  const navigate = useNavigate();

  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [sourceNote, setSourceNote] = useState<SavedNote | null>(null);
  const [sourceAssets, setSourceAssets] = useState<DraftAsset[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isSendingPublish, setIsSendingPublish] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [assetUrl, setAssetUrl] = useState("");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [optimizeModalOpen, setOptimizeModalOpen] = useState(false);
  const [optimizeAssetId, setOptimizeAssetId] = useState<number | null>(null);
  const [optimizePrompt, setOptimizePrompt] = useState("");
  const [optimizeRefImages, setOptimizeRefImages] = useState<string[]>([]);
  const [optimizeResult, setOptimizeResult] = useState<string | null>(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [draftTags, setDraftTags] = useState<{id: string; name: string}[]>([]);
  const [newTagInput, setNewTagInput] = useState("");
  const [isAddingTag, setIsAddingTag] = useState(false);
  const [userImages, setUserImages] = useState<UserImageFile[]>([]);
  const [aiAssets, setAiAssets] = useState<GeneratedImageAsset[]>([]);
  const [selectedAssetUrls, setSelectedAssetUrls] = useState<string[]>([]);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [refPickerOpen, setRefPickerOpen] = useState(false);
  const [refPickerUrlInput, setRefPickerUrlInput] = useState("");

  const selectedDraft = drafts.find((d) => d.id === selectedDraftId) ?? null;
  const hasImageAssets = sourceAssets.some((a) => a.asset_type === "image");
  const hasVideoAssets = sourceAssets.some((a) => a.asset_type === "video");

  /* ── status helpers ─────────────────────────────────────────────── */

  function clearStatus() {
    setMessage(null);
    setError(null);
  }

  function selectDraft(draft: Draft) {
    setSelectedDraftId(draft.id);
    setTitle(draft.title);
    setBody(draft.body);
    setAssetUrl("");
    clearStatus();
  }

  /* ── data fetching ──────────────────────────────────────────────── */

  async function loadDrafts() {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchDrafts("xhs");
      setDrafts(result.items);
      const current = selectedDraftId
        ? result.items.find((d) => d.id === selectedDraftId)
        : result.items[0];
      if (current) {
        setSelectedDraftId(current.id);
        setTitle(current.title);
        setBody(current.body);
      } else {
        setSelectedDraftId(null);
        setTitle("");
        setBody("");
      }
    } catch {
      setError("草稿列表加载失败。");
    } finally {
      setIsLoading(false);
    }
  }

  /* ── draft CRUD ─────────────────────────────────────────────────── */

  async function handleDeleteDraft(draftId: number) {
    try {
      await deleteDraft(draftId);
      setDrafts((prev) => prev.filter((d) => d.id !== draftId));
      if (selectedDraftId === draftId) {
        setSelectedDraftId(null);
        setTitle("");
        setBody("");
        setSourceNote(null);
        setSourceAssets([]);
      }
      setMessage("草稿已删除。");
    } catch {
      setError("草稿删除失败。");
    }
  }

  async function handleSave() {
    if (!selectedDraft) {
      setError("请先选择一个草稿。");
      return;
    }
    setIsSaving(true);
    clearStatus();
    try {
      const updated = await updateDraft(selectedDraft.id, { title, body, tags: draftTags });
      setDrafts((prev) =>
        prev.map((d) => (d.id === updated.id ? updated : d))
      );
      setMessage(`草稿 #${updated.id} 已保存。`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setError(detail || "草稿保存失败。");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSendToPublish() {
    if (!selectedDraft) {
      setError("请先选择一个草稿。");
      return;
    }
    setIsSendingPublish(true);
    clearStatus();
    try {
      const saved = await updateDraft(selectedDraft.id, { title, body });
      setDrafts((prev) =>
        prev.map((d) => (d.id === saved.id ? saved : d))
      );
      const job = await sendDraftToPublish(saved.id, {
        publish_mode: "immediate",
      });
      setMessage(
        `已送入发布中心，发布任务 #${job.id}。请前往发布中心选择账号并发布。`
      );
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setError(detail || "送发布中心失败。");
    } finally {
      setIsSendingPublish(false);
    }
  }

  /* ── asset management ───────────────────────────────────────────── */

  function addAssetWithCoexistenceCheck(
    newType: "image" | "video",
    createAsset: () => DraftAsset,
  ) {
    const oppositeExists =
      newType === "image" ? hasVideoAssets : hasImageAssets;

    if (oppositeExists) {
      const msg =
        newType === "image"
          ? "图片和视频不能共存，上传图片将替换现有视频素材，是否继续？"
          : "图片和视频不能共存，上传视频将替换现有图片素材，是否继续？";

      Modal.confirm({
        title: "素材类型冲突",
        content: msg,
        okText: "确定",
        cancelText: "取消",
        onOk() {
          const oppositeType = newType === "image" ? "video" : "image";
          setSourceAssets((prev) => [
            ...prev.filter((a) => a.asset_type !== oppositeType),
            createAsset(),
          ]);
        },
      });
    } else {
      setSourceAssets((prev) => [...prev, createAsset()]);
    }
  }

  function handleFileUpload(file: File): false {
    const assetType = getAssetTypeFromFile(file);
    const draftId = selectedDraft?.id;

    (async () => {
      try {
        const uploaded = await uploadAssetFile(file);
        if (draftId) {
          const saved = await addDraftAsset(draftId, {
            asset_type: uploaded.asset_type,
            url: uploaded.download_url,
            local_path: uploaded.file_name,
          });
          addAssetWithCoexistenceCheck(assetType, () => saved);
        } else {
          addAssetWithCoexistenceCheck(assetType, () => ({
            id: -(Date.now()),
            draft_id: 0,
            asset_type: uploaded.asset_type,
            url: uploaded.download_url,
            local_path: uploaded.file_name,
            sort_order: 0,
          }));
        }
        setUploadModalOpen(false);
        antMessage.success("素材上传成功");
      } catch {
        antMessage.error("素材上传失败");
      }
    })();

    return false;
  }

  function handleUrlAdd() {
    const trimmed = assetUrl.trim();
    if (!trimmed) {
      antMessage.warning("请输入素材链接。");
      return;
    }
    if (!isValidUrl(trimmed)) {
      antMessage.error("链接格式不正确，请输入 http:// 或 https:// 开头的链接。");
      return;
    }
    const assetType = getAssetTypeFromUrl(trimmed);
    const draftId = selectedDraft?.id;

    if (draftId) {
      (async () => {
        try {
          const saved = await addDraftAsset(draftId, { asset_type: assetType, url: trimmed });
          addAssetWithCoexistenceCheck(assetType, () => saved);
          setAssetUrl("");
          setUploadModalOpen(false);
        } catch {
          antMessage.error("素材添加失败");
        }
      })();
    } else {
      addAssetWithCoexistenceCheck(assetType, () => ({
        id: -(Date.now()),
        draft_id: 0,
        asset_type: assetType,
        url: trimmed,
        local_path: "",
        sort_order: 0,
      }));
      setAssetUrl("");
      setUploadModalOpen(false);
    }
  }

  function handleRemoveAsset(assetId: number) {
    setSourceAssets((prev) => prev.filter((a) => a.id !== assetId));
    const draftId = selectedDraft?.id;
    if (draftId && assetId > 0) {
      void deleteDraftAsset(draftId, assetId).catch(() => {});
    }
  }

  function toggleAssetUrl(url: string) {
    setSelectedAssetUrls(prev => prev.includes(url) ? prev.filter(u => u !== url) : [...prev, url]);
  }

  function handleAddSelectedAssets() {
    const draftId = selectedDraft?.id;
    (async () => {
      for (const url of selectedAssetUrls) {
        if (draftId) {
          try {
            const saved = await addDraftAsset(draftId, { asset_type: "image", url });
            setSourceAssets(prev => [...prev, saved]);
          } catch { /* ignore individual failures */ }
        } else {
          setSourceAssets(prev => [...prev, {
            id: -(Date.now() + Math.random()),
            draft_id: 0,
            asset_type: "image",
            url,
            local_path: "",
            sort_order: 0,
          }]);
        }
      }
      setSelectedAssetUrls([]);
      setUploadModalOpen(false);
      antMessage.success(`已添加 ${selectedAssetUrls.length} 个图片`);
    })();
  }

  /* ── effects ────────────────────────────────────────────────────── */

  useEffect(() => {
    void loadDrafts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedDraft) {
      setSourceNote(null);
      setSourceAssets([]);
      setDraftTags([]);
      return;
    }
    let cancelled = false;
    (async () => {
      // Load tags from draft itself
      if (!cancelled) {
        const tags = selectedDraft.tags;
        if (Array.isArray(tags)) {
          setDraftTags(tags.map((t) => ({ id: t.id || "", name: t.name || "" })));
        } else {
          setDraftTags([]);
        }
      }

      try {
        const assetsResult = await fetchDraftAssets(selectedDraft.id);
        if (!cancelled) {
          setSourceAssets(assetsResult.items);
        }
      } catch {
        if (!cancelled) setSourceAssets([]);
      }

      if (selectedDraft.source_note_id) {
        try {
          const note = await fetchSavedNote(selectedDraft.source_note_id);
          if (!cancelled) {
            setSourceNote(note);
          }
        } catch {
          if (!cancelled) { setSourceNote(null); }
        }
      } else {
        if (!cancelled) { setSourceNote(null); }
      }
    })();
    return () => { cancelled = true; };
  }, [selectedDraft?.id, selectedDraft?.source_note_id]);

  useEffect(() => {
    if (uploadModalOpen) {
      void fetchUserImages().then(r => setUserImages(r.items)).catch(() => {});
      void fetchGeneratedImageAssets().then(r => setAiAssets(r.items)).catch(() => {});
      setSelectedAssetUrls([]);
    }
  }, [uploadModalOpen]);

  useEffect(() => {
    if (refPickerOpen) {
      void fetchUserImages().then((r) => setUserImages(r.items)).catch(() => {});
      void fetchGeneratedImageAssets().then((r) => setAiAssets(r.items)).catch(() => {});
    }
  }, [refPickerOpen]);

  useEffect(() => {
    setOptimizeAssetId(null);
    setOptimizeModalOpen(false);
  }, [sourceAssets, selectedDraftId]);

  /* ── render helpers ─────────────────────────────────────────────── */

  const imageAssets = sourceAssets.filter((a) => a.asset_type === "image");
  const videoAssets = sourceAssets.filter((a) => a.asset_type === "video");

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setSourceAssets((prev) => {
      const images = prev.filter((a) => a.asset_type === "image");
      const others = prev.filter((a) => a.asset_type !== "image");
      const oldIdx = images.findIndex((a) => a.id === Number(active.id));
      const newIdx = images.findIndex((a) => a.id === Number(over.id));
      if (oldIdx < 0 || newIdx < 0) return prev;
      const reorderedImages = arrayMove(images, oldIdx, newIdx);
      const result = [...reorderedImages, ...others];
      const draftId = selectedDraft?.id;
      if (draftId) {
        const ids = reorderedImages.filter((a) => a.id > 0).map((a) => a.id);
        void reorderDraftAssets(draftId, ids).catch((err) => { console.error("reorder failed", err); });
      }
      return result;
    });
  }

  function renderImageAssets() {
    if (imageAssets.length === 0) return null;
    return (
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            <FileImageOutlined /> 图片素材 ({imageAssets.length}) — 拖拽调整顺序
          </Text>
        </div>
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={imageAssets.map((a) => a.id)} strategy={horizontalListSortingStrategy}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
              {imageAssets.map((asset) => (
                <SortableImageThumb
                  key={asset.id}
                  asset={asset}
                  onEdit={() => { setOptimizeAssetId(asset.id); setOptimizeModalOpen(true); }}
                  onRemove={() => handleRemoveAsset(asset.id)}
                  onView={() => setPreviewImage(asset.url || asset.local_path)}
                />
              ))}
              <div
                onClick={() => setUploadModalOpen(true)}
                style={{
                  width: 60, height: 60, borderRadius: 4, border: "1px dashed #434343",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  cursor: "pointer", background: "rgba(255,255,255,0.04)",
                }}
              >
                <PlusOutlined style={{ fontSize: 20, color: "#8c8c8c" }} />
              </div>
            </div>
          </SortableContext>
        </DndContext>
      </div>
    );
  }

  function renderVideoAssets() {
    if (videoAssets.length === 0) return null;
    return (
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            <VideoCameraOutlined /> 视频素材 ({videoAssets.length})
          </Text>
        </div>
        <Space direction="vertical" size={4} style={{ width: "100%" }}>
          {videoAssets.map((asset) => (
            <div
              key={asset.id}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "4px 8px", borderRadius: 4,
                background: "rgba(255,255,255,0.04)",
              }}
            >
              <PlayCircleOutlined style={{ fontSize: 18, color: "#1668dc" }} />
              <Text ellipsis style={{ flex: 1, fontSize: 13 }} title={asset.url || asset.local_path}>
                {asset.local_path ? asset.local_path : filenameFromUrl(asset.url)}
              </Text>
              {asset.url && (
                <a href={asset.url} target="_blank" rel="noopener noreferrer">
                  <Button type="link" size="small" icon={<LinkOutlined />}>查看</Button>
                </a>
              )}
              <Button
                type="text" size="small" icon={<EditOutlined />}
                onClick={() => { setOptimizeAssetId(asset.id); setOptimizeModalOpen(true); }}
                style={{ color: "#1668dc" }}
              />
              <Popconfirm title="移除此视频？" onConfirm={() => handleRemoveAsset(asset.id)}>
                <Button type="text" danger size="small" icon={<DeleteOutlined />} />
              </Popconfirm>
            </div>
          ))}
          <div
            onClick={() => setUploadModalOpen(true)}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              padding: "4px 8px", borderRadius: 4, border: "1px dashed #434343",
              cursor: "pointer", background: "rgba(255,255,255,0.04)",
            }}
          >
            <PlusOutlined style={{ fontSize: 16, color: "#8c8c8c" }} />
          </div>
        </Space>
      </div>
    );
  }

  /* ── main render ────────────────────────────────────────────────── */

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <PageHeader
        eyebrow="XHS Drafts"
        title="草稿库"
        description="管理所有 AI 改写草稿，编辑内容和素材后送入发布中心。"
        action={
          <Button
            icon={<ReloadOutlined />}
            onClick={loadDrafts}
            loading={isLoading}
          >
            刷新
          </Button>
        }
      />

      {error && (
        <Alert
          type="error"
          message={error}
          showIcon
          closable
          onClose={() => setError(null)}
        />
      )}
      {message && (
        <Alert
          type="success"
          message={message}
          showIcon
          closable
          onClose={() => setMessage(null)}
        />
      )}

      <Row gutter={16}>
        {/* Left column: draft list */}
        <Col xs={24} lg={8}>
          <Card
            title={
              <Space>
                <Text strong>草稿列表</Text>
                <Badge
                  count={drafts.length}
                  style={{ backgroundColor: "#1668dc" }}
                />
              </Space>
            }
            styles={{ body: { padding: 0 } }}
          >
            {isLoading ? (
              <div style={{ textAlign: "center", padding: 32 }}>
                <Spin />
                <Paragraph type="secondary" style={{ marginTop: 12 }}>
                  正在加载草稿...
                </Paragraph>
              </div>
            ) : drafts.length === 0 ? (
              <Empty
                image={
                  <FileTextOutlined
                    style={{ fontSize: 40, color: "#8c8c8c" }}
                  />
                }
                imageStyle={{ height: 56 }}
                description={
                  <Paragraph type="secondary">
                    还没有草稿，请从内容库或 AI 工坊创建。
                  </Paragraph>
                }
                style={{ padding: 24 }}
              />
            ) : (
              <List
                dataSource={drafts}
                renderItem={(draft) => {
                  const isActive = draft.id === selectedDraftId;
                  return (
                    <List.Item
                      onClick={() => selectDraft(draft)}
                      style={{
                        cursor: "pointer",
                        padding: "10px 16px",
                        background: isActive ? "#1668dc10" : "transparent",
                        borderLeft: isActive
                          ? "2px solid #1668dc"
                          : "2px solid transparent",
                        transition: "all 0.15s",
                        margin: 0,
                      }}
                    >
                      <div
                        style={{
                          minWidth: 0,
                          width: "100%",
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <Text
                            ellipsis
                            style={{
                              display: "block",
                              fontSize: 13,
                              fontWeight: isActive ? 600 : 400,
                            }}
                          >
                            {draft.title || "未命名草稿"}
                          </Text>
                          <Text
                            type="secondary"
                            style={{ fontSize: 11, display: "block" }}
                          >
                            {formatShanghaiTime(draft.created_at)}
                          </Text>
                          {draft.source_note_id && (
                            <Tag
                              color="blue"
                              style={{ fontSize: 10, marginTop: 2 }}
                            >
                              来源笔记
                            </Tag>
                          )}
                        </div>
                        <Popconfirm
                          title="删除此草稿？"
                          onConfirm={(e) => {
                            e?.stopPropagation();
                            void handleDeleteDraft(draft.id);
                          }}
                          onCancel={(e) => e?.stopPropagation()}
                        >
                          <Button
                            type="text"
                            danger
                            size="small"
                            icon={<DeleteOutlined />}
                            onClick={(e) => e.stopPropagation()}
                            style={{ flexShrink: 0 }}
                          />
                        </Popconfirm>
                      </div>
                    </List.Item>
                  );
                }}
                style={{
                  maxHeight: "calc(100vh - 340px)",
                  overflowY: "auto",
                }}
              />
            )}
          </Card>
        </Col>

        {/* Right column: detail editor */}
        <Col xs={24} lg={16}>
          {!selectedDraft ? (
            <Card>
              <Empty description="请从左侧选择一个草稿" />
            </Card>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Source note info card */}
              <Card
                title={
                  <Space>
                    <PictureOutlined />
                    <span>草稿素材</span>
                  </Space>
                }
                size="small"
                extra={
                  sourceNote ? (
                    <a
                      href={`https://www.xiaohongshu.com/explore/${sourceNote.note_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Button
                        type="link"
                        size="small"
                        icon={<LinkOutlined />}
                      >
                        查看原文
                      </Button>
                    </a>
                  ) : undefined
                }
              >
                {/* Source note info (when available) */}
                {sourceNote && (
                  <div style={{ marginBottom: 16 }}>
                    <Text strong style={{ display: "block", marginBottom: 4 }}>
                      {sourceNote.title}
                    </Text>
                    <Paragraph
                      ellipsis={{ rows: 3, expandable: true, symbol: "展开" }}
                      type="secondary"
                      style={{ marginBottom: 8, fontSize: 13 }}
                    >
                      {sourceNote.content}
                    </Paragraph>
                    <Space size={4}>
                      <Tag color={hasVideoAssets ? "purple" : "blue"}>
                        {hasVideoAssets ? "视频" : "图文"}
                      </Tag>
                    </Space>
                  </div>
                )}

                {/* Image assets display */}
                {renderImageAssets()}

                {/* Video assets display */}
                {renderVideoAssets()}

                {/* Empty state when no assets */}
                {imageAssets.length === 0 && videoAssets.length === 0 && (
                  <div onClick={() => setUploadModalOpen(true)} style={{
                    width: "100%", height: 80, borderRadius: 8, border: "1px dashed #434343",
                    display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column",
                    cursor: "pointer", background: "rgba(255,255,255,0.04)", gap: 4,
                  }}>
                    <PlusOutlined style={{ fontSize: 24, color: "#8c8c8c" }} />
                    <Text type="secondary" style={{ fontSize: 12 }}>添加素材</Text>
                  </div>
                )}
              </Card>

              {/* Optimize modal */}
              <Modal
                title="素材优化"
                open={optimizeModalOpen}
                onCancel={() => { setOptimizeModalOpen(false); setOptimizeAssetId(null); setOptimizePrompt(""); setOptimizeRefImages([]); setOptimizeResult(null); }}
                footer={null}
                width={520}
              >
                {(() => {
                  const asset = sourceAssets.find((a) => a.id === optimizeAssetId);
                  if (!asset) return <Text type="secondary">素材不存在</Text>;
                  const isImage = asset.asset_type === "image";
                  return (
                    <div>
                      <Row gutter={16} style={{ marginBottom: 16 }}>
                        <Col span={12}>
                          <div style={{ padding: 8, background: "rgba(255,255,255,0.04)", borderRadius: 8, textAlign: "center" }}>
                            <Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 4 }}>当前素材</Text>
                            {isImage ? (
                              <img src={asset.url || asset.local_path} style={{ width: 140, height: 140, objectFit: "cover", borderRadius: 6 }} referrerPolicy="no-referrer" />
                            ) : (
                              <div style={{ height: 140, display: "flex", alignItems: "center", justifyContent: "center" }}>
                                <Space direction="vertical" align="center"><PlayCircleOutlined style={{ fontSize: 32, color: "#1668dc" }} /><Text style={{ fontSize: 12 }}>视频</Text></Space>
                              </div>
                            )}
                          </div>
                        </Col>
                        <Col span={12}>
                          <div style={{ padding: 8, background: "rgba(255,255,255,0.04)", borderRadius: 8, textAlign: "center", height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                            <Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 4 }}>优化后预览</Text>
                            {optimizeResult ? (
                              <img src={optimizeResult} style={{ width: 140, height: 140, objectFit: "cover", borderRadius: 6 }} referrerPolicy="no-referrer" />
                            ) : (
                              <div style={{ width: 140, height: 140, border: "1px dashed #434343", borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center" }}>
                                <Text type="secondary" style={{ fontSize: 12 }}>{isOptimizing ? "生成中..." : "等待生成"}</Text>
                              </div>
                            )}
                          </div>
                        </Col>
                      </Row>

                      {isImage ? (
                        <div>
                          <div style={{ marginBottom: 8 }}>
                            <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>额外参考图（可选）</Text>
                            <Space size={8} wrap>
                              {optimizeRefImages.map((url, idx) => (
                                <div key={idx} style={{ position: "relative", width: 40, height: 40, borderRadius: 4, overflow: "hidden", border: "1px solid #333" }}>
                                  <img src={url} style={{ width: "100%", height: "100%", objectFit: "cover" }} referrerPolicy="no-referrer" />
                                  <Button type="text" danger size="small" icon={<DeleteOutlined />}
                                    onClick={() => setOptimizeRefImages((prev) => prev.filter((_, i) => i !== idx))}
                                    style={{ position: "absolute", top: -4, right: -4, fontSize: 8, width: 14, height: 14, minWidth: 14, padding: 0, background: "rgba(0,0,0,.6)", borderRadius: "50%" }}
                                  />
                                </div>
                              ))}
                              <div
                                onClick={() => setRefPickerOpen(true)}
                                style={{ width: 40, height: 40, borderRadius: 4, border: "1px dashed #434343", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", background: "rgba(255,255,255,0.04)" }}
                              >
                                <PlusOutlined style={{ fontSize: 14, color: "#8c8c8c" }} />
                              </div>
                            </Space>
                          </div>
                          <Input.TextArea
                            value={optimizePrompt}
                            onChange={(e) => setOptimizePrompt(e.target.value)}
                            placeholder="描述你想要的润色效果，如：提升画面清晰度和色彩饱和度，增加小红书风格滤镜..."
                            rows={3}
                            style={{ marginBottom: 12 }}
                            disabled={isOptimizing}
                          />
                          <Space direction="vertical" style={{ width: "100%" }} size={8}>
                            <Button
                              block
                              type="primary"
                              icon={<HighlightOutlined />}
                              loading={isOptimizing}
                              onClick={async () => {
                                if (!optimizePrompt.trim()) { antMessage.warning("请输入润色提示词"); return; }
                                setIsOptimizing(true); setOptimizeResult(null);
                                try {
                                  const result = await generateImageWithAi({
                                    prompt: optimizePrompt.trim(),
                                    reference_images: [asset.url || asset.local_path, ...optimizeRefImages],
                                    save_to_assets: false,
                                  });
                                  setOptimizeResult(result.url);
                                  antMessage.success("图片润色完成");
                                } catch {
                                  antMessage.error("图片润色失败，请确认已配置图片生成模型");
                                } finally { setIsOptimizing(false); }
                              }}
                            >
                              图片润色
                            </Button>
                            {optimizeResult && (
                              <Button
                                block
                                onClick={() => {
                                  setSourceAssets((prev) => prev.map((a) => a.id === optimizeAssetId ? { ...a, url: optimizeResult!, local_path: "" } : a));
                                  const draftId = selectedDraft?.id;
                                  if (draftId && optimizeAssetId && optimizeAssetId > 0) {
                                    void addDraftAsset(draftId, { asset_type: "image", url: optimizeResult! }).then((saved) => {
                                      void deleteDraftAsset(draftId, optimizeAssetId!).catch(() => {});
                                      setSourceAssets((prev) => prev.map((a) => a.id === optimizeAssetId ? saved : a));
                                    }).catch(() => {});
                                  }
                                  setOptimizeModalOpen(false); setOptimizeAssetId(null); setOptimizePrompt(""); setOptimizeRefImages([]); setOptimizeResult(null);
                                  antMessage.success("已替换为润色后的图片");
                                }}
                              >
                                替换当前素材
                              </Button>
                            )}
                          </Space>
                        </div>
                      ) : (
                        <Button block icon={<VideoCameraOutlined />} disabled>
                          视频润色（即将上线）
                        </Button>
                      )}
                    </div>
                  );
                })()}
              </Modal>

              {/* Reference image picker modal */}
              <Modal title="选择参考图" open={refPickerOpen} onCancel={() => { setRefPickerOpen(false); setRefPickerUrlInput(""); }} footer={null} width={560}>
                <Tabs size="small" items={[
                  {
                    key: "user",
                    label: "普通图片资产",
                    children: userImages.length === 0 ? <Text type="secondary">暂无</Text> : (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, maxHeight: 200, overflowY: "auto" }}>
                        {userImages.map((img) => (
                          <div key={img.file_name} onClick={() => { setOptimizeRefImages((prev) => [...prev, img.url]); setRefPickerOpen(false); }}
                            style={{ width: 60, height: 60, borderRadius: 4, overflow: "hidden", cursor: "pointer", border: "2px solid transparent" }}>
                            <img src={img.url} style={{ width: "100%", height: "100%", objectFit: "cover" }} referrerPolicy="no-referrer" />
                          </div>
                        ))}
                      </div>
                    ),
                  },
                  {
                    key: "ai",
                    label: "AI 图片资产",
                    children: aiAssets.length === 0 ? <Text type="secondary">暂无</Text> : (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, maxHeight: 200, overflowY: "auto" }}>
                        {aiAssets.filter((a) => a.file_path.startsWith("http")).map((asset) => (
                          <div key={asset.id} onClick={() => { setOptimizeRefImages((prev) => [...prev, asset.file_path]); setRefPickerOpen(false); }}
                            style={{ width: 60, height: 60, borderRadius: 4, overflow: "hidden", cursor: "pointer", border: "2px solid transparent" }}>
                            <img src={asset.file_path} style={{ width: "100%", height: "100%", objectFit: "cover" }} referrerPolicy="no-referrer" />
                          </div>
                        ))}
                      </div>
                    ),
                  },
                  {
                    key: "url",
                    label: "URL",
                    children: (
                      <Space.Compact style={{ width: "100%" }}>
                        <Input placeholder="粘贴图片 URL" value={refPickerUrlInput} onChange={(e) => setRefPickerUrlInput(e.target.value)} />
                        <Button type="primary" onClick={() => {
                          const v = refPickerUrlInput.trim();
                          if (v && (v.startsWith("http://") || v.startsWith("https://") || v.startsWith("/api/"))) {
                            setOptimizeRefImages((prev) => [...prev, v]);
                            setRefPickerUrlInput("");
                            setRefPickerOpen(false);
                          }
                        }}>添加</Button>
                      </Space.Compact>
                    ),
                  },
                ]} />
              </Modal>

              {/* Upload modal */}
              <Modal title="上传素材" open={uploadModalOpen} onCancel={() => setUploadModalOpen(false)} footer={null} width={480}>
                <Upload.Dragger
                  accept=".jpg,.jpeg,.png,.gif,.webp,.mp4,.mov,.avi,.mkv"
                  multiple
                  showUploadList={false}
                  beforeUpload={(file) => handleFileUpload(file as File)}
                  style={{ marginBottom: 12 }}
                >
                  <p className="ant-upload-drag-icon">
                    <InboxOutlined />
                  </p>
                  <p className="ant-upload-text" style={{ fontSize: 13 }}>
                    点击或拖拽文件上传
                  </p>
                  <p className="ant-upload-hint" style={{ fontSize: 12 }}>
                    支持 JPG / PNG / GIF / WEBP / MP4 / MOV
                  </p>
                </Upload.Dragger>
                <div style={{ marginTop: 12 }}>
                  <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: "block" }}>或粘贴链接</Text>
                  <Space.Compact style={{ width: "100%" }}>
                    <Input
                      placeholder="粘贴图片或视频链接"
                      prefix={<LinkOutlined />}
                      value={assetUrl}
                      onChange={(e) => setAssetUrl(e.target.value)}
                      onPressEnter={handleUrlAdd}
                    />
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={handleUrlAdd}
                    >
                      添加
                    </Button>
                  </Space.Compact>
                </div>

                <Divider style={{ margin: "12px 0" }}>或从图片资产选择</Divider>

                <Tabs size="small" items={[
                  {
                    key: "user",
                    label: "普通图片资产",
                    children: userImages.length === 0 ? (
                      <Text type="secondary" style={{ fontSize: 12 }}>暂无普通图片资产，请先在图片工坊上传</Text>
                    ) : (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, maxHeight: 200, overflowY: "auto" }}>
                        {userImages.map((img) => (
                          <div key={img.file_name} onClick={() => toggleAssetUrl(img.url)}
                            style={{
                              width: 60, height: 60, borderRadius: 4, overflow: "hidden", cursor: "pointer",
                              border: selectedAssetUrls.includes(img.url) ? "2px solid #1668dc" : "2px solid transparent",
                            }}>
                            <img src={img.url} style={{ width: "100%", height: "100%", objectFit: "cover" }} referrerPolicy="no-referrer" />
                          </div>
                        ))}
                      </div>
                    ),
                  },
                  {
                    key: "ai",
                    label: "AI 图片资产",
                    children: aiAssets.length === 0 ? (
                      <Text type="secondary" style={{ fontSize: 12 }}>暂无 AI 图片资产，请先在图片工坊生成</Text>
                    ) : (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, maxHeight: 200, overflowY: "auto" }}>
                        {aiAssets.filter(a => a.file_path.startsWith("http")).map((asset) => (
                          <div key={asset.id} onClick={() => toggleAssetUrl(asset.file_path)}
                            style={{
                              width: 60, height: 60, borderRadius: 4, overflow: "hidden", cursor: "pointer",
                              border: selectedAssetUrls.includes(asset.file_path) ? "2px solid #1668dc" : "2px solid transparent",
                            }}>
                            <img src={asset.file_path} style={{ width: "100%", height: "100%", objectFit: "cover" }} referrerPolicy="no-referrer" />
                          </div>
                        ))}
                      </div>
                    ),
                  },
                ]} />

                {selectedAssetUrls.length > 0 && (
                  <Button type="primary" block style={{ marginTop: 12 }} onClick={handleAddSelectedAssets}>
                    添加选中的 {selectedAssetUrls.length} 个图片
                  </Button>
                )}
              </Modal>

              {/* Editor card */}
              <Card title="编辑器">
                <Form layout="vertical">
                  <Form.Item label="标题" style={{ marginBottom: 16 }}>
                    <Input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="草稿标题"
                      size="large"
                    />
                  </Form.Item>
                  <Form.Item label="正文" style={{ marginBottom: 16 }}>
                    <TextArea
                      value={body}
                      onChange={(e) => setBody(e.target.value)}
                      placeholder="草稿正文内容"
                      rows={12}
                      style={{ fontFamily: "monospace" }}
                    />
                  </Form.Item>
                  <Form.Item label="标签" style={{ marginBottom: 16 }}>
                    <Space size={[4, 8]} wrap>
                      {draftTags.map((tag) => (
                        <Tag
                          key={tag.id || tag.name}
                          closable
                          onClose={() => setDraftTags((prev) => prev.filter((t) => t.name !== tag.name))}
                          color="blue"
                        >
                          #{tag.name}
                        </Tag>
                      ))}
                      {isAddingTag ? (
                        <Input
                          size="small"
                          style={{ width: 120 }}
                          value={newTagInput}
                          onChange={(e) => setNewTagInput(e.target.value)}
                          onPressEnter={() => {
                            const name = newTagInput.trim();
                            if (name && !draftTags.some((t) => t.name === name)) {
                              setDraftTags((prev) => [...prev, { id: "", name }]);
                            }
                            setNewTagInput("");
                            setIsAddingTag(false);
                          }}
                          onBlur={() => {
                            const name = newTagInput.trim();
                            if (name && !draftTags.some((t) => t.name === name)) {
                              setDraftTags((prev) => [...prev, { id: "", name }]);
                            }
                            setNewTagInput("");
                            setIsAddingTag(false);
                          }}
                          autoFocus
                          placeholder="输入标签"
                        />
                      ) : (
                        <Tag
                          style={{ cursor: "pointer", borderStyle: "dashed" }}
                          onClick={() => setIsAddingTag(true)}
                        >
                          + 添加标签
                        </Tag>
                      )}
                    </Space>
                  </Form.Item>
                  <Button
                    type="primary"
                    icon={<SaveOutlined />}
                    onClick={handleSave}
                    loading={isSaving}
                    disabled={!selectedDraft}
                  >
                    保存
                  </Button>
                </Form>
              </Card>

              {/* Action buttons */}
              <Card size="small">
                <Space>
                  <Button
                    type="primary"
                    icon={<SendOutlined />}
                    onClick={handleSendToPublish}
                    loading={isSendingPublish}
                    disabled={!selectedDraft}
                  >
                    送入发布中心
                  </Button>
                  <Button
                    icon={<ExperimentOutlined />}
                    onClick={() => navigate("/platforms/xhs/rewrite")}
                  >
                    AI 改写
                  </Button>
                </Space>
              </Card>
            </div>
          )}
        </Col>
      </Row>

      {previewImage && (
        <Image
          src={previewImage}
          style={{ display: "none" }}
          preview={{ visible: true, onVisibleChange: (v) => { if (!v) setPreviewImage(null); } }}
        />
      )}
    </div>
  );
}
