import {
  DeleteOutlined,
  FileImageOutlined,
  InboxOutlined,
  LinkOutlined,
  PictureOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  StarOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Empty,
  Image,
  Input,
  Modal,
  Row,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
  Upload,
} from "antd";
import { useEffect, useState } from "react";

import { PageHeader } from "../../../components/layout/app-shell";
import {
  deleteGeneratedImageAsset,
  deleteUserImage,
  describeImageWithAi,
  fetchGeneratedImageAssets,
  fetchUserImages,
  generateImageWithAi,
  uploadAssetFile,
} from "../../../lib/api";
import { formatShanghaiTime } from "../../../lib/time";
import type { GeneratedImageAsset, UserImageFile } from "../../../types";

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

function isRenderableImage(value: string): boolean {
  return (
    value.startsWith("http://") ||
    value.startsWith("https://") ||
    value.startsWith("data:image/") ||
    value.startsWith("/api/")
  );
}

export function XhsImageStudioPage() {
  const [assets, setAssets] = useState<GeneratedImageAsset[]>([]);
  const [userImages, setUserImages] = useState<UserImageFile[]>([]);
  const [prompt, setPrompt] = useState("");
  const [referenceImages, setReferenceImages] = useState<string[]>([]);
  const [imageUrl, setImageUrl] = useState("");
  const [description, setDescription] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDescribing, setIsDescribing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refPickerOpen, setRefPickerOpen] = useState(false);
  const [saveToAssets, setSaveToAssets] = useState(true);
  const [generatedPreview, setGeneratedPreview] = useState<string | null>(null);

  // For the reference picker modal: which callback mode
  const [pickerMode, setPickerMode] = useState<"reference" | "describe">(
    "reference",
  );
  const [pickerUrlInput, setPickerUrlInput] = useState("");

  async function loadAssets() {
    setIsLoading(true);
    setError(null);
    try {
      const [aiResult, userResult] = await Promise.all([
        fetchGeneratedImageAssets(),
        fetchUserImages(),
      ]);
      setAssets(aiResult.items);
      setUserImages(userResult.items);
    } catch {
      setError("图片资产加载失败。");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleGenerate() {
    if (!prompt.trim()) {
      setError("请填写提示词。");
      return;
    }
    setIsGenerating(true);
    setError(null);
    setMessage(null);
    setGeneratedPreview(null);
    try {
      const result = await generateImageWithAi({
        prompt: prompt.trim(),
        reference_images:
          referenceImages.length > 0 ? referenceImages : undefined,
        save_to_assets: saveToAssets,
      });
      setGeneratedPreview(result.url);
      if (result.asset) {
        setAssets((prev) => [result.asset!, ...prev]);
      }
      setMessage("图片生成成功。");
    } catch {
      setError("AI 图片生成失败，请确认已配置图片生成模型。");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleDescribeImage() {
    if (!imageUrl.trim()) {
      setError("请先填写图片 URL。");
      return;
    }
    setIsDescribing(true);
    setError(null);
    setMessage(null);
    try {
      const result = await describeImageWithAi({
        image_url: imageUrl.trim(),
        instruction: "提炼这张图片适合小红书发布的卖点、风格和标题方向。",
      });
      setDescription(result.text);
      setMessage("图片描述已生成。");
    } catch {
      setError("图片描述失败，请确认已配置支持视觉理解的图片模型。");
    } finally {
      setIsDescribing(false);
    }
  }

  function openRefPicker(mode: "reference" | "describe") {
    setPickerMode(mode);
    setPickerUrlInput("");
    setRefPickerOpen(true);
  }

  function handlePickerSelect(url: string) {
    if (pickerMode === "reference") {
      setReferenceImages((prev) =>
        prev.includes(url) ? prev : [...prev, url],
      );
    } else {
      setImageUrl(url);
    }
    setRefPickerOpen(false);
  }

  function handlePickerUrlAdd() {
    const trimmed = pickerUrlInput.trim();
    if (!trimmed) return;
    handlePickerSelect(trimmed);
  }

  async function handleUploadFile(file: File) {
    try {
      const uploaded = await uploadAssetFile(file);
      const newItem: UserImageFile = {
        file_name: uploaded.file_name,
        url: uploaded.download_url,
        size: uploaded.size,
      };
      setUserImages((prev) => [newItem, ...prev]);
    } catch {
      setError("文件上传失败。");
    }
    return false; // prevent antd auto-upload
  }

  useEffect(() => {
    void loadAssets();
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="XHS Image Studio"
        title="图片工坊"
        description="AI 图片生成、图片描述、沉淀图片资产，赋能小红书内容创作。"
        action={
          <Button
            icon={<ReloadOutlined />}
            onClick={loadAssets}
            loading={isLoading}
          >
            刷新资产
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
          style={{ marginBottom: 16 }}
        />
      )}
      {message && (
        <Alert
          type="success"
          message={message}
          showIcon
          closable
          onClose={() => setMessage(null)}
          style={{ marginBottom: 16 }}
        />
      )}

      {/* ---- Top Row: Two tool cards ---- */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {/* Left Card: AI Image Generation */}
        <Col xs={24} md={14}>
          <Card
            title={
              <Space>
                <StarOutlined /> AI 图片生成
              </Space>
            }
            extra={
              <Text type="secondary" style={{ fontSize: 11 }}>
                需配置图片生成模型（如 gpt-image-2、豆包 Seedream）
              </Text>
            }
          >
            <TextArea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="充满活力的特写编辑肖像，模特眼神犀利，头戴雕塑感帽子，色彩拼接丰富，具有 Vogue 杂志封面的美学风格..."
              rows={4}
              disabled={isGenerating}
              style={{ marginBottom: 12 }}
            />

            {/* Reference images */}
            <div style={{ marginBottom: 12 }}>
              <Text
                type="secondary"
                style={{ fontSize: 12, marginBottom: 6, display: "block" }}
              >
                参考图
              </Text>
              <Space size={8} wrap>
                {referenceImages.map((url, idx) => (
                  <div
                    key={idx}
                    style={{
                      position: "relative",
                      width: 60,
                      height: 60,
                      borderRadius: 4,
                      overflow: "hidden",
                      border: "1px solid #333",
                    }}
                  >
                    {isRenderableImage(url) ? (
                      <img
                        src={url}
                        alt={`ref-${idx}`}
                        style={{
                          width: 60,
                          height: 60,
                          objectFit: "cover",
                        }}
                      />
                    ) : (
                      <div
                        style={{
                          width: 60,
                          height: 60,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          background: "#1a1a1a",
                        }}
                      >
                        <PictureOutlined style={{ fontSize: 20, color: "#666" }} />
                      </div>
                    )}
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() =>
                        setReferenceImages((prev) =>
                          prev.filter((_, i) => i !== idx),
                        )
                      }
                      style={{
                        position: "absolute",
                        top: 0,
                        right: 0,
                        width: 18,
                        height: 18,
                        padding: 0,
                        minWidth: 18,
                        borderRadius: "0 4px 0 4px",
                        background: "rgba(0,0,0,0.6)",
                      }}
                    />
                  </div>
                ))}
                {/* Add placeholder */}
                <div
                  onClick={() => openRefPicker("reference")}
                  style={{
                    width: 60,
                    height: 60,
                    borderRadius: 4,
                    border: "1px dashed #444",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    background: "#1a1a1a",
                  }}
                >
                  <PlusOutlined style={{ fontSize: 20, color: "#666" }} />
                </div>
              </Space>
            </div>

            {/* Controls row */}
            <Row
              justify="space-between"
              align="middle"
              style={{ marginBottom: 12 }}
            >
              <Col>
                <Checkbox
                  checked={saveToAssets}
                  onChange={(e) => setSaveToAssets(e.target.checked)}
                >
                  保存到 AI 图片资产
                </Checkbox>
              </Col>
              <Col>
                <Space>
                  <Button
                    onClick={() => { setPrompt(""); setReferenceImages([]); setGeneratedPreview(null); setSaveToAssets(true); }}
                    disabled={isGenerating}
                  >
                    重置
                  </Button>
                  <Button
                    type="primary"
                    icon={<RobotOutlined />}
                    onClick={handleGenerate}
                    loading={isGenerating}
                  >
                    生成
                  </Button>
                </Space>
              </Col>
            </Row>

            {/* Generated result */}
            {generatedPreview && (
              <div style={{ marginTop: 8 }}>
                <Text
                  type="secondary"
                  style={{ fontSize: 12, marginBottom: 6, display: "block" }}
                >
                  生成结果
                </Text>
                <div
                  style={{
                    background: "#1a1a1a",
                    borderRadius: 6,
                    padding: 8,
                    textAlign: "center",
                  }}
                >
                  <Image
                    src={generatedPreview}
                    alt="generated"
                    style={{ maxHeight: 240, objectFit: "contain" }}
                  />
                  {!saveToAssets && (
                    <Button
                      size="small"
                      type="link"
                      onClick={() => {
                        // Re-generate with save flag
                        setSaveToAssets(true);
                        setMessage("下次生成将自动保存到 AI 资产。");
                      }}
                      style={{ marginTop: 8 }}
                    >
                      保存到 AI 资产
                    </Button>
                  )}
                </div>
              </div>
            )}
          </Card>
        </Col>

        {/* Right Card: Image Description */}
        <Col xs={24} md={10}>
          <Card
            title={
              <Space>
                <FileImageOutlined /> 图片描述
              </Space>
            }
            extra={
              <Text type="secondary" style={{ fontSize: 11 }}>
                需配置多模态模型（如 GPT-4o）
              </Text>
            }
          >
            <Space.Compact style={{ width: "100%", marginBottom: 12 }}>
              <Input
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                placeholder="图片 URL"
                disabled={isGenerating}
              />
              <Button
                icon={<PictureOutlined />}
                onClick={() => openRefPicker("describe")}
              >
                从资产选择
              </Button>
            </Space.Compact>
            <Button
              onClick={handleDescribeImage}
              loading={isDescribing}
              block
              style={{ marginBottom: 12 }}
            >
              生成描述
            </Button>
            {description && (
              <Paragraph
                style={{
                  background: "#262626",
                  padding: 12,
                  borderRadius: 6,
                  fontSize: 13,
                  margin: 0,
                }}
              >
                {description}
              </Paragraph>
            )}
          </Card>
        </Col>
      </Row>

      {/* ---- Bottom: Tabs ---- */}
      <Tabs
        defaultActiveKey="ai_assets"
        items={[
          {
            key: "ai_assets",
            label: (
              <Space>
                <StarOutlined /> AI 图片资产
              </Space>
            ),
            children: (
              <>
                {isLoading ? (
                  <div style={{ textAlign: "center", padding: 48 }}>
                    <Spin tip="正在加载 AI 图片资产..." />
                  </div>
                ) : assets.length === 0 ? (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="暂无 AI 图片资产。"
                    style={{ padding: 32 }}
                  />
                ) : (
                  <Row gutter={[12, 12]}>
                    {assets.map((asset) => (
                      <Col xs={12} sm={8} md={6} key={asset.id}>
                        <Card
                          size="small"
                          hoverable
                          styles={{ body: { padding: 8 } }}
                        >
                          <div
                            style={{
                              height: 120,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              marginBottom: 6,
                              overflow: "hidden",
                              borderRadius: 4,
                              background: "#1a1a1a",
                            }}
                          >
                            {isRenderableImage(asset.file_path) ? (
                              <Image
                                alt={asset.prompt}
                                src={asset.file_path}
                                style={{
                                  maxHeight: 120,
                                  objectFit: "contain",
                                }}
                              />
                            ) : (
                              <PictureOutlined
                                style={{ fontSize: 28, color: "#555" }}
                              />
                            )}
                          </div>
                          <Text
                            strong
                            ellipsis
                            style={{ fontSize: 12, display: "block" }}
                          >
                            {asset.prompt}
                          </Text>
                          <div style={{ marginTop: 4 }}>
                            <Tag
                              style={{
                                fontSize: 10,
                                padding: "0 4px",
                                margin: 0,
                              }}
                            >
                              {asset.model_name || "image model"}
                            </Tag>
                            <Text
                              type="secondary"
                              style={{ fontSize: 10, marginLeft: 4 }}
                            >
                              {formatShanghaiTime(asset.created_at)}
                            </Text>
                          </div>
                          <Button
                            type="text" danger size="small" icon={<DeleteOutlined />}
                            onClick={async () => {
                              try {
                                await deleteGeneratedImageAsset(asset.id);
                                setAssets((prev) => prev.filter((a) => a.id !== asset.id));
                              } catch { /* global interceptor shows error */ }
                            }}
                            style={{ width: "100%", marginTop: 4 }}
                          >
                            删除
                          </Button>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                )}
              </>
            ),
          },
          {
            key: "user_images",
            label: (
              <Space>
                <PictureOutlined /> 普通图片资产
              </Space>
            ),
            children: (
              <>
                <div style={{ marginBottom: 16 }}>
                  <Upload
                    accept="image/*"
                    showUploadList={false}
                    beforeUpload={(file) => {
                      void handleUploadFile(file);
                      return false;
                    }}
                  >
                    <Button icon={<UploadOutlined />}>上传图片</Button>
                  </Upload>
                </div>
                {userImages.length === 0 ? (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="暂无普通图片资产。上传图片后将显示在这里。"
                    style={{ padding: 32 }}
                  />
                ) : (
                  <Row gutter={[12, 12]}>
                    {userImages.map((img) => (
                      <Col xs={12} sm={8} md={6} key={img.file_name}>
                        <Card
                          size="small"
                          hoverable
                          styles={{ body: { padding: 8 } }}
                        >
                          <div
                            style={{
                              height: 120,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              marginBottom: 6,
                              overflow: "hidden",
                              borderRadius: 4,
                              background: "#1a1a1a",
                            }}
                          >
                            <Image
                              alt={img.file_name}
                              src={img.url}
                              style={{
                                maxHeight: 120,
                                objectFit: "contain",
                              }}
                            />
                          </div>
                          <Text
                            strong
                            ellipsis
                            style={{ fontSize: 12, display: "block" }}
                          >
                            {img.file_name}
                          </Text>
                          <Text type="secondary" style={{ fontSize: 10 }}>
                            {(img.size / 1024).toFixed(1)} KB
                          </Text>
                          <Button
                            type="text" danger size="small" icon={<DeleteOutlined />}
                            onClick={async () => {
                              try {
                                await deleteUserImage(img.file_name);
                                setUserImages((prev) => prev.filter((i) => i.file_name !== img.file_name));
                              } catch { /* global interceptor shows error */ }
                            }}
                            style={{ width: "100%", marginTop: 4 }}
                          >
                            删除
                          </Button>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                )}
              </>
            ),
          },
        ]}
      />

      {/* ---- Reference Image Picker Modal ---- */}
      <Modal
        title="选择图片"
        open={refPickerOpen}
        onCancel={() => setRefPickerOpen(false)}
        footer={null}
        width={640}
        destroyOnClose
      >
        <Tabs
          defaultActiveKey="user_images"
          items={[
            {
              key: "user_images",
              label: (
                <Space>
                  <PictureOutlined /> 普通图片资产
                </Space>
              ),
              children:
                userImages.length === 0 ? (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="暂无普通图片资产。"
                    style={{ padding: 24 }}
                  />
                ) : (
                  <Row gutter={[8, 8]}>
                    {userImages.map((img) => (
                      <Col span={6} key={img.file_name}>
                        <div
                          onClick={() => handlePickerSelect(img.url)}
                          style={{
                            cursor: "pointer",
                            borderRadius: 4,
                            overflow: "hidden",
                            border: "1px solid #333",
                            height: 80,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            background: "#1a1a1a",
                          }}
                        >
                          <img
                            src={img.url}
                            alt={img.file_name}
                            style={{
                              maxHeight: 80,
                              maxWidth: "100%",
                              objectFit: "contain",
                            }}
                          />
                        </div>
                      </Col>
                    ))}
                  </Row>
                ),
            },
            {
              key: "ai_assets",
              label: (
                <Space>
                  <StarOutlined /> AI 图片资产
                </Space>
              ),
              children:
                assets.length === 0 ? (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="暂无 AI 图片资产。"
                    style={{ padding: 24 }}
                  />
                ) : (
                  <Row gutter={[8, 8]}>
                    {assets.map((asset) => (
                      <Col span={6} key={asset.id}>
                        <div
                          onClick={() => handlePickerSelect(asset.file_path)}
                          style={{
                            cursor: "pointer",
                            borderRadius: 4,
                            overflow: "hidden",
                            border: "1px solid #333",
                            height: 80,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            background: "#1a1a1a",
                          }}
                        >
                          {isRenderableImage(asset.file_path) ? (
                            <img
                              src={asset.file_path}
                              alt={asset.prompt}
                              style={{
                                maxHeight: 80,
                                maxWidth: "100%",
                                objectFit: "contain",
                              }}
                            />
                          ) : (
                            <PictureOutlined
                              style={{ fontSize: 24, color: "#555" }}
                            />
                          )}
                        </div>
                      </Col>
                    ))}
                  </Row>
                ),
            },
            {
              key: "url",
              label: (
                <Space>
                  <LinkOutlined /> URL
                </Space>
              ),
              children: (
                <Space.Compact style={{ width: "100%" }}>
                  <Input
                    value={pickerUrlInput}
                    onChange={(e) => setPickerUrlInput(e.target.value)}
                    placeholder="输入图片 URL"
                    onPressEnter={handlePickerUrlAdd}
                  />
                  <Button type="primary" onClick={handlePickerUrlAdd}>
                    添加
                  </Button>
                </Space.Compact>
              ),
            },
          ]}
        />
      </Modal>
    </div>
  );
}
